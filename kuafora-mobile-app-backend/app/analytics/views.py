from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count, Q, Avg, Sum, F
from django.db.models.functions import TruncDate, TruncHour
from datetime import timedelta, datetime
from app.analytics.models import AppEvent, ScreenView, FeatureUsage, UserSession, UserActivityLog
from app.users.models import User
from app.analytics.serializers import (
    AppEventSerializer, ScreenViewSerializer, FeatureUsageSerializer,
    UserSessionSerializer, BatchTrackingSerializer
)


class TrackingViewSet(viewsets.ViewSet):
    """Tracking verilerini toplama endpoint'leri"""
    permission_classes = [permissions.AllowAny]  # Anonim kullanıcılar da tracking gönderebilir

    def _touch_activity_log(self, *, user, device_id: str, app_type: str, increment: bool) -> None:
        """Her yeni session oluştuğunda günlük aktivite logunu güncelle.

        - **increment=True**: yeni bir session_id oluşturuldu (günlük login_count +1)
        - **increment=False**: session update (sadece last_activity güncelle)
        """
        if not device_id:
            return
        if not app_type:
            app_type = "main"

        today = timezone.now().date()
        now = timezone.now()

        # Anonymous (user=None) kayıtlarında unique constraint yok; çoğalmayı engellemek için
        # mevcut ilk kaydı güncelliyoruz, yoksa oluşturuyoruz.
        if user is None:
            qs = UserActivityLog.objects.filter(
                user__isnull=True,
                device_id=device_id,
                activity_date=today,
                app_type=app_type,
            ).order_by("id")
            obj = qs.first()
            if obj:
                if increment:
                    obj.login_count = F("login_count") + 1
                obj.last_activity = now
                obj.save(update_fields=["login_count", "last_activity"] if increment else ["last_activity"])
            else:
                UserActivityLog.objects.create(
                    user=None,
                    device_id=device_id,
                    activity_date=today,
                    app_type=app_type,
                    login_count=1 if increment else 0,
                    last_activity=now,
                )
            return

        # Authenticated user: unique_together ile güvenli update_or_create
        defaults = {"last_activity": now}
        if increment:
            # login_count artırmak için önce getirip atomic increment yapıyoruz
            obj, created = UserActivityLog.objects.get_or_create(
                user=user,
                device_id=device_id,
                activity_date=today,
                app_type=app_type,
                defaults={"login_count": 1, "last_activity": now},
            )
            if not created:
                UserActivityLog.objects.filter(pk=obj.pk).update(
                    login_count=F("login_count") + 1,
                    last_activity=now,
                )
        else:
            UserActivityLog.objects.update_or_create(
                user=user,
                device_id=device_id,
                activity_date=today,
                app_type=app_type,
                defaults=defaults,
            )
    
    @action(detail=False, methods=['post'], url_path='batch')
    def batch_tracking(self, request):
        """Toplu tracking verisi gönderme (performans için)"""
        try:
            serializer = BatchTrackingSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            data = serializer.validated_data
            user = request.user if request.user.is_authenticated else None
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Rate limiting: Çok fazla veri gönderilirse sınırla
            total_items = len(data.get('events', [])) + len(data.get('screen_views', [])) + len(data.get('feature_usages', []))
            if total_items > 1000:
                return Response({'error': 'Too many items in batch. Maximum 1000 items allowed.'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Session güncelleme/oluşturma
            session_data = data.get('session')
            if session_data:
                session_id = session_data.get('session_id')
                if session_id:
                    try:
                        session, created = UserSession.objects.update_or_create(
                            session_id=session_id,
                            defaults={
                                'user': user,
                                'device_id': session_data.get('device_id', ''),
                                'app_type': session_data.get('app_type', 'main'),
                                'platform': session_data.get('platform', ''),
                                'app_version': session_data.get('app_version', ''),
                                'os_version': session_data.get('os_version', ''),
                                'end_time': session_data.get('end_time'),
                                'ip_address': ip_address,
                                'user_agent': user_agent,
                            }
                        )
                        if session.end_time:
                            session.calculate_duration()
                        # ✅ Daily activity log: sadece yeni session oluştuysa login say
                        self._touch_activity_log(
                            user=user,
                            device_id=session.device_id,
                            app_type=session.app_type,
                            increment=created,
                        )
                    except Exception:
                        pass  # Ignore session errors
            
            # Events kaydetme
            events = data.get('events', [])
            if events:
                event_objs = []
                for event_data in events:
                    event_objs.append(AppEvent(
                        user=user,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        **event_data
                    ))
                try:
                    AppEvent.objects.bulk_create(event_objs, ignore_conflicts=True, batch_size=500)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f'Error creating app events: {e}')
                
                # Session'a event count ekle
                if session_data and session_data.get('session_id'):
                    try:
                        UserSession.objects.filter(
                            session_id=session_data['session_id']
                        ).update(event_count=F('event_count') + len(events))
                    except Exception:
                        pass
            
            # Screen views kaydetme
            screen_views = data.get('screen_views', [])
            if screen_views:
                view_objs = []
                for view_data in screen_views:
                    view_objs.append(ScreenView(
                        user=user,
                        **view_data
                    ))
                try:
                    ScreenView.objects.bulk_create(view_objs, ignore_conflicts=True, batch_size=500)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f'Error creating screen views: {e}')
                
                # Session'a screen count ekle
                if session_data and session_data.get('session_id'):
                    try:
                        UserSession.objects.filter(
                            session_id=session_data['session_id']
                        ).update(screen_count=F('screen_count') + len(screen_views))
                    except Exception:
                        pass
            
            # Feature usages kaydetme
            feature_usages = data.get('feature_usages', [])
            if feature_usages:
                usage_objs = []
                for usage_data in feature_usages:
                    usage_objs.append(FeatureUsage(
                        user=user,
                        **usage_data
                    ))
                try:
                    FeatureUsage.objects.bulk_create(usage_objs, ignore_conflicts=True, batch_size=500)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f'Error creating feature usages: {e}')
            
            return Response({'status': 'success', 'saved': {
                'events': len(events),
                'screen_views': len(screen_views),
                'feature_usages': len(feature_usages),
            }}, status=status.HTTP_201_CREATED)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error in batch_tracking: {e}')
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], url_path='event')
    def track_event(self, request):
        """Tek event tracking"""
        serializer = AppEventSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                user=request.user if request.user.is_authenticated else None,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], url_path='screen')
    def track_screen(self, request):
        """Ekran görüntüleme tracking"""
        serializer = ScreenViewSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                user=request.user if request.user.is_authenticated else None
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], url_path='feature')
    def track_feature(self, request):
        """Özellik kullanım tracking"""
        serializer = FeatureUsageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                user=request.user if request.user.is_authenticated else None
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], url_path='session')
    def track_session(self, request):
        """Oturum tracking"""
        serializer = UserSessionSerializer(data=request.data)
        if serializer.is_valid():
            session_id = serializer.validated_data.get('session_id')
            if session_id:
                session, created = UserSession.objects.update_or_create(
                    session_id=session_id,
                    defaults={
                        **serializer.validated_data,
                        'user': request.user if request.user.is_authenticated else None,
                        'ip_address': self._get_client_ip(request),
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    }
                )
                if session.end_time:
                    session.calculate_duration()
                # ✅ Daily activity log: sadece yeni session oluştuysa login say
                self._touch_activity_log(
                    user=session.user,
                    device_id=session.device_id,
                    app_type=session.app_type,
                    increment=created,
                )
                return Response(UserSessionSerializer(session).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def _get_client_ip(self, request):
        """Client IP adresini al"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class AnalyticsViewSet(viewsets.ViewSet):
    """Admin için analytics verileri"""
    permission_classes = [permissions.IsAdminUser]
    
    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard_stats(self, request):
        """Dashboard için özet istatistikler"""
        now = timezone.now()
        today = now.date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # App opens (son 30 gün)
        app_opens = AppEvent.objects.filter(
            event_type='app_open',
            timestamp__gte=timezone.make_aware(datetime.combine(month_ago, datetime.min.time()))
        ).count()
        
        # Aktif kullanıcılar: benzersiz cihaz (device_id) bazlı,
        # ana mobil uygulama (app_type='main') için hesaplanır.
        # Kullanıcının login olup olmamasından bağımsızdır.
        session_qs = UserSession.objects.filter(app_type='main')

        # Daily active users: bugün en az bir kez uygulamayı açan benzersiz cihaz sayısı
        daily_active = session_qs.filter(
            start_time__date=today
        ).values('device_id').distinct().count()

        # Weekly active users: son 7 günde en az bir kez uygulamayı açan benzersiz cihaz sayısı
        weekly_active = session_qs.filter(
            start_time__date__gte=week_ago
        ).values('device_id').distinct().count()

        # Monthly active users: son 30 günde en az bir kez uygulamayı açan benzersiz cihaz sayısı
        monthly_active = session_qs.filter(
            start_time__date__gte=month_ago
        ).values('device_id').distinct().count()
        
        # Average session duration (son 30 gün)
        avg_session_duration = UserSession.objects.filter(
            start_time__gte=timezone.make_aware(datetime.combine(month_ago, datetime.min.time())),
            duration__isnull=False
        ).aggregate(avg=Avg('duration'))['avg'] or 0
        
        # Top screens (son 30 gün)
        top_screens = ScreenView.objects.filter(
            timestamp__gte=timezone.make_aware(datetime.combine(month_ago, datetime.min.time()))
        ).values('screen_name', 'app_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Top features (son 30 gün)
        top_features = FeatureUsage.objects.filter(
            timestamp__gte=timezone.make_aware(datetime.combine(month_ago, datetime.min.time()))
        ).values('feature_type', 'app_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Daily app opens chart (son 7 gün)
        daily_opens = []
        for i in range(7):
            date = today - timedelta(days=6-i)
            date_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
            date_end = timezone.make_aware(datetime.combine(date, datetime.max.time()))
            count = AppEvent.objects.filter(
                event_type='app_open',
                timestamp__gte=date_start,
                timestamp__lte=date_end
            ).count()
            daily_opens.append({
                'date': date.strftime('%d.%m'),
                'count': count
            })
        
        # App type distribution
        app_distribution = UserSession.objects.filter(
            start_time__gte=timezone.make_aware(datetime.combine(month_ago, datetime.min.time()))
        ).values('app_type').annotate(
            count=Count('id')
        )

        return Response({
            'app_opens': app_opens,
            'daily_active_users': daily_active,
            'weekly_active_users': weekly_active,
            'monthly_active_users': monthly_active,
            'avg_session_duration': round(avg_session_duration, 2),
            'top_screens': list(top_screens),
            'top_features': list(top_features),
            'daily_opens_chart': daily_opens,
            'app_distribution': list(app_distribution),
        })

    @action(detail=False, methods=['get'], url_path='user-activity')
    def user_activity(self, request):
        """
        Belirli bir kullanıcının hangi günlerde ve bir günde kaç defa uygulamaya girdiğini döner.
        - Query params:
          - user_id (zorunlu)
          - days (opsiyonel, varsayılan: 90)
          - app_type (opsiyonel, varsayılan: 'main')
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': 'user_id query parametresi zorunlu'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'Kullanıcı bulunamadı'}, status=status.HTTP_404_NOT_FOUND)

        try:
            days = int(request.query_params.get('days', '90'))
            if days <= 0:
                days = 90
        except ValueError:
            days = 90

        app_type = request.query_params.get('app_type', 'main').strip() or 'main'

        now = timezone.now()
        end_date = now.date()
        start_date = end_date - timedelta(days=days - 1)

        # Sadece ilgili kullanıcının, seçili app_type için oturumları
        qs = UserSession.objects.filter(
            user=user,
            app_type=app_type,
            start_time__date__gte=start_date,
            start_time__date__lte=end_date,
        )

        # Gün bazında kaç oturum açtığını hesapla
        per_day_qs = qs.annotate(day=TruncDate('start_time')).values('day').annotate(
            session_count=Count('id')
        ).order_by('day')

        per_day = [
            {
                'date': item['day'],
                'session_count': item['session_count'],
            }
            for item in per_day_qs
        ]

        total_days_used = len(per_day)
        total_sessions = qs.count()

        return Response({
            'user_id': str(user.id),
            'app_type': app_type,
            'start_date': start_date,
            'end_date': end_date,
            'total_days_used': total_days_used,
            'total_sessions': total_sessions,
            'per_day': per_day,
        })

