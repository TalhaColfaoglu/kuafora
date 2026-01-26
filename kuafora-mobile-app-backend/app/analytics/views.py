from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count, Q, Avg, Sum, F
from django.db.models.functions import TruncDate, TruncHour
from datetime import timedelta, datetime
from app.analytics.models import AppEvent, ScreenView, FeatureUsage, UserSession
from app.analytics.serializers import (
    AppEventSerializer, ScreenViewSerializer, FeatureUsageSerializer,
    UserSessionSerializer, BatchTrackingSerializer
)


class TrackingViewSet(viewsets.ViewSet):
    """Tracking verilerini toplama endpoint'leri"""
    permission_classes = [permissions.AllowAny]  # Anonim kullanıcılar da tracking gönderebilir
    
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
        
        # Daily active users (son 24 saatte app açan unique kullanıcılar)
        daily_active = UserSession.objects.filter(
            start_time__gte=now - timedelta(hours=24)
        ).values('user').distinct().count()
        
        # Weekly active users
        weekly_active = UserSession.objects.filter(
            start_time__gte=timezone.make_aware(datetime.combine(week_ago, datetime.min.time()))
        ).values('user').distinct().count()
        
        # Monthly active users
        monthly_active = UserSession.objects.filter(
            start_time__gte=timezone.make_aware(datetime.combine(month_ago, datetime.min.time()))
        ).values('user').distinct().count()
        
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

