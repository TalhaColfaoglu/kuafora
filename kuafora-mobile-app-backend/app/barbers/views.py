from __future__ import annotations

from typing import List

from django.db.models import Prefetch, Q, Count
from django.db.models.functions import Trim
from django.core.cache import cache
from django.utils.encoding import force_str
import hashlib
import json
from drf_spectacular.utils import extend_schema
from app.notifications.utils import (
    notify_shop_about_new_review,
    notify_customer_about_reply,
    notify_shop_staff_about_staff_change,
    notify_shop_staff_about_shop_schedule_change,
)
from rest_framework import viewsets, mixins, permissions, generics, status, serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.permissions import BasePermission
from django.utils import timezone
from django.core.exceptions import MultipleObjectsReturned
from datetime import timedelta, datetime

from .models import (
    Favorite,
    Barbershop,
    BarbershopAppeal,
    Staff,
    StaffService,
    StaffServiceCategory,
    WorkSchedule,
    ShopWorkingHours,
    StaffWorkingHours,
    Override,
    SpecialMessage,
    MessageViewLog,
    CalendarAuditLog,
    Review,
    ReviewReply,
    Service,
    ServiceCategory,
    LastViewed,
    ViewEvent,
    OfficialHoliday,
    ShopHolidayOverride,
    DailyOverride,
    BreakWindow,
    ScheduleChangeRequest,
    ShopCategory,
)
from .services.schedule import check_and_cancel_conflicts
from .serializers import (
    BarbershopWithFavoriteSerializer,
    FavoriteSerializer,
    BarbershopSerializer,
    ReviewSerializer,
    ReviewReplySerializer,
    StaffSerializer,
    StaffServiceSerializer,
    StaffServiceCategorySerializer,
    WorkScheduleSerializer,
    ServiceSerializer,
    ServiceCategorySerializer,
    LastViewedSerializer,
    InviteStaffSerializer,
    StaffHoursSerializer,
    ShopWorkingHoursSerializer,
    StaffWorkingHoursSerializer,
    OverrideSerializer,
    SpecialMessageSerializer,
    MessageViewLogSerializer,
    CalendarAuditLogSerializer,
    CalendarStatusSerializer,
    StaffCalendarStatusSerializer,
    WeeklyCalendarSerializer,
    OfficialHolidaySerializer,
    ShopHolidayOverrideSerializer,
    DailyOverrideSerializer,
    BreakWindowSerializer,
    ShopCategorySerializer,
)
from .filters import BarbershopFilter
from .permissions import IsShopAdmin
from .permissions_replies import IsReplyOwnerOrShopAdmin
from django.conf import settings
from .services.breaks import break_windows_by_date, serialize_break_window


def _jsonable(value):
    """Safely convert complex objects (models, date/time) into JSON-serializable structures."""
    from django.db.models import Model
    from datetime import date, time, datetime as _dt
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, Model):
        # Prefer primary key
        try:
            return getattr(value, "pk", str(value))
        except Exception:
            return str(value)
    if isinstance(value, time):
        try:
            return value.strftime("%H:%M")
        except Exception:
            return str(value)
    if isinstance(value, date):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    if isinstance(value, _dt):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    # Fallback
    try:
        return str(value)
    except Exception:
        return None


class IsStaffMember(BasePermission):
    """
    Permission to only allow staff members to access staff-related endpoints.
    Handles cases where a user might have multiple staff records.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        # Use exists() to safely check if user has at least one staff record
        return Staff.objects.filter(user=request.user).exists()


class BarbershopViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Optimized ViewSet for barbershop listings with caching and query optimization.
    """
    queryset = (
        Barbershop.objects.all()
        .select_related("subscription")  # Optimize foreign key lookups (owner field doesn't exist in Barbershop model)
        .prefetch_related("images", "services", "staff", "categories", "catalog")  # Optimize many-to-many and reverse FK
    )
    serializer_class = BarbershopSerializer
    filterset_class = BarbershopFilter
    search_fields = ("name", "city", "district")
    # Use larger pagination for map views
    pagination_class = None  # Will be set dynamically based on request

    def get_pagination_class(self, request=None):
        """Dynamically set pagination based on request type."""
        from app.core.pagination import StandardPageNumberPagination, LargePageNumberPagination
        
        # Use provided request or fall back to self.request
        req = request or getattr(self, 'request', None)
        if not req:
            return StandardPageNumberPagination
        
        # For map views, use larger page size
        if any(param in req.query_params for param in ['min_lat', 'max_lat', 'min_lng', 'max_lng']):
            return LargePageNumberPagination
        return StandardPageNumberPagination

    def get_queryset(self):
        qs = super().get_queryset()
        
        # Abonelik filtreleme: Sadece aktif aboneliği olanları göster (Ana uygulama için)
        # Partner/Vitrin uygulaması include_inactive=true gönderebilir
        include_inactive = self.request.query_params.get("include_inactive", "").lower() == "true"
        
        if not include_inactive:
            # Aktif abonelik durumları: trial, active, lifetime, grace_period
            # Aboneliği olmayan veya suspended/cancelled olanları hariç tut
            # Artık sadece aktif subscription'ı olanlar gösterilecek
            # Banlı kuaförleri de filtrele (is_verified=False olanlar)
            # İsimsiz kuaförleri de filtrele
            qs = qs.filter(
                subscription__status__in=['trial', 'active', 'lifetime', 'grace_period'],
                is_verified=True,  # Banlı kuaförleri filtrele
                is_approved=True,  # Admin onayı - sadece onaylanmış kuaförler ana uygulamada görünür
                name__isnull=False  # İsimsiz kuaförleri filtrele
            ).exclude(name='')  # Boş string isimleri de filtrele
        
        # Viewport filtreleme (Harita optimizasyonu)
        try:
            min_lat = self.request.query_params.get("min_lat")
            max_lat = self.request.query_params.get("max_lat")
            min_lng = self.request.query_params.get("min_lng")
            max_lng = self.request.query_params.get("max_lng")

            if all([min_lat, max_lat, min_lng, max_lng]):
                qs = qs.filter(
                    latitude__gte=float(min_lat),
                    latitude__lte=float(max_lat),
                    longitude__gte=float(min_lng),
                    longitude__lte=float(max_lng)
                )
        except (ValueError, TypeError):
            pass # Geçersiz parametreleri yut, tümünü döndür

        user = self.request.user
        if user.is_authenticated:
            if getattr(user, "gender", None) == "male":
                qs = qs.filter(Q(gender="male") | Q(gender="unisex"))
            elif getattr(user, "gender", None) == "female":
                qs = qs.filter(Q(gender="female") | Q(gender="unisex"))
        return qs

    def get_object(self):
        """Override to check subscription status for detail view"""
        obj = super().get_object()
        
        # Ana uygulama için subscription kontrolü (detail view)
        include_inactive = self.request.query_params.get("include_inactive", "").lower() == "true"
        
        if not include_inactive:
            # İsim kontrolü - İsimsiz kuaförleri engelle
            if not obj.name or obj.name.strip() == '':
                from rest_framework.exceptions import NotFound
                raise NotFound("Barbershop not found")
            
            # Ban kontrolü - Banlı kuaförleri engelle
            if not obj.is_verified:
                from rest_framework.exceptions import NotFound
                raise NotFound("Barbershop not found")
            
            # Aktif subscription kontrolü
            if not hasattr(obj, 'subscription') or obj.subscription.status not in ['trial', 'active', 'lifetime', 'grace_period']:
                from rest_framework.exceptions import NotFound
                raise NotFound("Barbershop not found or subscription inactive")
        
        return obj

    def get_serializer_class(self):
        # Use detail serializer for retrieve to include is_favorited
        if getattr(self, "action", None) == "retrieve":
            from .serializers import BarbershopDetailSerializer
            return BarbershopDetailSerializer
        return super().get_serializer_class()

    def retrieve(self, request, *args, **kwargs):
        """Detay yanıtına is_open ekle (En Son Bakılanlar kartları için)."""
        response = super().retrieve(request, *args, **kwargs)
        if response.status_code != 200 or not response.data:
            return response
        try:
            instance = self.get_object()
            from django.utils import timezone as dj_tz
            ts = dj_tz.now()
            data = _compute_shop_status(instance.id, ts)
            response.data["is_open"] = data.get("status") == "open"
            open_interval = data.get("open_interval") or {}
            if open_interval:
                response.data["opening_time"] = open_interval.get("start")
                response.data["closing_time"] = open_interval.get("end")
        except Exception:
            response.data["is_open"] = False
        return response

    def list(self, request, *args, **kwargs):
        """
        Override list to add caching and dynamic pagination for frequently accessed barbershop lists.
        Cache key includes all query parameters to ensure correct filtering.
        """
        # Set dynamic pagination based on request type
        self.pagination_class = self.get_pagination_class(request)
        
        # Cache sadece GET istekleri için ve include_inactive yoksa (ana uygulama için)
        include_inactive = request.query_params.get("include_inactive", "").lower() == "true"
        
        # Partner uygulaması için cache yapma (include_inactive=true)
        if include_inactive:
            return super().list(request, *args, **kwargs)
        
        # Cache key oluştur - tüm query parametrelerini dahil et
        query_params = dict(request.query_params)
        # Sıralama için normalize et
        query_str = json.dumps(query_params, sort_keys=True)
        cache_key = f"barbershop_list_{hashlib.md5(query_str.encode()).hexdigest()}"
        
        # Cache'den kontrol et (3 dakika TTL - barbershop listesi sık değişmez)
        cached_response = cache.get(cache_key)
        if cached_response is not None:
            return Response(cached_response)
        
        # Normal list işlemini yap
        response = super().list(request, *args, **kwargs)
        
        # Cache'e kaydet (sadece başarılı response'ları)
        if response.status_code == 200:
            cache.set(cache_key, response.data, 180)  # 3 dakika
        
        return response

    @action(detail=False, methods=["get"], url_path="available-locations")
    def available_locations(self, request):
        """
        Ana uygulama arama filtresi için sadece sistemde gerçekten kayıtlı (listelenebilir) şehir/ilçe listesini döndürür.
        - Şehirde hiç kuaför yoksa şehir dönmez.
        - Şehir içinde ilçede hiç kuaför yoksa o ilçe dönmez.
        Not: Bu endpoint, BarbershopViewSet'in ana listeleme mantığıyla aynı "listelenebilir" kriterlerini uygular
        (aktif subscription + is_verified + isim dolu). Böylece UI'da sadece seçilebilir seçenekler görünür.
        Pagination disabled: Returns a dictionary, not a list.
        """
        # Disable pagination for this action (returns dict, not list)
        original_pagination = self.pagination_class
        self.pagination_class = None
        
        try:
            qs = Barbershop.objects.all()

            include_inactive = request.query_params.get("include_inactive", "").lower() == "true"
            if not include_inactive:
                qs = (
                    qs.filter(
                        subscription__status__in=["trial", "active", "lifetime", "grace_period"],
                        is_verified=True,
                        is_approved=True,  # Admin onayı - sadece onaylanmış kuaförler ana uygulamada görünür
                        name__isnull=False,
                    )
                    .exclude(name="")
                )

            # Kullanıcı girişliyse, ana listede uygulanan cinsiyet kuralı ile uyumlu olsun
            user = request.user
            if getattr(user, "is_authenticated", False):
                if getattr(user, "gender", None) == "male":
                    qs = qs.filter(Q(gender="male") | Q(gender="unisex"))
                elif getattr(user, "gender", None) == "female":
                    qs = qs.filter(Q(gender="female") | Q(gender="unisex"))

            # Trim ile baş/son boşluklardan arındırıp unique al
            pairs = (
                qs.annotate(city_t=Trim("city"), district_t=Trim("district"))
                .exclude(city_t__isnull=True)
                .exclude(district_t__isnull=True)
                .exclude(city_t="")
                .exclude(district_t="")
                .values("city_t", "district_t")
                .distinct()
                .order_by("city_t", "district_t")
            )

            out: dict[str, list[str]] = {}
            for it in pairs:
                city = it.get("city_t") or ""
                district = it.get("district_t") or ""
                if not city or not district:
                    continue
                out.setdefault(city, []).append(district)

            # İlçeleri tekilleştirip deterministik sırala
            for city in list(out.keys()):
                out[city] = sorted(set(out[city]))

            return Response(out)
        finally:
            # Restore pagination for other actions
            self.pagination_class = original_pagination

    @action(detail=True, methods=["get"], url_path="services")
    def services(self, request, pk=None):
        """
        Get services for a barbershop.
        Pagination disabled: Returns a small list of services for a single shop.
        """
        # Disable pagination for this action (returns small list for single shop)
        original_pagination = self.pagination_class
        self.pagination_class = None
        
        try:
            staff_id = request.query_params.get('staff_id')
            
            if staff_id:
                staff_services = StaffService.objects.filter(
                    staff__id=staff_id, 
                    staff__barbershop_id=pk,
                    is_active=True
                ).select_related('service', 'service__category')
                
                data = []
                for ss in staff_services:
                    svc = ss.service
                    data.append({
                        "id": svc.id,
                        "name": svc.name,
                        "description": getattr(svc, 'description', ''),
                        "price": ss.price,
                        "duration": ss.duration_minutes,
                        "category_id": svc.category_id,
                        "category_name": svc.category.name if svc.category else None,
                        "is_active": True,
                        "price_range": {'min': float(ss.price), 'max': float(ss.price)},
                        "target_gender": getattr(svc, 'target_gender', None),
                    })
                return Response(data)

            services = Service.objects.filter(barbershop_id=pk, is_active=True)
            serializer = ServiceSerializer(services, many=True)
            return Response(serializer.data)
        finally:
            # Restore pagination for other actions
            self.pagination_class = original_pagination

    @action(detail=False, methods=["post"], url_path="today-toggle", permission_classes=[permissions.IsAuthenticated])
    def today_toggle(self, request):
        """Adminler için bugünlük manuel şalter (open/closed).
        BarbershopViewSet.toggle ile aynı mantık; prod router uyuşmazlıkları için güvenli rota.
        Döner: {ok: bool, error?: {code,message}}
        """
        try:
            shop_id = request.data.get('barbershop_id') or request.query_params.get('barbershop_id')
            status_val = (request.data.get('status') or '').lower()
            note = request.data.get('note', '')
            if not shop_id:
                return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'barbershop_id gerekli'}}, status=200)
            try:
                shop = Barbershop.objects.get(id=int(shop_id))
            except Barbershop.DoesNotExist:
                return Response({'ok': False, 'error': {'code': 'not_found', 'message': 'Dükkan bulunamadı'}}, status=200)
            # izin: dükkan admini olmalı
            is_admin = Staff.objects.filter(user=request.user, barbershop=shop, is_admin=True).exists()
            if not is_admin:
                return Response({'ok': False, 'error': {'code': 'forbidden', 'message': 'Bu işlem için yetkiniz yok.'}}, status=200)
            if status_val not in ('open','closed'):
                return Response({'ok': False, 'error': {'code': 'invalid_status', 'message': "Geçersiz durum. 'open' veya 'closed' olmalı."}}, status=200)

            local_now = timezone.localtime()
            today = local_now.date()
            expires_at = timezone.make_aware(datetime.combine(today, datetime.max.time())).replace(hour=23, minute=59, second=59, microsecond=0)
            obj, _ = DailyOverride.objects.update_or_create(
                barbershop=shop,
                date=today,
                defaults={
                    'status': status_val,
                    'note': note or ("Manuel kapatma" if status_val=='closed' else "Manuel açma"),
                    'expires_at': expires_at,
                    'created_by': request.user,
                }
            )
            # Sinyaller cache'i temizleyecek
            return Response({'ok': True, 'data': DailyOverrideSerializer(obj).data}, status=200)
        except Exception as e:
            return Response({'ok': False, 'error': {'code': 'unknown', 'message': str(e)}}, status=200)

    @action(detail=True, methods=["get"], url_path="staff")
    def staff(self, request, pk=None):
        # Disable pagination for this action (returns small list for single shop)
        original_pagination = self.pagination_class
        self.pagination_class = None
        try:
            staff = Staff.objects.filter(barbershop_id=pk).prefetch_related(
                "staff_working_hours"
            )
            serializer = StaffSerializer(staff, many=True)
            return Response(serializer.data)
        finally:
            self.pagination_class = original_pagination

    @action(detail=True, methods=["get"], url_path="services-tree")
    def services_tree(self, request, pk=None):
        """
        Get barbershop's categories and services in tree structure.
        Accessible to authenticated staff of this barbershop.
        Pagination disabled: Returns a tree structure, not a list.
        """
        # Disable pagination for this action (returns tree structure)
        original_pagination = self.pagination_class
        self.pagination_class = None
        try:
            barbershop = self.get_object()
            
            categories = ServiceCategory.objects.filter(
                barbershop=barbershop
            ).prefetch_related(
            Prefetch('services', queryset=Service.objects.filter(is_active=True))
        ).order_by('name')
        
            result = []
            for category in categories:
                result.append({
                    'id': category.id,
                    'name': category.name,
                    'services': ServiceSerializer(category.services.all(), many=True).data
                })
            
            return Response(result)
        finally:
            # Restore pagination for other actions
            self.pagination_class = original_pagination

    @action(detail=True, methods=["get", "put"], url_path="working-hours")
    def working_hours(self, request, pk=None):
        """\
        GET: Haftalık tabloyu (7 gün) MON..SUN kodlarıyla, override'lar uygulanmış şekilde döndür.
             - Öncelik: Global override > Staff override > StaffWorkingHours > ShopWorkingHours
             - Daha kısıtlayıcı olan kazanır.
        PUT: Admin kullanıcı için mağazanın çalışma saatlerini günceller (legacy, korunur).
        Pagination disabled: Returns exactly 7 days (one week).
        """
        # Disable pagination for this action (returns fixed 7-day structure)
        original_pagination = self.pagination_class
        self.pagination_class = None
        try:
            if request.method == "GET":
                try:
                    shop = Barbershop.objects.get(id=pk)
                except Barbershop.DoesNotExist:
                    return Response({"detail": "Barbershop not found"}, status=404)

                code_list = ["MON","TUE","WED","THU","FRI","SAT","SUN"]
                result = []
                
                # Pre-fetch breaks (time_range_closed overrides) for the relevant week
                # Simplification: For standard weekly display, we just fetch overrides that might represent a "recurring break" 
                # or specific time blocks. However, standard working hours display usually needs "static" breaks.
                # If we use overrides for breaks, they are date-specific. 
                # For now, let's just check if there are any 'time_range_closed' overrides active for 'today' or general (if we had recurring).
                # But to be consistent with the plan: We will just list time_range_closed overrides for "today" if the requested day matches today,
                # or maybe just return empty list for breaks in this generic weekly view unless we have a dedicated WeeklyBreak model.
                # Given the requirement is "gunluk mola", we should probably inject breaks if the requested day is today.
                # But this endpoint returns a list of 7 days. It's a static schedule.
                # Let's inject breaks into the response if they exist as recurring Overrides (if we supported them) 
                # or just keep it simple: this endpoint shows standard hours. 
                # Wait, the user wants breaks to appear in the app. 
                # Let's try to find 'time_range_closed' overrides that are active for the current week dates.
                
                start_of_week = timezone.now().date() - timedelta(days=timezone.now().date().weekday())
                week_end = start_of_week + timedelta(days=6)
                week_breaks = break_windows_by_date(
                            barbershop=shop,
                    start_date=start_of_week,
                    end_date=week_end,
                    include_staff=True,
                )
                
                for i, code in enumerate(code_list):
                    current_date = start_of_week + timedelta(days=i)
                    try:
                        # ... existing logic for open/close ...
                        # Note: We removed the 'today' override check here because this endpoint returns
                        # the generic weekly schedule. Date-specific overrides are handled by the 
                        # availability endpoint or by specific date queries.
                        # Including timezone.localdate() check here caused the shop to appear fully closed
                        # on all days if 'today' happened to be a holiday.

                        staff_hours = StaffWorkingHours.objects.filter(
                            staff__barbershop=shop, day_of_week=code, is_closed=False,
                        )
                        shop_hours = ShopWorkingHours.objects.filter(barbershop=shop, day_of_week=code).first()

                        day_result = {'day_of_week': code, 'start_time': None, 'end_time': None, 'is_closed': True, 'breaks': []}

                        if not staff_hours.exists():
                            # StaffWorkingHours yoksa, ShopWorkingHours'a bak
                            if not shop_hours:
                                pass # defaults to closed
                            elif shop_hours.is_closed:
                                pass # defaults to closed
                            else:
                                # ShopWorkingHours var ve açık, saatleri döndür
                                day_result.update({'start_time': shop_hours.start_time, 'end_time': shop_hours.end_time, 'is_closed': False})
                        else:
                            candidates_start = [sh.start_time or (shop_hours.start_time if shop_hours else None) for sh in staff_hours]
                            candidates_end = [sh.end_time or (shop_hours.end_time if shop_hours else None) for sh in staff_hours]
                            candidates_start = [c for c in candidates_start if c is not None]
                            candidates_end = [c for c in candidates_end if c is not None]
                            
                            if candidates_start and candidates_end:
                                day_result.update({
                                    'start_time': min(candidates_start),
                                    'end_time': max(candidates_end),
                                    'is_closed': False
                                })
                            
                        # Inject breaks (time_range_closed overrides for this specific date)
                        # Find overrides for this shop that are time_range_closed and cover this date
                        breaks_qs = Override.objects.filter(
                            barbershop=shop,
                            override_scope='time_range_closed',
                            is_active=True,
                            start_date__lte=current_date,
                            end_date__gte=current_date
                        )
                        
                        day_breaks = [serialize_break_window(br) for br in week_breaks.get(current_date, [])]
                        for b in breaks_qs:
                             if b.start_time and b.end_time:
                                day_breaks.append({
                                    'start': b.start_time,
                                    'end': b.end_time,
                                    'label': b.reason or 'Özel Durum',
                                    'scope': 'override',
                                    'staff_id': None,
                                    'staff_name': None,
                                })
                        
                        day_result['breaks'] = day_breaks
                        result.append(day_result)

                    except Exception:
                        # Fallback: at least return closed state (no 500)
                        result.append({'day_of_week': code,'start_time': None,'end_time': None,'is_closed': True, 'breaks': []})
                
                # stringify times
                def _fmt(t):
                    try:
                        return t.strftime('%H:%M') if t else None
                    except Exception:
                        return None
                
                for it in result:
                    it['start_time'] = _fmt(it.get('start_time'))
                    it['end_time'] = _fmt(it.get('end_time'))
                    # fmt breaks
                    for b in it.get('breaks', []):
                        b['start'] = _fmt(b['start'])
                        b['end'] = _fmt(b['end'])

                return Response(result)

            elif request.method == "PUT":
                # PUT (normalize "week" payload)
                if not request.user or not request.user.is_authenticated:
                    return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

                admin_staff = Staff.objects.filter(barbershop_id=pk, user=request.user, is_admin=True).first()
                if not admin_staff:
                    return Response({"detail": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

                body = request.data or {}
                week = body.get("week")
                if not isinstance(week, list) or len(week) != 7:
                    return Response({"detail": "invalid_payload", "errors": {"week": "7 items required (MON..SUN)"}}, status=400)

                def parse_hhmm(s: str):
                    try:
                        hh, mm = str(s).split(":")
                        return timezone.datetime(2000, 1, 1, int(hh), int(mm)).time()
                    except Exception:
                        return None

                valid_days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
                errors = {}
                normalized = []
                zero_time = timezone.datetime(2000, 1, 1, 0, 0).time()
                for item in week:
                    day = (item.get("day") or "").upper()
                    is_closed = bool(item.get("is_closed", False))
                    open_s = item.get("open")
                    close_s = item.get("close")
                    if day not in valid_days:
                        errors[day or "?"] = "invalid_day"
                        continue
                    if is_closed:
                        # DB şemamızda start_time/end_time NOT NULL olduğu için kapalı günlerde
                        # 00:00 / 00:00 yazarız. is_closed=True olduğu için UI bu saatleri göstermeyecek.
                        normalized.append({"day": day, "is_closed": True, "open": zero_time, "close": zero_time})
                        continue
                    # is_closed=False ise mutlaka open ve close olmalı
                    if open_s is None or close_s is None:
                        errors[day] = "invalid_time"
                        continue
                    st = parse_hhmm(open_s)
                    et = parse_hhmm(close_s)
                    if not st or not et:
                        errors[day] = "invalid_time"
                        continue
                    # Mola saatleri (opsiyonel)
                    break_start_s = item.get("break_start")
                    break_end_s = item.get("break_end")
                    break_start = parse_hhmm(break_start_s) if break_start_s else None
                    break_end = parse_hhmm(break_end_s) if break_end_s else None
                    
                    normalized.append({
                        "day": day, 
                        "is_closed": False, 
                        "open": st, 
                        "close": et,
                        "break_start": break_start,
                        "break_end": break_end,
                    })

                if errors:
                    return Response({"detail": "invalid_payload", "errors": errors}, status=400)

                # Replace ShopWorkingHours for this shop
                ShopWorkingHours.objects.filter(barbershop_id=pk).delete()
                for it in normalized:
                    ShopWorkingHours.objects.create(
                        barbershop_id=pk,
                        day_of_week=it["day"],
                        is_closed=it["is_closed"],
                        start_time=it["open"],
                        end_time=it["close"],
                        break_start_time=it.get("break_start"),
                        break_end_time=it.get("break_end"),
                    )
                return Response({"detail": "Updated"})
        finally:
            # Restore pagination for other actions
            self.pagination_class = original_pagination

    @action(detail=True, methods=["get", "post"], url_path="reviews")
    def reviews(self, request, pk=None):
        # POST → upsert
        if request.method == "POST":
            shop = Barbershop.objects.filter(id=pk).first()
            if not shop:
                return Response({"detail": "Barbershop not found"}, status=status.HTTP_404_NOT_FOUND)
            if not request.user or not request.user.is_authenticated:
                return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

            try:
                rating = int(request.data.get("rating"))
            except (TypeError, ValueError):
                rating = None
            if rating is None or rating < 1 or rating > 5:
                return Response({"rating": ["1 ile 5 arasında olmalı."]}, status=400)

            comment = (request.data.get("comment") or "").strip()
            is_anonymous = bool(request.data.get("is_anonymous", False))

            obj, created = Review.objects.update_or_create(
                user=request.user,
                barbershop=shop,
                defaults={"rating": rating, "comment": comment, "is_anonymous": is_anonymous},
            )

            data = ReviewSerializer(obj).data
            shop.refresh_from_db(fields=[
                "rating_avg","total_reviews","star_1_count","star_2_count","star_3_count","star_4_count","star_5_count"
            ])
            meta = {
                "rating_avg": shop.rating_avg,
                "total_reviews": shop.total_reviews,
                "star_counts": {1: shop.star_1_count, 2: shop.star_2_count, 3: shop.star_3_count, 4: shop.star_4_count, 5: shop.star_5_count},
            }
            return Response({"review": data, "meta": meta}, status=201 if created else 200)

        # GET → list with filters/pagination
        qs = Review.objects.filter(barbershop_id=pk).select_related("user")
        stars = request.query_params.get("stars")
        if stars and stars.isdigit():
            qs = qs.filter(rating=int(stars))
        order = request.query_params.get("order", "recent")
        if order == "random":
            qs = qs.order_by("?")
        else:
            qs = qs.order_by("-created_at")

        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 10))
        except ValueError:
            page, page_size = 1, 10
        start = (page - 1) * page_size
        end = start + page_size
        items = qs[start:end]

        serializer = ReviewSerializer(items, many=True)
        shop = Barbershop.objects.filter(id=pk).first()
        meta = {
            "total": qs.count(),
            "rating_avg": getattr(shop, "rating_avg", 0),
            "total_reviews": getattr(shop, "total_reviews", 0),
            "star_counts": {
                1: getattr(shop, "star_1_count", 0),
                2: getattr(shop, "star_2_count", 0),
                3: getattr(shop, "star_3_count", 0),
                4: getattr(shop, "star_4_count", 0),
                5: getattr(shop, "star_5_count", 0),
            },
        }
        return Response({"items": serializer.data, "meta": meta})
    # reviews action kaldırıldı; public liste ve upsert artık ayrı endpointlerde

    @action(detail=True, methods=["get"], url_path="status")
    def status(self, request, pk=None):
        # Tek-kaynak durum API'ye yönlendir (geriye dönük uyum için minimal)
        ts_str = request.query_params.get('ts')
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str)
                if timezone.is_naive(ts):
                     ts = timezone.make_aware(ts)
            except Exception:
                ts = timezone.now()
        else:
            ts = timezone.now()
        data = _compute_shop_status(pk, ts)
        # Mevcut şemayı koruyarak ok alanı ekle
        if isinstance(data, dict):
            data = {**data, 'ok': True}
        return Response(data)


    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, pk=None):
        """Bugünlük manuel şalter. Only today, highest priority.
        Hiçbir koşulda 4xx/5xx dönmez; ok=false + error nesnesi ile 200.
        """
        try:
            shop = Barbershop.objects.get(id=pk)
        except Barbershop.DoesNotExist:
            return Response({'ok': False, 'error': {'code': 'not_found', 'message': 'Dükkan bulunamadı'}})
        user = request.user
        # İzin: varsayılan olarak admin gerekliydi; iş akışını sadeleştirmek için aynı dükkanda herhangi bir staff'a izin ver
        has_access = Staff.objects.filter(user=user, barbershop=shop).exists()
        if not has_access:
            return Response({'ok': False, 'error': {'code': 'forbidden', 'message': 'Bu işlem için yetkiniz yok.'}})
        status_val = request.data.get('status')
        note = request.data.get('note', '')
        if status_val not in ('open','closed'):
            return Response({'ok': False, 'error': {'code': 'invalid_status', 'message': "Geçersiz durum. 'open' veya 'closed' olmalı."}})
        local_now = timezone.localtime()
        today = local_now.date()
        # Öncelik politikası: Günlük manuel şalter (DailyOverride) her zaman en üstte olmalı.
        # Bu nedenle özel gün/haftalık saat çakışmalarına bakıp reddetme YAPMAYIZ.
        expires_at = timezone.make_aware(datetime.combine(today, datetime.max.time())).replace(hour=23, minute=59, second=59, microsecond=0)
        obj, _ = DailyOverride.objects.update_or_create(
            barbershop=shop,
            date=today,
            defaults={
                'status': status_val,
                'note': note or ("Manuel kapatma" if status_val=='closed' else "Manuel açma"),
                'expires_at': expires_at,
                'created_by': user,
            }
        )
        # Cache temizle: bugünün durumunu yeniden hesaplansın
        try:
            from django.core.cache import cache
            key = f"shop_status:{shop.id}:{today.strftime('%Y-%m-%d')}"
            cache.delete(key)
        except Exception:
            pass
        # Duyuru oluştur: kısa açıklama varsa içerik olarak kullan; yoksa otomatik mesaj
        try:
            from .models import SpecialMessage
            from django.utils import timezone as dj_tz
            title = 'Dükkan Kapatıldı' if status_val == 'closed' else 'Dükkan Açıldı'
            content = (note or ("Bugünlük durum değiştirildi" if status_val=='closed' else "Bugünlük durum açıldı")).strip()
            SpecialMessage.objects.create(
                barbershop=shop,
                source='manual' if note else 'automatic',
                display_type='banner',
                target_type='all_shop',
                title=title,
                content=content,
                start_datetime=dj_tz.now(),
                end_datetime=dj_tz.now() + timedelta(days=2),
                created_by=user,
                is_active=True,
            )
        except Exception:
            pass
        return Response({'ok': True, 'data': DailyOverrideSerializer(obj).data})
def _compute_shop_status(barbershop_id: int, ts: datetime) -> dict:
    """DailyOverride > SpecialDay(Override) > OfficialHoliday(is_shop_closed) > WeeklySchedule
    Dönen şema:
    {status, source, message, next_change, open_interval:{start,end}, breaks:[]}
    """
    from django.core.cache import cache
    key = f"shop_status:{barbershop_id}:{ts.date().strftime('%Y-%m-%d')}"
    def _cache_and_return(payload: dict, timeout: int = 60):
        payload.setdefault("active_break", None)
        cache.set(key, payload, timeout=timeout)
        return payload

    cached = cache.get(key)
    if cached:
        # Eğer DailyOverride varsa cache'i bypass et - manuel değişiklikler hemen yansımalı
        do = DailyOverride.objects.filter(barbershop_id=barbershop_id, date=ts.date()).first()
        if do:
            # DailyOverride varsa cache'i temizle ve yeniden hesapla
            cache.delete(key)
        else:
            return cached
    # 1) DailyOverride (bugün)
    local_ts = timezone.localtime(ts)
    date = local_ts.date()
    shop = Barbershop.objects.filter(id=barbershop_id).first()
    if not shop:
        return {
            "status": "closed",
            "source": "WEEKLY_SCHEDULE",
            "message": "Bulunamadı",
            "next_change": None,
            "open_interval": None,
            "breaks": [],
            "active_break": None,
        }
    do = DailyOverride.objects.filter(barbershop_id=barbershop_id, date=date).first()
    if do:
        status = 'open' if do.status == 'open' else 'closed'
        # Note varsa onu kullan, yoksa varsayılan mesaj
        if do.note and do.note.strip():
            msg = do.note.strip()
        else:
            msg = "Bugün kapalı" if status == 'closed' else "Bugün açık"
        data = {
            "status": status,
            "source": "TOGGLE",
            "message": msg,
            "note": do.note or "",  # Note'u ayrıca döndür
            "next_change": None,
            "open_interval": None,
            "breaks": [],
        }
        return _cache_and_return(data)
    # 2) SpecialDay (Override) - dükkan seviyesinde sadece shop_global override'lar sayılır
    ov_shop = Override.objects.filter(
        barbershop_id=barbershop_id,
        override_type='shop_global',
        start_date__lte=date,
        end_date__gte=date,
        is_active=True,
    ).order_by('-created_at')

    # Dükkan tam gün kapalı: sadece salon izin günü (shop_global full_day_closed)
    shop_full_day = ov_shop.filter(override_scope='full_day_closed').first()
    if shop_full_day:
        data = {
            "status": "closed",
            "source": "SPECIAL_DAY",
            "message": shop_full_day.reason or "Bugün kapalı",
            "next_change": None,
            "open_interval": None,
            "breaks": [],
        }
        return _cache_and_return(data)

    # Şu an mola (sadece salon seviyesi time_range_closed)
    now_time = local_ts.time()
    active_break_override = None
    for o in ov_shop:
        if o.override_scope == 'time_range_closed' and o.start_time and o.end_time:
            if o.start_time <= now_time <= o.end_time:
                active_break_override = o
                break

    if active_break_override:
        end_dt = timezone.make_aware(datetime.combine(date, active_break_override.end_time))
        end_str = active_break_override.end_time.strftime('%H:%M')
        data = {
            "status": "closed",
            "source": "BREAK_OVERRIDE",
            "message": f"Şu an mola vakti, {end_str}'da mola bitecek.",
            "next_change": end_dt.isoformat(),
            "open_interval": None,
            "breaks": [],
            "active_break": {
                "label": active_break_override.reason or "Mola",
                "end_time": end_str,
                "scope": "override",
            },
        }
        return _cache_and_return(data)

    shop_break = (
        BreakWindow.objects.filter(
            barbershop_id=barbershop_id,
            scope=BreakWindow.Scope.SHOP,
            date=date,
            start_time__lte=now_time,
            end_time__gte=now_time,
        )
        .order_by("start_time")
        .first()
    )
    if shop_break:
        end_dt = timezone.make_aware(datetime.combine(date, shop_break.end_time))
        end_str = shop_break.end_time.strftime('%H:%M')
        data = {
            "status": "closed",
            "source": "BREAK",
            "message": f"Şu an mola vakti, {end_str}'da mola bitecek.",
            "next_change": end_dt.isoformat(),
            "open_interval": None,
            "breaks": [],
            "active_break": {
                "label": shop_break.label or "Mola",
                "end_time": end_str,
                "scope": "shop",
            },
        }
        return _cache_and_return(data)

    # Salon seviyesi saat aralığı kapalı (time_range_closed) - mola gibi göster
    top = ov_shop.filter(override_scope='time_range_closed').first() or ov_shop.first()
    if top and top.override_scope == 'time_range_closed' and top.start_time and top.end_time:
        open_interval, breaks = _effective_shop_hours_with_breaks(
            shop, date, extra_closed=[(top.start_time, top.end_time)]
        )
        msg, next_change = _message_for_state(open_interval, breaks, local_ts)
        data = {
            "status": _open_closed_now(open_interval, breaks, local_ts),
            "source": "SPECIAL_DAY",
            "message": msg,
            "next_change": next_change,
            "open_interval": _to_dict_interval(open_interval),
            "breaks": _to_list_breaks(breaks),
        }
        return _cache_and_return(data)

    # 3) OfficialHoliday (shop decision)
    shov = ShopHolidayOverride.objects.filter(barbershop_id=barbershop_id, date=date).first()
    if shov:
        if shov.status == 'closed':
            data = {
                "status": "closed",
                "source": "OFFICIAL_HOLIDAY",
                "message": shov.title or "Bugün kapalı",
                "next_change": None,
                "open_interval": None,
                "breaks": [],
            }
            return _cache_and_return(data)
        if shov.status == 'custom_hours':
            open_interval = (shov.open_time, shov.close_time)
            msg, next_change = _message_for_state(open_interval, [], local_ts)
            data = {
                "status": _open_closed_now(open_interval, [], local_ts),
                "source": "OFFICIAL_HOLIDAY",
                "message": msg,
                "next_change": next_change,
                "open_interval": _to_dict_interval(open_interval),
                "breaks": [],
            }
            return _cache_and_return(data)
    # 4) WeeklySchedule
    open_interval, breaks = _effective_shop_hours_with_breaks(shop, date)
    msg, next_change = _message_for_state(open_interval, breaks, local_ts)
    
    # Haftalık periyodik mola kontrolü (şu an mola saatinde mi?)
    weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
    code = weekday_code_map.get(date.weekday())
    shop_hours = ShopWorkingHours.objects.filter(barbershop=shop, day_of_week=code).first()
    active_break = None
    if shop_hours and shop_hours.break_start_time and shop_hours.break_end_time:
        if shop_hours.break_start_time <= now_time <= shop_hours.break_end_time:
            active_break = {
                "label": "Mola",
                "start_time": shop_hours.break_start_time.strftime('%H:%M'),
                "end_time": shop_hours.break_end_time.strftime('%H:%M'),
                "scope": "shop",
            }
    
    # NEW: Check if any staff is working (critical for shop status)
    from app.barbers.models import StaffWorkingHours
    active_staff_count = 0
    if open_interval and open_interval[0] and open_interval[1]:
        # Check if any staff is working at this time
        active_staff_count = StaffWorkingHours.objects.filter(
            staff__barbershop=shop,
            day_of_week=code,
            is_closed=False,
            start_time__lte=now_time,
            end_time__gte=now_time
        ).exclude(
            # Exclude staff with full_day_closed override
            staff__overrides__override_type='staff_individual',
            staff__overrides__override_scope='full_day_closed',
            staff__overrides__start_date__lte=date,
            staff__overrides__end_date__gte=date,
            staff__overrides__is_active=True
        ).count()
    
    # Açık/kapalı = dükkan saatleri + mola; personel sayısı sadece bilgi (kartlarda "açık" dükkan saatine göre)
    final_status = _open_closed_now(open_interval, breaks, local_ts)

    data = {
        "status": final_status,
        "source": "WEEKLY_SCHEDULE",
        "message": msg,
        "next_change": next_change,
        "open_interval": _to_dict_interval(open_interval),
        "breaks": _to_list_breaks(breaks),
        "active_break": active_break,
        "active_staff_count": active_staff_count,
    }
    return _cache_and_return(data)


def _effective_shop_hours_with_breaks(shop, date, extra_closed=None):
    weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
    code = weekday_code_map.get(date.weekday())
    sh = ShopWorkingHours.objects.filter(barbershop=shop, day_of_week=code).first()
    if not sh or sh.is_closed:
        return (None, None), []
    open_interval = (sh.start_time, sh.end_time)
    breaks = []
    
    # 1. Haftalık periyodik mola (ShopWorkingHours modelindeki break_start_time/break_end_time)
    if sh.break_start_time and sh.break_end_time:
        breaks.append(
            {
                "start": sh.break_start_time,
                "end": sh.break_end_time,
                "label": "Mola",
                "scope": "shop",
                "staff_id": None,
                "staff_name": None,
            }
        )
    
    # 2. Extra closed intervals (override'lar)
    if extra_closed:
        for item in extra_closed:
            if not item:
                continue
            start_extra, end_extra = item
            if start_extra and end_extra:
                breaks.append(
                    {
                        "start": start_extra,
                        "end": end_extra,
                        "label": "Özel Durum",
                        "scope": "override",
                        "staff_id": None,
                        "staff_name": None,
                    }
                )
    
    # 3. Tarih bazlı özel molalar (BreakWindow - belirli bir tarihe atanmış)
    for br in BreakWindow.objects.filter(barbershop=shop, scope=BreakWindow.Scope.SHOP, date=date):
        breaks.append(serialize_break_window(br))
    
    return open_interval, breaks


def _to_dict_interval(interval):
    start, end = interval if interval else (None, None)
    if not start or not end:
        return None
    return {"start": start.strftime('%H:%M'), "end": end.strftime('%H:%M')}


def _to_list_breaks(breaks):
    payload = []
    for b in breaks:
        start = b.get("start")
        end = b.get("end")
        payload.append(
            {
                "start": start.strftime("%H:%M") if hasattr(start, "strftime") else start,
                "end": end.strftime("%H:%M") if hasattr(end, "strftime") else end,
                "label": b.get("label"),
                "scope": b.get("scope", "shop"),
                "staff_id": b.get("staff_id"),
                "staff_name": b.get("staff_name"),
            }
        )
    return payload


def _open_closed_now(open_interval, breaks, ts):
    if not open_interval or not open_interval[0] or not open_interval[1]:
        return "closed"
    start_dt = timezone.make_aware(datetime.combine(ts.date(), open_interval[0]))
    end_dt = timezone.make_aware(datetime.combine(ts.date(), open_interval[1]))
    if not (start_dt <= ts <= end_dt):
        return "closed"
    # Closed if currently in a break
    for b in breaks:
        bs = timezone.make_aware(datetime.combine(ts.date(), b["start"]))
        be = timezone.make_aware(datetime.combine(ts.date(), b["end"]))
        if bs <= ts <= be:
            return "closed"
    return "open"


def _message_for_state(open_interval, breaks, ts):
    if not open_interval or not open_interval[0] or not open_interval[1]:
        # Yarın açılış tahmini
        return ("Yarın açılacak.", None)
    start_dt = timezone.make_aware(datetime.combine(ts.date(), open_interval[0]))
    end_dt = timezone.make_aware(datetime.combine(ts.date(), open_interval[1]))
    if ts < start_dt:
        return (f"{open_interval[0].strftime('%H:%M')}'de açılacak.", start_dt.isoformat())
    if ts > end_dt:
        # Tomorrow open (simple)
        return ("Yarın açılacak.", None)
    # Within day window; check if in break
    for b in breaks:
        bs = timezone.make_aware(datetime.combine(ts.date(), b["start"]))
        be = timezone.make_aware(datetime.combine(ts.date(), b["end"]))
        if bs <= ts <= be:
            return ("Şu an mola.", be.isoformat())
    return (f"{open_interval[1].strftime('%H:%M')}’a kadar açık.", end_dt.isoformat())


"""Test-only viewset removed"""


class LastViewedViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = LastViewedSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Schema jenerasyonu veya anonim isteklerde güvenli boş queryset dön
        if getattr(self, "swagger_fake_view", False) or not self.request or self.request.user.is_anonymous:
            return LastViewed.objects.none()
        # return last 7 viewed for current user, most recent first
        active_status = ['trial', 'active', 'lifetime', 'grace_period']
        return (
            LastViewed.objects
            .select_related("barbershop", "barbershop__subscription")
            .filter(
                user=self.request.user,
                barbershop__is_verified=True,
                barbershop__is_approved=True,  # Admin onayı - sadece onaylanmış kuaförler ana uygulamada görünür
                barbershop__name__isnull=False,
                barbershop__subscription__status__in=active_status,
            )
            .exclude(barbershop__name='')
            .order_by('-viewed_at')[:7]
        )

    def perform_create(self, serializer):
        # upsert behavior: update-or-create LastViewed and trim to last 7
        obj, created = LastViewed.objects.update_or_create(
            user=self.request.user,
            barbershop_id=self.request.data.get('barbershop'),
            defaults={}
        )
        # Tekrar görüntülemede zaman damgasını güncelle
        if not created:
            try:
                obj.viewed_at = timezone.now()
                obj.save(update_fields=["viewed_at"])
            except Exception:
                pass
        # Her giriş için ViewEvent ekleyerek toplam görüntülenmeyi arttır
        # device_id varsa onu da kaydet
        device_id = self.request.data.get('device_id')
        barbershop_id = self.request.data.get('barbershop')
        try:
            ViewEvent.objects.create(
                user=self.request.user, 
                barbershop_id=barbershop_id,
                device_id=device_id
            )
            # Check for view milestone achievements
            try:
                from app.notifications.utils import notify_shop_about_views_milestone
                views_count = ViewEvent.objects.filter(barbershop_id=barbershop_id).count()
                milestones = [100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000]
                if views_count in milestones:
                    barbershop = Barbershop.objects.get(id=barbershop_id)
                    notify_shop_about_views_milestone(barbershop, views_count)
            except Exception:
                pass
        except Exception:
            pass
        # ensure at most 7 entries
        qs = LastViewed.objects.filter(user=self.request.user).order_by('-viewed_at')
        ids = list(qs.values_list('id', flat=True))
        if len(ids) > 7:
            LastViewed.objects.filter(id__in=ids[7:]).delete()
        return


class TrackViewApi(generics.GenericAPIView):
    """
    Hem misafir hem de giriş yapmış kullanıcılar için görüntülenme takibi.
    POST /track-view/
    Body: { "barbershop": <id>, "device_id": "<uuid>" }
    
    - Giriş yapmış kullanıcı: user + device_id kaydedilir
    - Misafir kullanıcı: sadece device_id kaydedilir
    
    Tekil kullanıcı sayısı: user_id veya device_id'ye göre distinct count yapılır
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        barbershop_id = request.data.get('barbershop')
        device_id = request.data.get('device_id')
        
        if not barbershop_id:
            return Response({'error': 'barbershop is required'}, status=400)
        
        if not device_id:
            return Response({'error': 'device_id is required'}, status=400)
        
        # Barbershop var mı ve aktif mi kontrol et
        barbershop = (
            Barbershop.objects
            .select_related("subscription")
            .filter(id=barbershop_id, is_verified=True, is_approved=True, name__isnull=False)
            .exclude(name='')
            .first()
        )
        sub_status = getattr(getattr(barbershop, "subscription", None), "status", None)
        is_active_sub = sub_status in ['trial', 'active', 'lifetime', 'grace_period']
        if not barbershop or not is_active_sub:
            return Response({'error': 'barbershop not found'}, status=404)
        
        # Kullanıcı giriş yapmışsa user'ı da kaydet
        user = request.user if request.user.is_authenticated else None
        
        try:
            ViewEvent.objects.create(
                user=user,
                barbershop_id=barbershop_id,
                device_id=device_id
            )
            # Check for view milestone achievements
            try:
                from app.notifications.utils import notify_shop_about_views_milestone
                views_count = ViewEvent.objects.filter(barbershop_id=barbershop_id).count()
                milestones = [100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000]
                if views_count in milestones:
                    notify_shop_about_views_milestone(barbershop, views_count)
            except Exception:
                pass
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        
        return Response({'status': 'ok'})



class ReviewViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="my")
    def my(self, request):
        """Kullanıcının tüm yorumları (barbershop bilgisiyle)."""
        qs = self.get_queryset().select_related("barbershop")
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        review = self.get_object()
        if review.likes.filter(id=request.user.id).exists():
            review.likes.remove(request.user)
        else:
            review.likes.add(request.user)
            review.dislikes.remove(request.user)
        return Response({"detail": "Toggled like"})

    @action(detail=True, methods=["post"])
    def dislike(self, request, pk=None):
        review = self.get_object()
        if review.dislikes.filter(id=request.user.id).exists():
            review.dislikes.remove(request.user)
        else:
            review.dislikes.add(request.user)
            review.likes.remove(request.user)
        return Response({"detail": "Toggled dislike"})

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PartnerBarbershopViewSet(viewsets.ModelViewSet):
    serializer_class = BarbershopSerializer
    # Allow any authenticated user; queryset restriction + perform_create will enforce admin ownership
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Schema jenerasyonu veya anonim isteklerde güvenli boş queryset dön
        if getattr(self, "swagger_fake_view", False) or not self.request or self.request.user.is_anonymous:
            return Barbershop.objects.none()
        # Partner can manage barbershops where they have admin staff
        user = self.request.user
        return Barbershop.objects.filter(staff__user=user, staff__is_admin=True).distinct()

    # No custom permissions; queryset is already restricted to admin-owned shops
    def update(self, request, *args, **kwargs):
        # Admin kuaför ise salon bilgilerini kısmi güncelleyebilir (override)
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        # Sadece belirli alanlar güncellenebilir
        allowed = {
            # Core profile
            "name",
            "address",
            "description",
            "phone",
            "phone_number",
            "latitude",
            "longitude",
            "city",
            "district",
            "gender",
            "google_maps_link",
            # Social
            "instagram",
            "facebook",
            "twitter",
            "whatsapp",
            # Badges / features (vitrin app uses this)
            "features",
            # Hizmet süresi aralığı (10, 15, 20 dk)
            "service_duration_interval",
        }
        data = {k: v for k, v in request.data.items() if k in allowed}
        # phone alias desteği
        if "phone" in data and "phone_number" not in data:
            data["phone_number"] = data.pop("phone")
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Eğer barbershop reddedilmişse ve profil güncelleniyorsa,
        # reddetme bilgilerini temizle ve tekrar inceleme için hazırla
        if instance.rejection_reason or instance.rejected_at:
            instance.rejection_reason = None
            instance.rejected_at = None
            instance.is_verified = False  # Yeniden inceleme için
            instance.is_approved = False   # Açıkça False yap
            instance.save(update_fields=['rejection_reason', 'rejected_at', 'is_verified', 'is_approved'])
        
        return Response(serializer.data)

    @action(detail=True, methods=["patch"], url_path="status")
    def status(self, request, pk=None):
        instance = self.get_object()
        is_verified = request.data.get("is_verified")
        if is_verified is not None:
            instance.is_verified = bool(is_verified)
            instance.save(update_fields=["is_verified"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Override create to handle exceptions properly"""
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            logger.error(f"[PartnerBarbershopViewSet CREATE ERROR] {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'detail': f'Barbershop oluşturulurken hata oluştu: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_create(self, serializer):
        from .models import Staff
        from django.contrib.auth import get_user_model
        from django.db import transaction
        from django.utils import timezone
        from datetime import timedelta
        import logging
        logger = logging.getLogger(__name__)
        
        user = self.request.user
        
        try:
            with transaction.atomic():
                # Partner uygulamasından oluşturulan salonlar otomatik olarak onaylı ve doğrulanmış olarak oluşturulur
                barbershop = serializer.save(is_verified=True, is_approved=True)
                # Ensure creator is admin staff of this barbershop
                Staff.objects.get_or_create(
                    barbershop=barbershop, 
                    user=user, 
                    defaults={"email": getattr(user, 'email', ''), "is_admin": True}
                )
                
                # Otomatik olarak 3 aylık trial subscription oluştur (eğer yoksa)
                try:
                    from app.subscriptions.models import Subscription, SubscriptionPlan
                    if not Subscription.objects.filter(barbershop=barbershop).exists():
                        # Plan seçimi: system_type'a göre
                        system_type = getattr(barbershop, 'system_type', 'info')
                        if system_type == 'booking':
                            plan = SubscriptionPlan.objects.filter(slug='randevu', is_active=True).first()
                        else:
                            plan = SubscriptionPlan.objects.filter(slug='bilgi', is_active=True).first()
                        
                        if not plan:
                            plan = SubscriptionPlan.objects.filter(is_active=True).first()
                        
                        if plan:
                            subscription = Subscription.objects.create(
                                barbershop=barbershop,
                                plan=plan,
                                status='trial',
                                trial_ends_at=timezone.now() + timedelta(days=90)
                            )
                            # İlk 200 kuaför: ILK200 kuponu varsa otomatik uygula (quota doluysa otomatik atlar)
                            try:
                                from app.subscriptions.models import Coupon, CouponUsage
                                coupon = Coupon.objects.filter(code='ILK200', is_active=True).first()
                                if coupon and coupon.is_valid:
                                    subscription.coupon = coupon
                                    subscription.coupon_applied_at = timezone.now()
                                    subscription.status = 'lifetime'
                                    subscription.save(update_fields=['coupon', 'coupon_applied_at', 'status'])
                                    _, created = CouponUsage.objects.get_or_create(coupon=coupon, subscription=subscription)
                                    if created:
                                        coupon.current_uses += 1
                                        coupon.save()
                            except Exception as coupon_err:
                                logger.warning(f"[PartnerBarbershopViewSet] Coupon uygulanamadı: {str(coupon_err)}")
                except Exception as sub_err:
                    # Subscription oluşturma hatası kritik değil, sessizce geç
                    logger.warning(f"[PartnerBarbershopViewSet] Subscription oluşturulamadı: {str(sub_err)}")
        except Exception as e:
            logger.error(f"[PartnerBarbershopViewSet PERFORM_CREATE ERROR] {str(e)}")
            raise

    @action(detail=False, methods=["get"], url_path="my", permission_classes=[permissions.IsAuthenticated])
    def my_shops(self, request):
        """Kullanıcının personel olduğu (admin veya normal) tüm dükkanlar"""
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            qs = Barbershop.objects.filter(staff__user=request.user).distinct()
            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"[PartnerBarbershopViewSet.my_shops ERROR] {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {'detail': f'Dükkanlar yüklenirken hata oluştu: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["post"], url_path="appeal")
    def appeal(self, request, pk=None):
        """Reddedilen salon için itiraz gönderir; admin panelde görüntülenir ve tekrar değerlendirilir."""
        bs = self.get_object()
        if not (bs.rejection_reason or bs.rejected_at):
            return Response(
                {"detail": "Sadece reddedilmiş salonlar itiraz gönderebilir."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        message = (request.data.get("message") or "").strip()
        if not message:
            return Response(
                {"detail": "İtiraz metni (message) zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        BarbershopAppeal.objects.create(barbershop=bs, message=message, status=BarbershopAppeal.Status.PENDING)
        return Response({"detail": "İtirazınız alındı; en kısa sürede değerlendirilecektir."}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="images")
    def upload_image(self, request, pk=None):
        from .models import BarbershopImage
        bs = self.get_object()
        image = request.FILES.get('image')
        if not image:
            return Response({'detail': 'No image'}, status=400)
        BarbershopImage.objects.create(barbershop=bs, image=image)
        return Response({'detail': 'ok'})

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>[^/.]+)")
    def delete_image(self, request, pk=None, image_id=None):
        from django.shortcuts import get_object_or_404
        from .models import BarbershopImage
        bs = self.get_object()
        img = get_object_or_404(BarbershopImage, id=image_id, barbershop=bs)
        img.delete()
        return Response({'detail': 'ok'})

    @action(detail=True, methods=["post", "delete"], url_path="main-image")
    def set_main_image(self, request, pk=None):
        import traceback
        from app.core.cache_utils import invalidate_home_dashboard_cache
        try:
            bs = self.get_object()
            if request.method.lower() == "delete":
                bs.main_image = None
                bs.main_image_thumb = None
                bs.save(update_fields=["main_image", "main_image_thumb"])
                invalidate_home_dashboard_cache()
                return Response({'detail': 'ok'})
            image = request.FILES.get('image')
            if not image:
                # Debug: log what we received so partner app can fix multipart field name / Content-Type
                keys = list(request.FILES.keys()) if request.FILES else []
                import logging
                logging.getLogger(__name__).warning(
                    "set_main_image: no file under 'image'. FILES.keys=%s content_type=%s",
                    keys, getattr(request, "content_type", None),
                )
                return Response(
                    {'detail': "No image file. Send multipart form with field name 'image'."},
                    status=400,
                )
            bs.main_image = image
            # Don't use update_fields - model save() generates thumbnail which also needs to be saved
            bs.save()
            invalidate_home_dashboard_cache()
            return Response({'detail': 'ok'})
        except Exception as e:
            print(f"[set_main_image ERROR] {e}")
            traceback.print_exc()
            return Response({'detail': str(e)}, status=500)

    @action(detail=True, methods=["get"], url_path="catalog")
    def get_catalog(self, request, pk=None):
        """Partner için katalog listesi"""
        from .models import BarbershopCatalog
        from .serializers import BarbershopCatalogSerializer
        bs = self.get_object()
        items = BarbershopCatalog.objects.filter(barbershop=bs).order_by('order', 'created_at')
        serializer = BarbershopCatalogSerializer(items, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="catalog")
    def create_catalog_item(self, request, pk=None):
        """Katalog öğesi ekle"""
        from .models import BarbershopCatalog
        bs = self.get_object()
        image = request.FILES.get('image')
        if not image:
            return Response({'detail': 'No image'}, status=400)
        
        name = request.data.get('name', '').strip() or None
        description = request.data.get('description', '').strip() or None
        
        # Order: mevcut en yüksek order + 1
        from django.db.models import Max
        max_order = BarbershopCatalog.objects.filter(barbershop=bs).aggregate(
            max_order=Max('order')
        )['max_order'] or 0
        
        catalog_item = BarbershopCatalog.objects.create(
            barbershop=bs,
            image=image,
            name=name,
            description=description,
            order=max_order + 1,
        )
        from .serializers import BarbershopCatalogSerializer
        serializer = BarbershopCatalogSerializer(catalog_item, context={'request': request})
        return Response(serializer.data, status=201)

    @action(detail=True, methods=["patch"], url_path=r"catalog/(?P<catalog_id>[^/.]+)")
    def update_catalog_item(self, request, pk=None, catalog_id=None):
        """Katalog öğesi güncelle"""
        from django.shortcuts import get_object_or_404
        from .models import BarbershopCatalog
        from .serializers import BarbershopCatalogSerializer
        bs = self.get_object()
        catalog_item = get_object_or_404(BarbershopCatalog, id=catalog_id, barbershop=bs)
        
        # Görsel güncelleme
        if 'image' in request.FILES:
            catalog_item.image = request.FILES['image']
        
        # İsim ve açıklama güncelleme
        if 'name' in request.data:
            name = request.data['name'].strip() or None
            catalog_item.name = name
        if 'description' in request.data:
            description = request.data['description'].strip() or None
            catalog_item.description = description
        if 'is_active' in request.data:
            catalog_item.is_active = bool(request.data['is_active'])
        if 'order' in request.data:
            catalog_item.order = int(request.data['order'])
        
        catalog_item.save()
        serializer = BarbershopCatalogSerializer(catalog_item, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=["delete"], url_path=r"catalog/(?P<catalog_id>[^/.]+)")
    def delete_catalog_item(self, request, pk=None, catalog_id=None):
        """Katalog öğesi sil"""
        from django.shortcuts import get_object_or_404
        from .models import BarbershopCatalog
        bs = self.get_object()
        catalog_item = get_object_or_404(BarbershopCatalog, id=catalog_id, barbershop=bs)
        catalog_item.delete()
        return Response({'detail': 'ok'})

    @action(detail=True, methods=["post"], url_path="catalog/reorder")
    def reorder_catalog(self, request, pk=None):
        """Katalog öğelerini yeniden sırala"""
        from django.db import models
        from .models import BarbershopCatalog
        bs = self.get_object()
        ids = request.data.get('ids', [])
        if not isinstance(ids, list):
            return Response({'detail': 'ids must be a list'}, status=400)
        
        for order, catalog_id in enumerate(ids, start=1):
            try:
                catalog_item = BarbershopCatalog.objects.get(id=catalog_id, barbershop=bs)
                catalog_item.order = order
                catalog_item.save(update_fields=['order'])
            except BarbershopCatalog.DoesNotExist:
                continue
        
        return Response({'detail': 'ok'})


class PartnerServiceViewSetSecure(viewsets.ModelViewSet):
    serializer_class = ServiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return (
            Service.objects
            .filter(barbershop__staff__user=user, barbershop__staff__is_admin=True)
            .select_related('category')
            .distinct()
        )

    def get_object(self):
        """Avoid MultipleObjectsReturned when joins duplicate rows; fetch by PK safely."""
        from rest_framework.exceptions import NotFound, PermissionDenied
        pk = self.kwargs.get(self.lookup_field or 'pk')
        if pk is None:
            raise NotFound()
        user = self.request.user
        # Constrain to admin's shops and fetch one safely
        obj = (
            Service.objects
            .filter(id=pk, barbershop__staff__user=user, barbershop__staff__is_admin=True)
            .select_related('category')
            .order_by('id')
            .first()
        )
        if not obj:
            raise NotFound()
        return obj

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Resolve admin_staff safely
        admin_staff = Staff.objects.filter(user=request.user, is_admin=True).order_by('-id').first()
        if not admin_staff:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("No admin barbershop for this user")
        try:
            serializer.save(barbershop=admin_staff.barbershop)
        except Exception as e:
            from django.db import IntegrityError
            if isinstance(e, IntegrityError):
                return Response({"detail": "Integrity error: %s" % str(e)}, status=400)
            raise
        headers = self.get_success_headers(serializer.data)
        # Fire-and-forget message (ignore errors)
        try:
            SpecialMessage.objects.create(
                barbershop=admin_staff.barbershop,
                source='automatic', target_type='all_shop',
                title='Yeni hizmet eklendi', content=f"{serializer.instance.name}",
                start_datetime=timezone.now(), end_datetime=timezone.now() + timedelta(days=30),
                created_by=request.user, is_active=True,
            )
        except Exception:
            pass
        return Response(serializer.data, status=201, headers=headers)

    def perform_create(self, serializer):
        # Kept for compatibility if DRF calls perform_create via create()
        admin_staff = Staff.objects.filter(user=self.request.user, is_admin=True).order_by('-id').first()
        if not admin_staff:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("No admin barbershop for this user")
        serializer.save(barbershop=admin_staff.barbershop)
        # Duyuru gönderme devre dışı

    def perform_update(self, serializer):
        super().perform_update(serializer)
        # Duyuru gönderme devre dışı

    def perform_destroy(self, instance):
        name = getattr(instance, 'name', 'Hizmet')
        shop = instance.barbershop
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError
        try:
            super().perform_destroy(instance)
        except IntegrityError as e:
            raise ValidationError({"detail": f"Silme engellendi: {e}"})
        # Duyuru gönderme devre dışı

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        user = request.user
        barbershop_id = request.query_params.get('barbershop') or request.query_params.get('barbershop_id')
        if not barbershop_id:
            return Response({"detail": "barbershop parameter required"}, status=400)
        admin_staff = Staff.objects.filter(user=user, is_admin=True, barbershop_id=barbershop_id).order_by('-id').first()
        if not admin_staff:
            return Response({"detail": "No permission for this barbershop"}, status=403)
        categories = ServiceCategory.objects.filter(barbershop_id=barbershop_id).prefetch_related('services')
        result = []
        for category in categories:
            result.append({
                'id': category.id,
                'name': category.name,
                'services': ServiceSerializer(category.services.filter(is_active=True), many=True).data,
            })
        return Response(result)


class ReviewThrottle(UserRateThrottle):
    rate = "10/min"


@extend_schema(exclude=True)
class ReviewUpsertApi(generics.GenericAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ReviewThrottle]
    schema = None  # drf-spectacular: bu view'i şemadan tamamen hariç tut

    def post(self, request, barber_id):
        shop = Barbershop.objects.filter(id=barber_id).first()
        if not shop:
            return Response({"detail": "Barbershop not found"}, status=status.HTTP_404_NOT_FOUND)

        payload = {
            "rating": request.data.get("rating"),
            "comment": request.data.get("comment", ""),
            "is_anonymous": bool(request.data.get("is_anonymous", False)),
        }
        staff_id = request.data.get("staff_id")
        staff = None
        if staff_id:
            try:
                staff = Staff.objects.get(id=staff_id, barbershop=shop)
            except Staff.DoesNotExist:
                return Response({"detail": "invalid_staff_for_shop"}, status=400)
        try:
            rating = int(payload["rating"]) if payload["rating"] is not None else None
        except (TypeError, ValueError):
            rating = None
        if rating is None or rating < 1 or rating > 5:
            return Response({"rating": ["1 ile 5 arasında olmalı."]}, status=400)

        # upsert by (user, barbershop, staff)
        obj, created = Review.objects.update_or_create(
            user=request.user,
            barbershop=shop,
            staff=staff,
            defaults={
                "rating": rating,
                "comment": payload["comment"],
                "is_anonymous": payload["is_anonymous"],
            },
        )

        # Kuaför adminlerine yeni yorum bildirimi
        if created:
            try:
                notify_shop_about_new_review(obj)
            except Exception:
                # Bildirim hatası ana akışı etkilemesin
                pass

        data = ReviewSerializer(obj).data
        # snapshot meta
        shop.refresh_from_db(fields=[
            "rating_avg","total_reviews","star_1_count","star_2_count","star_3_count","star_4_count","star_5_count"
        ])
        meta = {
            "rating_avg": shop.rating_avg,
            "total_reviews": shop.total_reviews,
            "star_counts": {
                1: shop.star_1_count, 2: shop.star_2_count, 3: shop.star_3_count, 4: shop.star_4_count, 5: shop.star_5_count
            },
        }
        return Response({"review": data, "meta": meta}, status=201 if created else 200)


@extend_schema(exclude=True)
class ReviewHighlightsApi(generics.GenericAPIView):
    serializer_class = ReviewSerializer
    schema = None  # şemadan tamamen hariç
    def get(self, request, barber_id):
        shop = Barbershop.objects.filter(id=barber_id).first()
        if not shop:
            return Response({"detail": "Barbershop not found"}, status=404)
        qs = Review.objects.filter(barbershop=shop).order_by("?")
        # öncelik: yorumlu
        commented = list(qs.exclude(comment="").values_list("id", flat=True)[:50])
        pool = Review.objects.filter(id__in=commented)
        if pool.count() < 3:
            pool = Review.objects.filter(barbershop=shop).order_by("?")
        items = list(pool[:3])
        data = ReviewSerializer(items, many=True).data
        meta = {
            "rating_avg": shop.rating_avg,
            "total_reviews": shop.total_reviews,
            "star_counts": {1: shop.star_1_count, 2: shop.star_2_count, 3: shop.star_3_count, 4: shop.star_4_count, 5: shop.star_5_count},
        }
        return Response({"items": data, "meta": meta})


@extend_schema(exclude=True)
class BarbershopReviewsListApi(generics.GenericAPIView):
    """Public list endpoint for all reviews of a barbershop with pagination and filters."""
    serializer_class = ReviewSerializer
    schema = None  # şemadan tamamen hariç
    def get(self, request, barber_id):
        shop = Barbershop.objects.filter(id=barber_id).first()
        if not shop:
            return Response({"detail": "Barbershop not found"}, status=404)

        qs = Review.objects.filter(barbershop=shop).select_related("user")
        stars = request.query_params.get("stars")
        if stars and stars.isdigit():
            qs = qs.filter(rating=int(stars))
        order = request.query_params.get("order", "recent")
        if order == "random":
            qs = qs.order_by("?")
        else:
            qs = qs.order_by("-created_at")

        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 10))
        except ValueError:
            page, page_size = 1, 10
        start = (page - 1) * page_size
        end = start + page_size
        items = qs[start:end]

        serializer = ReviewSerializer(items, many=True)
        meta = {
            "total": qs.count(),
            "rating_avg": shop.rating_avg,
            "total_reviews": shop.total_reviews,
            "star_counts": {
                1: shop.star_1_count,
                2: shop.star_2_count,
                3: shop.star_3_count,
                4: shop.star_4_count,
                5: shop.star_5_count,
            },
        }
        return Response({"items": serializer.data, "meta": meta})


class PartnerStaffViewSet(viewsets.ModelViewSet):
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return Staff.objects.filter(barbershop__staff__user=user, barbershop__staff__is_admin=True).select_related("barbershop", "user")
    
    @action(detail=False, methods=['get', 'patch'], url_path='me')
    def my_profile(self, request):
        """
        Personelin kendi profilini görüntülemesi/güncellemesi.
        Her personel sadece kendi bilgilerini değiştirebilir.
        """
        try:
            # Use filter().first() to handle multiple staff records safely
            staff = Staff.objects.select_related('barbershop', 'user').filter(user=request.user).order_by('-is_admin', '-id').first()
            if not staff:
                raise Staff.DoesNotExist
        except Staff.DoesNotExist:
            return Response({"detail": "Staff profile not found"}, status=404)
        
        if request.method == 'PATCH':
            serializer = self.get_serializer(staff, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            try:
                notify_shop_staff_about_staff_change(
                    staff=staff,
                    title="Personel bilgisi güncellendi",
                    body=f"{getattr(staff.user, 'full_name', '') or staff.user.email} profil bilgilerini güncelledi.",
                    exclude_user_id=request.user.id,
                )
            except Exception:
                pass
            data = serializer.data
            data['barbershop_id'] = staff.barbershop.id  # Add barbershop ID
            return Response(data)
        else:
            serializer = self.get_serializer(staff)
            data = serializer.data
            data['barbershop_id'] = staff.barbershop.id  # Add barbershop ID
            return Response(data)

    @action(detail=False, methods=["get"], url_path="my-shops")
    def my_shops(self, request):
        qs = Staff.objects.filter(user=request.user).select_related("barbershop")
        from .serializers import BarbershopSerializer
        shops = [s.barbershop for s in qs if s.barbershop_id]
        data = BarbershopSerializer(shops, many=True).data
        return Response(data)

    @action(detail=False, methods=["post"], url_path="invite")
    def invite(self, request):
        data = InviteStaffSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data["email"]
        is_admin = data.validated_data.get("is_admin", False)
        target_barbershop_id = data.validated_data.get("barbershop")
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(email=email).first()
        if not user:
            # Kullanıcı yoksa oluştur (parola sıfırlama akışıyla değiştirebilir)
            user = User.objects.create_user(email=email, password=User.objects.make_random_password())
        # Attach to admin's chosen or first barbershop
        admin_staff_qs = Staff.objects.filter(user=request.user, is_admin=True).select_related("barbershop")
        if target_barbershop_id:
            admin_staff = admin_staff_qs.filter(barbershop_id=target_barbershop_id).first()
        else:
            admin_staff = admin_staff_qs.first()
        if not admin_staff:
            return Response({"detail": "No admin barbershop"}, status=400)
        # Aynı kullanıcı birden fazla dükkanda personel olamaz
        exists_any = Staff.objects.filter(user=user).exclude(barbershop=admin_staff.barbershop).exists()
        if exists_any:
            return Response({"detail": "User already attached to another barbershop"}, status=400)
        # Aynı dükkanda zaten varsa tekrarlama
        already = Staff.objects.filter(user=user, barbershop=admin_staff.barbershop).exists()
        if already:
            return Response({"detail": "User already a staff of this barbershop"}, status=409)
        Staff.objects.get_or_create(barbershop=admin_staff.barbershop, user=user, defaults={"email": user.email, "is_admin": is_admin})
        return Response({"detail": "Invited/attached"})

    @action(detail=False, methods=["post"], url_path="attach")
    def attach(self, request):
        data = InviteStaffSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data["email"]
        is_admin = data.validated_data.get("is_admin", False)
        target_barbershop_id = data.validated_data.get("barbershop")
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"detail": "User not found"}, status=400)
        admin_staff_qs = Staff.objects.filter(user=request.user, is_admin=True).select_related("barbershop")
        if target_barbershop_id:
            admin_staff = admin_staff_qs.filter(barbershop_id=target_barbershop_id).first()
        else:
            admin_staff = admin_staff_qs.first()
        if not admin_staff:
            return Response({"detail": "No admin barbershop"}, status=400)
        exists_any = Staff.objects.filter(user=user).exclude(barbershop=admin_staff.barbershop).exists()
        if exists_any:
            return Response({"detail": "User already attached to another barbershop"}, status=400)
        already = Staff.objects.filter(user=user, barbershop=admin_staff.barbershop).exists()
        if already:
            return Response({"detail": "User already a staff of this barbershop"}, status=409)
        staff = Staff.objects.create(barbershop=admin_staff.barbershop, user=user, email=user.email, is_admin=is_admin)
        # Otomatik duyuru: yeni personel
        try:
            display_name = getattr(user, 'full_name', '') or getattr(user, 'email', 'Yeni personel')
            SpecialMessage.objects.create(
                barbershop=admin_staff.barbershop,
                source='automatic', target_type='all_shop',
                title='Yeni personel aramıza katıldı', content=f"{display_name} takımımıza katıldı. Hoş geldin!",
                start_datetime=timezone.now(), end_datetime=timezone.now() + timedelta(days=30),
                created_by=self.request.user, is_active=True,
            )
        except Exception:
            pass
        return Response(StaffSerializer(staff).data, status=201)


class PartnerWorkScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = WorkScheduleSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return WorkSchedule.objects.filter(staff__barbershop__staff__user=user, staff__barbershop__staff__is_admin=True).select_related("staff")

    @action(detail=False, methods=["post"], url_path="set-hours")
    def set_hours(self, request):
        staff_id = request.data.get("staff_id")
        hours = request.data.get("hours", [])
        try:
            staff = Staff.objects.get(id=staff_id, barbershop__staff__user=request.user, barbershop__staff__is_admin=True)
        except Staff.DoesNotExist:
            return Response({"detail": "Staff not found or no permission"}, status=404)
        WorkSchedule.objects.filter(staff=staff).delete()
        serializer = StaffHoursSerializer(data=hours, many=True)
        serializer.is_valid(raise_exception=True)
        for h in serializer.validated_data:
            WorkSchedule.objects.create(staff=staff, **h)
        try:
            staff_name = getattr(staff.user, "full_name", "") or staff.user.email or "Personel"
            notify_shop_staff_about_staff_change(
                staff=staff,
                title="Çalışma saatleri güncellendi",
                body=f"{staff_name} için çalışma saatleri yetkili personel tarafından güncellendi.",
                exclude_user_id=request.user.id,
            )
        except Exception:
            pass
        return Response({"detail": "Updated"})



class FavoriteListView(generics.ListAPIView):
    serializer_class = BarbershopWithFavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]
    # Ham liste dön; mobil uygulama tek sayfa bekliyor ve kendi içinde filtreleme yapıyor.
    pagination_class = None

    def get_queryset(self):
        # Schema jenerasyonu veya anonim isteklerde güvenli boş queryset dön
        if getattr(self, "swagger_fake_view", False) or not self.request or self.request.user.is_anonymous:
            return Barbershop.objects.none()
        return (
            Barbershop.objects.filter(
                favorited_by__user=self.request.user,
                name__isnull=False,  # İsimsiz kuaförleri filtrele
                is_verified=True,  # Banlı kuaförleri filtrele
                is_approved=True,  # Admin onayı - sadece onaylanmış kuaförler ana uygulamada görünür
                subscription__status__in=['trial', 'active', 'lifetime', 'grace_period']  # Aktif aboneliği olanları göster
            )
            .exclude(name='')  # Boş string isimleri de filtrele
            .order_by("-favorited_by__created_at")
        )

    def list(self, request, *args, **kwargs):
        """
        Favoriler listesini dönerken her kayıt için açık/kapalı bilgisini de ekle.
        Ana sayfadaki 'Favorilerim' bölümünün En Son Bakılanlar ile tutarlı şekilde
        'Açık' / 'Kapalı' etiketi göstermesi için _compute_shop_status kullanılır.
        Yeni liste döndürülür ki JSON çıktısında is_open kesin yer alsın.
        """
        response = super().list(request, *args, **kwargs)
        data = response.data
        if not isinstance(data, list):
            return response
        now_ts = timezone.now()
        out = []
        for item in data:
            row = dict(item)
            try:
                shop_id = row.get("id")
                if shop_id is not None:
                    status_data = _compute_shop_status(int(shop_id), now_ts)
                    row["is_open"] = status_data.get("status") == "open"
                else:
                    row["is_open"] = False
            except Exception:
                row["is_open"] = False
            out.append(row)
        return Response(out)


@extend_schema(exclude=True)
class FavoriteToggleView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    schema = None  # Şemadan tamamen hariç; serializer'a ihtiyaç yok
    
    def post(self, request, barbershop_id):
        try:
            barbershop = Barbershop.objects.get(id=barbershop_id)
        except Barbershop.DoesNotExist:
            return Response({"error": "Barbershop not found"}, status=404)
        
        # Banlı veya pasif abonelikli kuaförler için favori işlemini engelle
        sub_status = getattr(getattr(barbershop, "subscription", None), "status", None)
        is_active_sub = sub_status in ['trial', 'active', 'lifetime', 'grace_period']
        if not barbershop.is_verified or not is_active_sub:
            return Response({"error": "Barbershop not available"}, status=404)
        
        favorite, created = Favorite.objects.get_or_create(
            user=request.user,
            barbershop=barbershop
        )
        
        if not created:
            favorite.delete()
            favorited = False
        else:
            favorited = True
        
        # Update favorites_count
        favorites_count = barbershop.favorited_by.count()
        barbershop.favorites_count = favorites_count
        barbershop.save(update_fields=["favorites_count"])
        
        # Check for milestone achievements (only when adding favorite)
        if favorited:
            from app.notifications.utils import notify_shop_about_favorites_milestone
            milestones = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
            for milestone in milestones:
                if favorites_count == milestone:
                    try:
                        notify_shop_about_favorites_milestone(barbershop, milestone)
                    except Exception:
                        pass
                    break
        
        return Response({"favorited": favorited, "favorites_count": favorites_count})


class PartnerServiceCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return (
            ServiceCategory.objects
            .filter(barbershop__staff__user=user, barbershop__staff__is_admin=True)
            .order_by('position','id')
            .distinct()
        )

    def perform_create(self, serializer):
        admin_staff = Staff.objects.filter(user=self.request.user, is_admin=True).order_by('-id').first()
        if not admin_staff:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("No admin barbershop for this user")
        serializer.save(barbershop=admin_staff.barbershop)
        # Otomatik duyuru devre dışı

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError
        try:
            self.perform_destroy(instance)
        except IntegrityError:
            raise ValidationError({"detail": "Silme engellendi: bu kategoriye bağlı hizmetler var"})
        return Response(status=204)

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        ids = request.data if isinstance(request.data, list) else request.data.get('ids')
        if not isinstance(ids, list) or not ids:
            return Response({"detail": "ids list required"}, status=400)
        admin_staff = Staff.objects.filter(user=request.user, is_admin=True).order_by('-id').first()
        if not admin_staff:
            return Response({"detail": "No admin barbershop"}, status=403)
        qs = ServiceCategory.objects.filter(barbershop=admin_staff.barbershop, id__in=ids)
        pos_map = {int(cid): i for i, cid in enumerate(ids)}
        updated = 0
        for c in qs:
            new_pos = pos_map.get(int(c.id))
            if new_pos is not None and c.position != new_pos:
                c.position = new_pos
                c.save(update_fields=["position"])
                updated += 1
        return Response({"detail": "ok", "updated": updated})


class PartnerServiceViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return (
            Service.objects
            .filter(barbershop__staff__user=user, barbershop__staff__is_admin=True)
            .select_related('category')
            .distinct()
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin_staff = Staff.objects.filter(user=request.user, is_admin=True).order_by('-id').first()
        if not admin_staff:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("No admin barbershop for this user")
        shop = admin_staff.barbershop
        # Unisex: target_gender zorunlu (male/female/both). Erkek/kadın: otomatik.
        if getattr(shop, "gender", None) == "male":
            serializer.validated_data["target_gender"] = "male"
        elif getattr(shop, "gender", None) == "female":
            serializer.validated_data["target_gender"] = "female"
        else:
            tg = serializer.validated_data.get("target_gender") or (request.data.get("target_gender") if isinstance(request.data, dict) else None)
            if tg not in ("male", "female", "both"):
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"target_gender": ["Unisex kuaförde Kadın, Erkek veya Kadın ve Erkek seçilmelidir."]})
            serializer.validated_data["target_gender"] = tg
        try:
            serializer.save(barbershop=shop)
        except Exception as e:
            from django.db import IntegrityError
            if isinstance(e, IntegrityError):
                return Response({"detail": str(e)}, status=400)
            raise
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)

    def perform_update(self, serializer):
        instance = serializer.instance
        shop = instance.barbershop
        if getattr(shop, "gender", None) == "male":
            serializer.validated_data["target_gender"] = "male"
        elif getattr(shop, "gender", None) == "female":
            serializer.validated_data["target_gender"] = "female"
        else:
            tg = serializer.validated_data.get("target_gender") or (self.request.data.get("target_gender") if isinstance(self.request.data, dict) else None)
            if tg not in ("male", "female", "both"):
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"target_gender": ["Unisex kuaförde Kadın, Erkek veya Kadın ve Erkek seçilmelidir."]})
            serializer.validated_data["target_gender"] = tg
        super().perform_update(serializer)
        # Otomatik duyuru devre dışı

    def perform_destroy(self, instance):
        name = getattr(instance, 'name', 'Hizmet')
        shop = instance.barbershop
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError
        try:
            super().perform_destroy(instance)
        except IntegrityError as e:
            raise ValidationError({"detail": f"Silme engellendi: {e}"})
        # Duyuru gönderme devre dışı

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        """Kategoriler ve altındaki hizmetleri ağaç yapısında döndür"""
        user = request.user
        barbershop_id = request.query_params.get('barbershop') or request.query_params.get('barbershop_id')
        
        if not barbershop_id:
            return Response({"detail": "barbershop parameter required"}, status=400)
        
        # Admin staff'ın barbershop'ını kontrol et
        admin_staff = Staff.objects.filter(user=user, is_admin=True, barbershop_id=barbershop_id).order_by('-id').first()
        if not admin_staff:
            return Response({"detail": "No permission for this barbershop"}, status=403)
        
        categories = ServiceCategory.objects.filter(barbershop_id=barbershop_id).prefetch_related('services')
        result = []
        
        for category in categories:
            category_data = {
                'id': category.id,
                'name': category.name,
                'services': ServiceSerializer(category.services.filter(is_active=True), many=True).data
            }
            result.append(category_data)
        
        return Response(result)


class ReviewReplyViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewReplySerializer
    permission_classes = [permissions.IsAuthenticated, IsReplyOwnerOrShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return ReviewReply.objects.filter(review__barbershop__staff__user=user, review__barbershop__staff__is_admin=True)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="reply-to-review")
    def reply_to_review(self, request):
        """Bir review'a cevap ver"""
        review_id = request.data.get('review_id')
        text = request.data.get('text')
        
        if not review_id or not text:
            return Response({"detail": "review_id and text required"}, status=400)
        
        try:
            review = Review.objects.get(id=review_id)
        except Review.DoesNotExist:
            return Response({"detail": "Review not found"}, status=404)
        
        # Admin staff'ın bu barbershop'ta yetkisi var mı kontrol et
        try:
            admin_staff = Staff.objects.filter(user=request.user, is_admin=True, barbershop=review.barbershop).order_by('-id').first()
            if not admin_staff:
                return Response({"detail": "No permission to reply to this review"}, status=403)
        except Staff.DoesNotExist:
            return Response({"detail": "No permission to reply to this review"}, status=403)
        
        # Zaten cevap vermiş mi kontrol et
        if ReviewReply.objects.filter(review=review, user=request.user).exists():
            return Response({"detail": "Already replied to this review"}, status=400)
        
        reply = ReviewReply.objects.create(review=review, user=request.user, text=text)
        return Response(ReviewReplySerializer(reply).data, status=201)


class PartnerReviewViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        try:
            # Find the barbershop where the current user is an admin
            admin_staff = Staff.objects.filter(user=self.request.user, is_admin=True).order_by('-id').first()
            if admin_staff:
                return Review.objects.filter(barbershop=admin_staff.barbershop).select_related('user', 'barbershop').order_by('-created_at')
        except:
            pass
        return Review.objects.none()

    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        review = self.get_object()
        text = request.data.get('reply')
        if not text:
            return Response({'detail': 'Yanıt metni gerekli'}, status=400)
        
        # Create or update reply
        ReviewReply.objects.update_or_create(
            review=review,
            user=request.user,
            defaults={'text': text}
        )
        # Also update review replied_at
        review.replied_at = timezone.now()
        review.save()

        # Müşteriye bildirim: yoruma cevap verildi
        try:
            notify_customer_about_reply(review)
        except Exception:
            # Bildirim hatası ana akışı bozmasın
            pass
        
        # Refresh review to include reply
        return Response(ReviewSerializer(review).data)


# Takvim ve Mesaj Yönetimi ViewSet'leri
class PartnerShopWorkingHoursViewSet(viewsets.ModelViewSet):
    serializer_class = ShopWorkingHoursSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]
    pagination_class = None  # Vitrin uygulaması 7 günlük listeyi tek seferde bekliyor

    def get_queryset(self):
        user = self.request.user
        return ShopWorkingHours.objects.filter(barbershop__staff__user=user, barbershop__staff__is_admin=True).distinct()

    def create(self, request, *args, **kwargs):
        """Force-inject barbershop and create directly to avoid 400/500."""
        try:
            admin_staff = Staff.objects.filter(user=request.user, is_admin=True).order_by('-id').first()
            if not admin_staff:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Admin yetkisi gerekli")
        except Staff.DoesNotExist:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Admin yetkisi gerekli")

        # Debug: Log the request data
        print(f"DEBUG: Request data: {request.data}")
        print(f"DEBUG: Admin staff barbershop: {admin_staff.barbershop.id}")

        # Create/update directly without serializer validation issues
        try:
            # Standard logic here
            return super().create(request, *args, **kwargs)
        except Exception as e:
            # Fallback for safety
            print(f"Standard create failed: {e}")
            raise

    @action(detail=False, methods=["post"], url_path="update-schedule")
    def update_schedule(self, request):
        from datetime import datetime, time as _time
        from django.db import transaction
        from rest_framework import serializers as drf_serializers

        schedule_data = request.data.get("schedule", [])
        effective_date_str = request.data.get("effective_date")
        barbershop_id = request.data.get("barbershop")

        try:
            admin_qs = Staff.objects.filter(user=request.user, is_admin=True).order_by('-id')
            if barbershop_id is not None:
                try:
                    bid = int(barbershop_id)
                    admin_qs = admin_qs.filter(barbershop_id=bid)
                except (TypeError, ValueError):
                    pass
            admin_staff = admin_qs.first()
            if not admin_staff:
                return Response({"detail": "Admin yetkisi gerekli veya bu dükkan için yetkiniz yok"}, status=403)
            shop = admin_staff.barbershop
        except Staff.DoesNotExist:
            return Response({"detail": "Admin yetkisi gerekli"}, status=403)

        if not isinstance(schedule_data, list) or not schedule_data:
            return Response({"detail": "Schedule data required"}, status=400)

        valid_days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        valid_set = set(valid_days)

        def _parse_time(val):
            if val is None:
                return None
            s = str(val).strip()
            if not s:
                return None
            # Accept "HH:MM" or "HH:MM:SS" (and tolerate longer strings)
            try:
                return datetime.strptime(s[:5], "%H:%M").time()
            except Exception:
                try:
                    return datetime.strptime(s[:8], "%H:%M:%S").time()
                except Exception:
                    return None

        # Build a dict to de-dup days; also tolerate old keys ("day", "open", "close", etc.)
        incoming_by_day = {}
        for raw in schedule_data:
            if not isinstance(raw, dict):
                continue
            day = (raw.get("day_of_week") or raw.get("day") or "").upper()
            if day in valid_set:
                incoming_by_day[day] = raw

        # Normalize to a full 7-day schedule to avoid partial payload issues
        normalized_schedule = []
        normalized_objs = []

        for day in valid_days:
            raw = incoming_by_day.get(day)
            if not raw:
                # Missing day: treat as closed (safe default)
                normalized_schedule.append(
                    {
                        "day_of_week": day,
                        "is_closed": True,
                        "start_time": "00:00:00",
                        "end_time": "00:00:00",
                        "break_start_time": None,
                        "break_end_time": None,
                    }
                )
                normalized_objs.append(
                    ShopWorkingHours(
                        barbershop=shop,
                        day_of_week=day,
                        is_closed=True,
                        start_time=_time(0, 0),
                        end_time=_time(0, 0),
                        break_start_time=None,
                        break_end_time=None,
                    )
                )
                continue

            is_closed = bool(raw.get("is_closed", False))
            break_start = _parse_time(raw.get("break_start") or raw.get("break_start_time"))
            break_end = _parse_time(raw.get("break_end") or raw.get("break_end_time"))

            if is_closed:
                normalized_schedule.append(
                    {
                        "day_of_week": day,
                        "is_closed": True,
                        "start_time": "00:00:00",
                        "end_time": "00:00:00",
                        "break_start_time": None,
                        "break_end_time": None,
                    }
                )
                normalized_objs.append(
                    ShopWorkingHours(
                        barbershop=shop,
                        day_of_week=day,
                        is_closed=True,
                        start_time=_time(0, 0),
                        end_time=_time(0, 0),
                        break_start_time=None,
                        break_end_time=None,
                    )
                )
                continue

            start_raw = raw.get("start_time") or raw.get("open")
            end_raw = raw.get("end_time") or raw.get("close")
            start_t = _parse_time(start_raw)
            end_t = _parse_time(end_raw)
            if not start_t or not end_t:
                raise drf_serializers.ValidationError({"detail": f"{day} için açılış/kapanış saati gerekli"})
            if end_t <= start_t:
                raise drf_serializers.ValidationError({"detail": f"{day} için kapanış saati açılıştan sonra olmalı"})

            b_start_raw = raw.get("break_start_time") or raw.get("break_start")
            b_end_raw = raw.get("break_end_time") or raw.get("break_end")
            b_start_t = _parse_time(b_start_raw)
            b_end_t = _parse_time(b_end_raw)
            if (b_start_t and not b_end_t) or (b_end_t and not b_start_t):
                raise drf_serializers.ValidationError({"detail": f"{day} için mola başlangıç ve bitiş birlikte gönderilmeli"})
            if b_start_t and b_end_t:
                if b_end_t <= b_start_t:
                    raise drf_serializers.ValidationError({"detail": f"{day} için mola bitişi başlangıçtan sonra olmalı"})
                if b_start_t < start_t or b_end_t > end_t:
                    raise drf_serializers.ValidationError({"detail": f"{day} için mola saatleri çalışma saatleri içinde olmalı"})

            normalized_schedule.append(
                {
                    "day_of_week": day,
                    "is_closed": False,
                    "start_time": start_t.strftime("%H:%M:%S"),
                    "end_time": end_t.strftime("%H:%M:%S"),
                    "break_start_time": b_start_t.strftime("%H:%M:%S") if b_start_t else None,
                    "break_end_time": b_end_t.strftime("%H:%M:%S") if b_end_t else None,
                }
            )
            normalized_objs.append(
                ShopWorkingHours(
                    barbershop=shop,
                    day_of_week=day,
                    is_closed=False,
                    start_time=start_t,
                    end_time=end_t,
                    break_start_time=b_start_t,
                    break_end_time=b_end_t,
                )
            )

        schedule_data = normalized_schedule

        effective_date = timezone.now().date()
        if effective_date_str:
            try:
                effective_date = datetime.strptime(effective_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        
        today = timezone.now().date()
        is_future = effective_date > today

        if is_future:
            ScheduleChangeRequest.objects.create(
                target_type=ScheduleChangeRequest.TargetType.SHOP,
                target_id=shop.id,
                new_schedule_json=schedule_data,
                effective_date=effective_date,
                applied=False
            )
            count = check_and_cancel_conflicts(shop, schedule_data, effective_date)
            try:
                notify_shop_staff_about_shop_schedule_change(
                    barbershop=shop,
                    title="Salon çalışma saatleri güncellendi",
                    body=f"Salon çalışma saatleri {effective_date} tarihi için planlandı.",
                    exclude_user_id=request.user.id,
                )
            except Exception:
                pass
            return Response({"detail": f"Değişiklikler {effective_date} tarihine planlandı. {count} çakışan randevu iptal edildi."})
        else:
            # Apply immediately
            with transaction.atomic():
                ShopWorkingHours.objects.filter(barbershop=shop).delete()
                # Bulk create is faster and avoids serializer time parsing edge-cases (400'leri bitirir)
                ShopWorkingHours.objects.bulk_create(normalized_objs)
                
                count = check_and_cancel_conflicts(shop, schedule_data, today)
            # Cache bust: shop_status kullanıldığı için güncel saatler hemen yansısın
            try:
                from django.core.cache import cache
                for i in range(8):
                    d = today + timedelta(days=-3 + i)
                    cache.delete(f"shop_status:{shop.id}:{d.strftime('%Y-%m-%d')}")
            except Exception:
                pass
            try:
                notify_shop_staff_about_shop_schedule_change(
                    barbershop=shop,
                    title="Salon çalışma saatleri güncellendi",
                    body="Salon çalışma saatleri yetkili personel tarafından güncellendi.",
                    exclude_user_id=request.user.id,
                )
            except Exception:
                pass
            return Response({"detail": f"Çalışma saatleri güncellendi. {count} çakışan randevu iptal edildi."})

    def perform_create(self, serializer):
        try:
            admin_staff = Staff.objects.filter(user=self.request.user, is_admin=True).order_by('-id').first()
            if not admin_staff:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Admin yetkisi gerekli")
        except Staff.DoesNotExist:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Admin yetkisi gerekli")
        
        serializer.save(barbershop=admin_staff.barbershop)
        self._log_action('create', 'ShopWorkingHours', serializer.instance.id, serializer.validated_data)
        # Duyuru gönderme devre dışı

    def perform_update(self, serializer):
        old_data = ShopWorkingHoursSerializer(serializer.instance).data
        super().perform_update(serializer)
        self._log_action('update', 'ShopWorkingHours', serializer.instance.id, {
            'old': old_data,
            'new': serializer.validated_data
        })
        # Duyuru gönderme devre dışı

    def perform_destroy(self, instance):
        old_data = ShopWorkingHoursSerializer(instance).data
        self._log_action('delete', 'ShopWorkingHours', instance.id, old_data)
        super().perform_destroy(instance)
        # Duyuru gönderme devre dışı

    def _log_action(self, action_type, target_model, target_id, changes):
        try:
            admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
            CalendarAuditLog.objects.create(
                barbershop=admin_staff.barbershop,
                user=self.request.user,
                action_type=action_type,
                target_model=target_model,
                target_id=target_id,
                changes=_jsonable(changes)
            )
        except Staff.DoesNotExist:
            pass


class PartnerStaffWorkingHoursViewSet(viewsets.ModelViewSet):
    serializer_class = StaffWorkingHoursSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]

    def get_queryset(self):
        user = self.request.user
        # Politika: Hem admin hem personel SADECE kendi staff kaydı için saatleri yönetebilir
        my_staff = Staff.objects.filter(user=user).first()
        return StaffWorkingHours.objects.filter(staff=my_staff)

    @action(detail=False, methods=["get"], url_path="planned-change")
    def planned_change(self, request):
        """
        Gelecekte başlayacak planlanmış personel çalışma saati değişikliğini döndürür.
        valid_from > bugünün olan ilk blok planlanmış değişiklik kabul edilir.
        """
        staff = Staff.objects.filter(user=request.user).order_by("-is_admin", "-id").first()
        if not staff:
            return Response({"has_planned_change": False})

        today = timezone.now().date()
        future_hours = StaffWorkingHours.objects.filter(staff=staff, valid_from__gt=today)
        if not future_hours.exists():
            return Response({"has_planned_change": False})

        effective_date = future_hours.order_by("valid_from").first().valid_from
        future_for_date = future_hours.filter(valid_from=effective_date)

        valid_days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        week = []
        for day in valid_days:
            sh = future_for_date.filter(day_of_week=day).first()
            if sh:
                week.append(
                    {
                        "day": day,
                        "is_closed": bool(getattr(sh, "is_closed", False)),
                        "open": getattr(sh, "start_time", None) and sh.start_time.strftime("%H:%M"),
                        "close": getattr(sh, "end_time", None) and sh.end_time.strftime("%H:%M"),
                    }
                )
            else:
                week.append({"day": day, "is_closed": True, "open": None, "close": None})

        return Response(
            {
                "has_planned_change": True,
                "effective_date": effective_date.strftime("%Y-%m-%d"),
                "week": week,
            }
        )

    @action(detail=False, methods=["post"], url_path="cancel-planned-change")
    def cancel_planned_change(self, request):
        """
        Gelecekteki planlanmış personel çalışma saati değişikliğini iptal eder.
        Eski saatlerin valid_until değerini tekrar sonsuza çeker ve gelecek kayıtları siler.
        """
        from django.db import transaction

        staff = Staff.objects.filter(user=request.user).order_by("-is_admin", "-id").first()
        if not staff:
            return Response({"detail": "Staff not found"}, status=404)

        today = timezone.now().date()
        future_hours = StaffWorkingHours.objects.filter(staff=staff, valid_from__gt=today)
        if not future_hours.exists():
            return Response({"detail": "Planlanmış bir değişiklik bulunamadı."}, status=400)

        effective_date = future_hours.order_by("valid_from").first().valid_from
        yesterday = effective_date - timedelta(days=1)

        with transaction.atomic():
            # Eski segmentleri tekrar sonsuza kadar geçerli yap
            StaffWorkingHours.objects.filter(
                staff=staff,
                valid_until=yesterday,
            ).update(valid_until=None)

            # Gelecek saatleri sil
            StaffWorkingHours.objects.filter(staff=staff, valid_from__gte=effective_date).delete()

        return Response({"detail": "Planlanmış değişiklik iptal edildi."})

    @action(detail=False, methods=["post"], url_path="check-impact")
    def check_impact(self, request):
        """
        Check impact of schedule changes for 3 scenarios:
        1. Immediate (Today)
        2. Next Week (Next Monday)
        3. Two Weeks (Monday after next)
        """
        from app.appointments.models import Appointment, AppointmentStatus
        
        schedule_data = request.data.get("week", [])
        if not schedule_data:
            return Response({"detail": "Week data required"}, status=400)

        staff = Staff.objects.filter(user=request.user).order_by('-is_admin', '-id').first()
        if not staff:
            return Response({"detail": "Staff not found"}, status=404)

        today = timezone.now().date()
        
        # Calculate effective dates
        # 1. Immediate: Today
        date_now = today
        
        # 2. Next Week: Next Monday
        days_ahead = 7 - today.weekday() # 0=Mon, 6=Sun.
        if days_ahead == 0: days_ahead = 7 
        date_next_week = today + timedelta(days=days_ahead)
        
        # 3. Two Weeks: Monday after next
        date_two_weeks = date_next_week + timedelta(days=7)

        scenarios = [
            {"key": "now", "label": "Hemen Uygula", "date": date_now},
            {"key": "1_week", "label": "Gelecek Hafta Başı", "date": date_next_week},
            {"key": "2_weeks", "label": "2 Hafta Sonra", "date": date_two_weeks},
        ]

        results = {}
        
        def parse_time(s):
            if not s: return None
            try:
                return datetime.strptime(str(s)[:5], "%H:%M").time()
            except:
                return None

        new_schedule = {}
        for item in schedule_data:
            day_code = item.get('day')
            if day_code:
                new_schedule[day_code] = {
                    'is_closed': item.get('is_closed', False),
                    'open': parse_time(item.get('open')),
                    'close': parse_time(item.get('close'))
                }

        weekday_map = {0: 'MON', 1: 'TUE', 2: 'WED', 3: 'THU', 4: 'FRI', 5: 'SAT', 6: 'SUN'}

        for scen in scenarios:
            eff_date = scen["date"]
            qs = Appointment.objects.filter(
                staff=staff,
                start_datetime__date__gte=eff_date,
                status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]
            )
            
            conflict_count = 0
            
            for appt in qs:
                appt_date = appt.start_datetime.date()
                appt_day_code = weekday_map[appt_date.weekday()]
                day_rules = new_schedule.get(appt_day_code)
                
                if not day_rules or day_rules['is_closed']:
                    conflict_count += 1
                    continue
                
                open_t = day_rules['open']
                close_t = day_rules['close']
                
                if not open_t or not close_t:
                    conflict_count += 1
                    continue
                
                appt_start = appt.start_datetime.time()
                appt_end = appt.end_datetime.time()
                
                if appt_start < open_t or appt_end > close_t:
                    conflict_count += 1
            
            results[scen["key"]] = {
                "date": eff_date.strftime("%Y-%m-%d"),
                "conflict_count": conflict_count
            }

        return Response(results)

    @action(detail=False, methods=["post"], url_path="update-schedule-v2")
    def update_schedule_v2(self, request):
        from app.appointments.models import Appointment, AppointmentStatus, CancelledBy
        from app.appointments.services import events
        from django.db import transaction

        schedule_data = request.data.get("week", [])
        apply_option = request.data.get("apply_option", "now") # now, 1_week, 2_weeks
        cancel_message = request.data.get("cancellation_message", "")

        staff = Staff.objects.filter(user=request.user).order_by('-is_admin', '-id').first()
        if not staff:
            return Response({"detail": "Staff not found"}, status=404)

        today = timezone.now().date()
        
        if apply_option == '1_week':
            days_ahead = 7 - today.weekday()
            if days_ahead == 0: days_ahead = 7
            effective_date = today + timedelta(days=days_ahead)
        elif apply_option == '2_weeks':
            days_ahead = 7 - today.weekday()
            if days_ahead == 0: days_ahead = 7
            effective_date = today + timedelta(days=days_ahead + 7)
        else: # now
            effective_date = today

        def parse_time(s):
            if not s: return None
            try:
                return datetime.strptime(str(s)[:5], "%H:%M").time()
            except:
                return None

        with transaction.atomic():
            # 1. Versioning Logic: Terminate overlapping current hours
            current_active = StaffWorkingHours.objects.filter(
                staff=staff,
                valid_from__lt=effective_date
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=effective_date)
            )
            
            yesterday = effective_date - timedelta(days=1)
            
            for swh in current_active:
                swh.valid_until = yesterday
                swh.save()
            
            # Delete future hours that are fully replaced
            StaffWorkingHours.objects.filter(
                staff=staff,
                valid_from__gte=effective_date
            ).delete()
            
            # 2. Create New Hours
            for item in schedule_data:
                day = item.get('day')
                if not day: continue
                is_closed = item.get('is_closed', False)
                open_t = parse_time(item.get('open'))
                close_t = parse_time(item.get('close'))
                break_start_t = parse_time(item.get('break_start_time') or item.get('break_start'))
                break_end_t = parse_time(item.get('break_end_time') or item.get('break_end'))
                
                StaffWorkingHours.objects.create(
                    staff=staff,
                    day_of_week=day,
                    is_closed=is_closed,
                    start_time=open_t,
                    end_time=close_t,
                    break_start_time=break_start_t,
                    break_end_time=break_end_t,
                    valid_from=effective_date,
                    valid_until=None
                )
            
            # 3. Cancel Conflicts
            qs = Appointment.objects.filter(
                staff=staff,
                start_datetime__date__gte=effective_date,
                status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]
            )
            
            new_schedule_map = {item.get('day'): item for item in schedule_data}
            weekday_map = {0: 'MON', 1: 'TUE', 2: 'WED', 3: 'THU', 4: 'FRI', 5: 'SAT', 6: 'SUN'}
            
            cancelled_count = 0
            for appt in qs:
                appt_date = appt.start_datetime.date()
                appt_day_code = weekday_map[appt_date.weekday()]
                day_rules = new_schedule_map.get(appt_day_code)
                
                should_cancel = False
                if not day_rules or day_rules.get('is_closed'):
                    should_cancel = True
                else:
                    open_t = parse_time(day_rules.get('open'))
                    close_t = parse_time(day_rules.get('close'))
                    if not open_t or not close_t:
                         should_cancel = True
                    else:
                        if appt.start_datetime.time() < open_t or appt.end_datetime.time() > close_t:
                            should_cancel = True
                
                if should_cancel:
                    appt.status = AppointmentStatus.CANCELLED
                    appt.rejection_reason = f"Çalışma saati değişikliği: {cancel_message}"
                    appt.cancelled_by = CancelledBy.SYSTEM
                    appt.save()
                    cancelled_count += 1

                    # Bildirim olayı oluştur
                    try:
                        events.emit(
                            events.staff_topic(appt.staff_id),
                            {
                                "type": "appointment_cancelled_by_schedule_change",
                                "id": appt.id,
                                "reason": appt.rejection_reason,
                            },
                        )
                        events.emit(
                            events.shop_topic(appt.shop_id),
                            {
                                "type": "appointment_cancelled_by_schedule_change",
                                "id": appt.id,
                                "reason": appt.rejection_reason,
                            },
                        )
                    except Exception:
                        # Bildirim tarafındaki bir hata, randevu iptal akışını bozmamalı
                        pass

            try:
                staff_name = getattr(staff.user, "full_name", "") or staff.user.email or "Personel"
                notify_shop_staff_about_staff_change(
                    staff=staff,
                    title="Çalışma saatleri güncellendi",
                    body=f"{staff_name} kendi çalışma saatlerini güncelledi (geçerlilik: {effective_date}).",
                    exclude_user_id=request.user.id,
                )
            except Exception:
                pass

        return Response({
            "detail": "Changes saved",
            "effective_date": effective_date,
            "cancelled_count": cancelled_count
        })


    @action(detail=False, methods=["get", "put"], url_path="weekly")
    def weekly(self, request):
        """GET: Personelin haftalık saatlerini (shop inherit ile) döndür.
        PUT: Personelin haftalık saatlerini ayarla; inherits_shop_hours=true ise personel kayıtlarını sil.
        """
        # Get staff from logged-in user
        # Use filter().first() to handle multiple staff records safely
        staff = Staff.objects.filter(user=request.user).order_by('-is_admin', '-id').first()
        if not staff:
            return Response({"detail": "Staff profile not found"}, status=404)

        valid_days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

        if request.method == "GET":
            try:
                result = []
                inherits = True
                for day in valid_days:
                    shop = ShopWorkingHours.objects.filter(barbershop=staff.barbershop, day_of_week=day).first()
                    sh = StaffWorkingHours.objects.filter(staff=staff, day_of_week=day).first()
                    if sh:
                        inherits = False
                        result.append({
                            "day": day,
                            "is_closed": bool(getattr(sh, 'is_closed', False)),
                            "open": getattr(sh, 'start_time', None) and sh.start_time.strftime("%H:%M"),
                            "close": getattr(sh, 'end_time', None) and sh.end_time.strftime("%H:%M"),
                            "break_start": getattr(sh, 'break_start_time', None) and sh.break_start_time.strftime("%H:%M"),
                            "break_end": getattr(sh, 'break_end_time', None) and sh.break_end_time.strftime("%H:%M"),
                            "source": "staff",
                        })
                    else:
                        # Shop saatleri olmayabilir; güvenli fallback
                        result.append({
                            "day": day,
                            "is_closed": bool(getattr(shop, 'is_closed', False)) if shop else True,
                            "open": (shop.start_time.strftime("%H:%M") if getattr(shop, 'start_time', None) else None),
                            "close": (shop.end_time.strftime("%H:%M") if getattr(shop, 'end_time', None) else None),
                            "break_start": (shop.break_start_time.strftime("%H:%M") if getattr(shop, 'break_start_time', None) else None),
                            "break_end": (shop.break_end_time.strftime("%H:%M") if getattr(shop, 'break_end_time', None) else None),
                            "source": "shop" if shop else "default",
                        })
                return Response({"staff_id": staff.id, "inherits_shop_hours": inherits, "week": result})
            except Exception:
                # Hiçbir şeyi patlatma; tamamını kapalı default dön
                safe = [{"day": d, "is_closed": True, "open": None, "close": None, "source": "default"} for d in valid_days]
                return Response({"staff_id": staff.id, "inherits_shop_hours": True, "week": safe})

        # PUT
        # Dio/Flutter bazı durumlarda JSON'ı string olarak gönderebilir; güvenle parse et
        data = request.data
        if isinstance(data, (str, bytes)):
            try:
                import json
                data = json.loads(data)
            except Exception:
                data = {}

        inherits_shop_hours = bool((data or {}).get("inherits_shop_hours", False))
        week = (data or {}).get("week") or []
        if inherits_shop_hours:
            StaffWorkingHours.objects.filter(staff=staff).delete()
            return Response({"detail": "Inherited from shop"})

        def parse_hhmm(s: str):
            try:
                hh, mm = str(s).split(":"); return timezone.datetime(2000,1,1,int(hh),int(mm)).time()
            except Exception:
                return None

        errors = {}
        normalized = []
        if not isinstance(week, list) or len(week) != 7:
            return Response({"detail": "invalid_payload", "errors": {"week": "7 items required"}}, status=400)
        for item in week:
            day = (item.get("day") or "").upper()
            if day not in valid_days:
                errors[day or "?"] = "invalid_day"; continue
            is_closed = bool(item.get("is_closed", False))
            if is_closed:
                normalized.append({"day": day, "is_closed": True, "open": None, "close": None}); continue
            st = parse_hhmm(item.get("open")); et = parse_hhmm(item.get("close"))
            if not st or not et:
                errors[day] = "invalid_time"; continue
            break_start = parse_hhmm(item.get("break_start") or item.get("break_start_time"))
            break_end = parse_hhmm(item.get("break_end") or item.get("break_end_time"))
            normalized.append({
                "day": day, 
                "is_closed": False, 
                "open": st, 
                "close": et,
                "break_start": break_start,
                "break_end": break_end,
            })
        if errors:
            return Response({"detail": "invalid_payload", "errors": errors}, status=400)

        # Conflict validation: personel saatleri dükkan saatleri içinde olmalı (dükkan saati varsa)
        # Dükkan o gün kapalıysa veya dükkan saati yoksa personel yine de kendi saatini girebilir
        conflict_errors = {}
        for it in normalized:
            if it["is_closed"]:
                continue
            shop_hours = ShopWorkingHours.objects.filter(barbershop=staff.barbershop, day_of_week=it["day"]).first()
            if not shop_hours or shop_hours.is_closed:
                continue
            sh_start = shop_hours.start_time
            sh_end = shop_hours.end_time
            if sh_start and sh_end:
                if it["open"] < sh_start:
                    conflict_errors[it["day"]] = {
                        "code": "open_before_shop",
                        "message": f"Açılış dükkan açılışından ({sh_start.strftime('%H:%M')}) önce olamaz.",
                    }
                elif it["close"] > sh_end:
                    conflict_errors[it["day"]] = {
                        "code": "close_after_shop",
                        "message": f"Kapanış dükkan kapanışından ({sh_end.strftime('%H:%M')}) sonra olamaz.",
                    }
        if conflict_errors:
            return Response({"detail": "conflict", "errors": conflict_errors}, status=400)

        StaffWorkingHours.objects.filter(staff=staff).delete()
        for it in normalized:
            StaffWorkingHours.objects.create(
                staff=staff,
                day_of_week=it["day"],
                is_closed=it["is_closed"],
                start_time=it["open"],
                end_time=it["close"],
                break_start_time=it.get("break_start"),
                break_end_time=it.get("break_end"),
            )
        return Response({"detail": "Updated"})

    def perform_create(self, serializer):
        user = self.request.user
        staff = serializer.validated_data['staff']
        # RBAC: Yalnızca kendi staff saatlerini düzenleyebilir (admin dahi olsa)
        if staff.user != user:
            raise drf_serializers.ValidationError("Yetkisiz işlem: sadece kendi saatlerinizi düzenleyebilirsiniz")
        serializer.save()
        self._log_action('create', 'StaffWorkingHours', serializer.instance.id, serializer.validated_data)
        # Duyuru gönderme devre dışı

    def perform_update(self, serializer):
        old = StaffWorkingHoursSerializer(serializer.instance).data
        super().perform_update(serializer)
        self._log_action('update', 'StaffWorkingHours', serializer.instance.id, {
            'old': old,
            'new': StaffWorkingHoursSerializer(serializer.instance).data
        })
        # Duyuru gönderme devre dışı

    def perform_destroy(self, instance):
        old = StaffWorkingHoursSerializer(instance).data
        self._log_action('delete', 'StaffWorkingHours', instance.id, old)
        super().perform_destroy(instance)
        # Otomatik duyuru devre dışı

    def _log_action(self, action_type, target_model, target_id, changes):
        try:
            admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
            CalendarAuditLog.objects.create(
                barbershop=admin_staff.barbershop,
                user=self.request.user,
                action_type=action_type,
                target_model=target_model,
                target_id=target_id,
                changes=_jsonable(changes)
            )
        except Staff.DoesNotExist:
            pass


class PartnerBreakWindowViewSet(viewsets.ModelViewSet):
    serializer_class = BreakWindowSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def get_queryset(self):
        # Schema jenerasyonu veya anonim kullanıcıda güvenli boş queryset
        if getattr(self, "swagger_fake_view", False) or not self.request or self.request.user.is_anonymous:
            return BreakWindow.objects.none()
        user = self.request.user
        admin_shop_ids = self._admin_shop_ids()
        base_qs = BreakWindow.objects.select_related("barbershop", "staff__user", "created_by")
        if admin_shop_ids:
            qs = base_qs.filter(barbershop_id__in=admin_shop_ids)
        else:
            staff_ids = list(Staff.objects.filter(user=user).values_list("id", flat=True))
            if not staff_ids:
                return base_qs.none()
            qs = base_qs.filter(staff_id__in=staff_ids)

        params = self.request.query_params
        barbershop_id = params.get("barbershop_id")
        if barbershop_id:
            qs = qs.filter(barbershop_id=barbershop_id)
        staff_id = params.get("staff_id")
        if staff_id:
            qs = qs.filter(staff_id=staff_id)
        scope = params.get("scope")
        if scope in (BreakWindow.Scope.SHOP, BreakWindow.Scope.STAFF):
            qs = qs.filter(scope=scope)
        date_str = params.get("date")
        if date_str:
            qs = qs.filter(date=date_str)
        else:
            date_from = params.get("date_from")
            date_to = params.get("date_to")
            if date_from:
                qs = qs.filter(date__gte=date_from)
            if date_to:
                qs = qs.filter(date__lte=date_to)
        return qs.order_by("date", "start_time")

    def perform_create(self, serializer):
        # Tarih sınırlaması: bugün ve 7 gün sonrası dahil
        from django.utils import timezone
        today = timezone.now().date()
        date_val = serializer.validated_data.get("date")
        if date_val:
            max_day = today + timezone.timedelta(days=7)
            if date_val < today or date_val > max_day:
                raise drf_serializers.ValidationError({"date": "Mola tarihi sadece bugünden itibaren 7 gün içinde olabilir"})

        scope = serializer.validated_data.get("scope")
        target_barbershop = (
            serializer.validated_data.get("barbershop")
            or getattr(serializer.validated_data.get("staff"), "barbershop", None)
        )
        if not target_barbershop:
            raise drf_serializers.ValidationError({"barbershop": "Dükkan zorunlu"})

        if scope == BreakWindow.Scope.SHOP:
            if not self._is_admin_for(target_barbershop.id):
                raise drf_serializers.ValidationError({"detail": "Dükkan molası eklemek için admin olmalısınız"})
            serializer.save(created_by=self.request.user)
            return

        staff = serializer.validated_data.get("staff")
        if staff:
            if staff.user_id != self.request.user.id and not self._is_admin_for(staff.barbershop_id):
                raise drf_serializers.ValidationError({"detail": "Bu personel için yetkiniz yok"})
        else:
            staff = (
                Staff.objects.filter(user=self.request.user, barbershop=target_barbershop)
                .order_by("-is_admin", "-id")
                .first()
            )
            if not staff:
                raise drf_serializers.ValidationError({"staff": "Personel profili bulunamadı"})
        serializer.save(staff=staff, barbershop=staff.barbershop, created_by=self.request.user)

    def perform_update(self, serializer):
        from django.utils import timezone
        date_val = serializer.validated_data.get("date", serializer.instance.date)
        today = timezone.now().date()
        max_day = today + timezone.timedelta(days=7)
        if date_val < today or date_val > max_day:
            raise drf_serializers.ValidationError({"date": "Mola tarihi sadece bugünden itibaren 7 gün içinde olabilir"})

        instance = serializer.instance
        if not self._can_manage(instance):
            raise drf_serializers.ValidationError({"detail": "Bu molayı güncelleme yetkiniz yok"})
        scope = serializer.validated_data.get("scope", instance.scope)
        if scope == BreakWindow.Scope.SHOP and not self._is_admin_for(instance.barbershop_id):
            raise drf_serializers.ValidationError({"detail": "Dükkan molası güncellemek için admin olmalısınız"})
        serializer.save()

    def perform_destroy(self, instance):
        if not self._can_manage(instance):
            raise drf_serializers.ValidationError({"detail": "Bu molayı silme yetkiniz yok"})
        instance.delete()

    def _admin_shop_ids(self) -> List[int]:
        if not hasattr(self, "_cached_admin_ids"):
            self._cached_admin_ids = list(
                Staff.objects.filter(user=self.request.user, is_admin=True).values_list("barbershop_id", flat=True)
            )
        return self._cached_admin_ids

    def _is_admin_for(self, barbershop_id: int) -> bool:
        return barbershop_id in self._admin_shop_ids()

    def _can_manage(self, instance: BreakWindow) -> bool:
        if self._is_admin_for(instance.barbershop_id):
            return True
        return bool(instance.staff and instance.staff.user_id == self.request.user.id)


class PartnerOverrideViewSet(viewsets.ModelViewSet):
    serializer_class = OverrideSerializer
    # Personel kendi özel gününü oluşturabilsin; dükkan genel override için RBAC aşağıda kontrol ediliyor
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Liste ham dizi dönsün (vitrin + ana uygulama uyumluluğu)

    def get_queryset(self):
        user = self.request.user
        # Politika: Shop-level override'lar (admin) + kendi personel override'ları
        my_staff = Staff.objects.filter(user=user).first()
        shop_ids = list(Staff.objects.filter(user=user, is_admin=True).values_list('barbershop_id', flat=True))
        
        qs = Override.objects.filter(
            (Q(staff=my_staff) | Q(barbershop_id__in=shop_ids, override_type='shop_global'))
        )
        
        # Scope parametresi ile filtreleme (shop/staff)
        scope = self.request.query_params.get('scope', '').lower()
        if scope == 'shop' or scope == 'global':
            # Sadece salon izin günleri
            qs = qs.filter(override_type='shop_global')
        elif scope == 'staff' or scope == 'personel':
            # Sadece personel izin günleri
            qs = qs.filter(override_type='staff_individual', staff=my_staff)
        
        return qs.order_by('-start_date', '-created_at')

    def perform_create(self, serializer):
        from datetime import datetime, time, timedelta
        from django.utils import timezone as dj_tz
        from app.appointments.models import Appointment, AppointmentStatus
        
        # RBAC: admin olabilir ya da normal personel
        user = self.request.user
        admin_staff = Staff.objects.filter(user=user, is_admin=True).first()
        my_staff = Staff.objects.filter(user=user).first()

        payload = dict(self.request.data)
        # Yeni API sözleşmesini destekle: scope (shop/staff) + override_type (closed/open/change/break)
        scope_in = (payload.get('scope') or '').lower() if isinstance(payload.get('scope'), str) else ''
        kind_in = (payload.get('override_type') or '').lower() if isinstance(payload.get('override_type'), str) else ''

        mapped_type = None
        mapped_scope = None
        if scope_in in ('shop', 'global'):
            mapped_type = 'shop_global'
        elif scope_in in ('staff', 'personel'):
            mapped_type = 'staff_individual'

        if kind_in in ('closed', 'kapali', 'full_day_closed'):
            mapped_scope = 'full_day_closed'
        elif kind_in in ('break', 'mola', 'time_range_closed'):
            mapped_scope = 'time_range_closed'
        elif kind_in in ('early_closing', 'early'):
            mapped_scope = 'early_closing'
        elif kind_in in ('late_opening', 'late'):
            mapped_scope = 'late_opening'

        # serializer.validated_data içindeki alanları override etmeye çalış
        if mapped_type and 'override_type' in serializer.fields:
            serializer.validated_data['override_type'] = mapped_type
        if mapped_scope and 'override_scope' in serializer.fields:
            serializer.validated_data['override_scope'] = mapped_scope

        # Eğer personel kapsamı seçilmiş ama staff verilmemişse, isteği yapan kullanıcının staff kaydını ata
        if (serializer.validated_data.get('override_type') or mapped_type) == 'staff_individual' and not serializer.validated_data.get('staff'):
            serializer.validated_data['staff'] = my_staff

        # RBAC: admin değilse shop_global yasak; admin olsa bile staff_individual sadece kendi adına
        effective_type = serializer.validated_data.get('override_type') or mapped_type
        if not Staff.objects.filter(user=user, is_admin=True).exists() and effective_type == 'shop_global':
            raise drf_serializers.ValidationError("Yetkisiz işlem: dükkan genel override oluşturma yetkiniz yok")
        if effective_type == 'staff_individual' and serializer.validated_data.get('staff') and serializer.validated_data['staff'].user != user:
            raise drf_serializers.ValidationError("Yalnızca kendi adınıza personel override oluşturabilirsiniz")

        # Çoklu tarih desteği: dates[] verilirse her gün için ayrı override oluştur
        base_shop = admin_staff.barbershop if admin_staff else (my_staff.barbershop if my_staff else None)
        if not base_shop:
            raise drf_serializers.ValidationError({"detail": "Barbershop bulunamadı"})
        
        dates = self.request.data.get('dates')
        created = []
        today = dj_tz.localdate()
        
        if isinstance(dates, list) and dates:
            # Tür bazlı doğrulama
            scope = serializer.validated_data.get('override_scope') or mapped_scope
            st = serializer.validated_data.get('start_time')
            et = serializer.validated_data.get('end_time')
            # overnight yasak (tek gün kuralı)
            if st and et and st >= et:
                raise drf_serializers.ValidationError("Saat aralığı geçersiz")
            if scope == 'full_day_closed' and (st or et):
                raise drf_serializers.ValidationError("Tam gün kapalı için saat girilmemelidir")
            if scope == 'time_range_closed' and (not st or not et):
                raise drf_serializers.ValidationError("Saat aralığı kapalı için başlangıç ve bitiş saatleri zorunludur")
            if scope == 'early_closing' and not et:
                raise drf_serializers.ValidationError("Erken kapanış için bitiş saati zorunludur")
            if scope == 'late_opening' and not st:
                raise drf_serializers.ValidationError("Geç açılış için başlangıç saati zorunludur")
            
            # Validasyonlar ve randevu kontrolü
            weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
            appointment_conflicts = []
            
            for d in dates:
                # Geçmiş ve bugün yasak
                if d <= today:
                    raise drf_serializers.ValidationError("Geçmiş ve bugün seçilemez")
                
                # Duplicate kontrol: Daha önce izin eklenmiş güne izin eklenemez
                if effective_type == 'shop_global':
                    existing = Override.objects.filter(
                        barbershop=base_shop,
                        start_date__lte=d,
                        end_date__gte=d,
                        override_type='shop_global',
                        override_scope='full_day_closed'
                    ).exists()
                    if existing:
                        raise drf_serializers.ValidationError({"detail": "Bu tarih zaten izin günü olarak işaretlenmiş."})
                else:
                    staff_obj = serializer.validated_data.get('staff')
                    if staff_obj:
                        existing = Override.objects.filter(
                            staff=staff_obj,
                            start_date__lte=d,
                            end_date__gte=d,
                            override_type='staff_individual',
                            override_scope='full_day_closed'
                        ).exists()
                        if existing:
                            raise drf_serializers.ValidationError({"detail": "Bu tarih zaten izin günü olarak işaretlenmiş."})
                
                # Salon kapalı günü kontrolü
                day_code = weekday_code_map.get(d.weekday())
                shop_wh = ShopWorkingHours.objects.filter(barbershop=base_shop, day_of_week=day_code).first()
                shop_daily_closed = DailyOverride.objects.filter(barbershop=base_shop, date=d, status='closed').exists()
                shop_global_full = Override.objects.filter(
                    barbershop=base_shop,
                    override_type='shop_global',
                    start_date__lte=d,
                    end_date__gte=d,
                    override_scope='full_day_closed'
                ).exists()
                
                # Personel için: Salon kapalı gününe veya kendi çalışmadığı güne izin eklenemez
                if effective_type == 'staff_individual':
                    if shop_daily_closed or shop_global_full or (shop_wh and shop_wh.is_closed):
                        raise drf_serializers.ValidationError({"detail": "Dükkan kapalı gününde personel izin günü eklenemez"})
                    
                    staff_obj = serializer.validated_data.get('staff')
                    if staff_obj:
                        staff_wh = StaffWorkingHours.objects.filter(staff=staff_obj, day_of_week=day_code).first()
                        if not staff_wh or staff_wh.is_closed:
                            raise drf_serializers.ValidationError({"detail": "Personel o gün çalışmıyor, izin günü eklenemez"})
                
                # Yetkili personel için: Salon kapalı gününe salon izin günü eklenemez
                if effective_type == 'shop_global':
                    if shop_daily_closed or (shop_wh and shop_wh.is_closed):
                        raise drf_serializers.ValidationError({"detail": "Salon zaten kapalı günü, izin günü eklenemez"})
                
                # Randevu kontrolü: Sadece system_type == 'booking' ise
                if scope == 'full_day_closed' and base_shop.system_type == 'booking':
                    if effective_type == 'shop_global':
                        conflicts = Appointment.objects.filter(
                            shop=base_shop,
                            start_datetime__date=d,
                            status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED, AppointmentStatus.SUGGESTED]
                        ).count()
                    else:
                        staff_obj = serializer.validated_data.get('staff')
                        if staff_obj:
                            conflicts = Appointment.objects.filter(
                                shop=base_shop,
                                staff=staff_obj,
                                start_datetime__date=d,
                                status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED, AppointmentStatus.SUGGESTED]
                            ).count()
                        else:
                            conflicts = 0
                    
                    if conflicts > 0:
                        appointment_conflicts.append((d, conflicts))
                
                # Saat aralığı doğrulama (yalnız time_range_closed)
                if scope == 'time_range_closed':
                    if st >= et:
                        raise drf_serializers.ValidationError({"detail": "Saat aralığı geçersiz"})
                    if effective_type == 'shop_global':
                        open_interval, _ = _effective_shop_hours_with_breaks(base_shop, d)
                        if not open_interval or not open_interval[0] or not open_interval[1]:
                            raise drf_serializers.ValidationError({"detail": "O gün dükkan kapalı"})
                        if not (open_interval[0] <= st and et <= open_interval[1]):
                            raise drf_serializers.ValidationError({"detail": "Saat, açık saatlerin dışında seçilemez"})
                    else:
                        staff_obj = serializer.validated_data.get('staff')
                        if staff_obj:
                            swh = StaffWorkingHours.objects.filter(staff=staff_obj, day_of_week=day_code, is_closed=False).first()
                            if swh and swh.start_time and swh.end_time:
                                if not (swh.start_time <= st and et <= swh.end_time):
                                    raise drf_serializers.ValidationError({"detail": "Saat, personel açık saatlerinin dışında seçilemez"})
                            else:
                                open_interval, _ = _effective_shop_hours_with_breaks(base_shop, d)
                                if not open_interval or not open_interval[0] or not open_interval[1]:
                                    raise drf_serializers.ValidationError({"detail": "O gün dükkan kapalı"})
                                if not (open_interval[0] <= st and et <= open_interval[1]):
                                    raise drf_serializers.ValidationError({"detail": "Saat, açık saatlerin dışında seçilemez"})
            
            # Randevu çakışması varsa uyarı ver (ama engelleme)
            if appointment_conflicts and base_shop.system_type == 'booking':
                total_conflicts = sum(c for _, c in appointment_conflicts)
                # Uyarı mesajı response'a eklenebilir, ama override oluşturulur
            
            # Tek tek create (is_active=True: ana uygulamada seçilen günde salon/personel kapalı görünsün)
            for d in dates:
                obj = Override.objects.create(
                    barbershop=base_shop,
                    staff=serializer.validated_data.get('staff'),
                    override_type=effective_type,
                    override_scope=scope,
                    start_date=d,
                    end_date=d,
                    start_time=st,
                    end_time=et,
                    is_recurring=False,
                    recurring_rule='',
                    reason=serializer.validated_data.get('reason',''),
                    is_active=True,
                    created_by=self.request.user,
                )
                created.append(obj)
            serializer.instance = created[-1]
        else:
            # Tek tarih (mevcut davranış)
            d = serializer.validated_data.get('start_date')
            if not d:
                raise drf_serializers.ValidationError({"detail": "start_date zorunludur"})
            # Geçmiş ve bugün yasak
            if d <= today:
                raise drf_serializers.ValidationError({"detail": "Geçmiş ve bugün seçilemez"})
            
            weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
            day_code = weekday_code_map.get(d.weekday())
            
            # Duplicate kontrol
            if effective_type == 'shop_global':
                existing = Override.objects.filter(
                    barbershop=base_shop,
                    start_date__lte=d,
                    end_date__gte=d,
                    override_type='shop_global',
                    override_scope='full_day_closed'
                ).exists()
                if existing:
                    raise drf_serializers.ValidationError({"detail": "Bu tarih zaten izin günü olarak işaretlenmiş."})
            else:
                staff_obj = serializer.validated_data.get('staff')
                if staff_obj:
                    existing = Override.objects.filter(
                        staff=staff_obj,
                        start_date__lte=d,
                        end_date__gte=d,
                        override_type='staff_individual',
                        override_scope='full_day_closed'
                    ).exists()
                    if existing:
                        raise drf_serializers.ValidationError({"detail": "Bu tarih zaten izin günü olarak işaretlenmiş."})
            
            # Salon kapalı günü kontrolü
            shop_wh = ShopWorkingHours.objects.filter(barbershop=base_shop, day_of_week=day_code).first()
            shop_daily_closed = DailyOverride.objects.filter(barbershop=base_shop, date=d, status='closed').exists()
            shop_global_full = Override.objects.filter(
                barbershop=base_shop,
                override_type='shop_global',
                start_date__lte=d,
                end_date__gte=d,
                override_scope='full_day_closed'
            ).exists()
            
            # Personel için: Salon kapalı gününe veya kendi çalışmadığı güne izin eklenemez
            if effective_type == 'staff_individual':
                if shop_daily_closed or shop_global_full or (shop_wh and shop_wh.is_closed):
                    raise drf_serializers.ValidationError({"detail": "Dükkan kapalı gününde personel izin günü eklenemez"})
                
                staff_obj = serializer.validated_data.get('staff')
                if staff_obj:
                    staff_wh = StaffWorkingHours.objects.filter(staff=staff_obj, day_of_week=day_code).first()
                    if not staff_wh or staff_wh.is_closed:
                        raise drf_serializers.ValidationError({"detail": "Personel o gün çalışmıyor, izin günü eklenemez"})
            
            # Yetkili personel için: Salon kapalı gününe salon izin günü eklenemez
            if effective_type == 'shop_global':
                if shop_daily_closed or (shop_wh and shop_wh.is_closed):
                    raise drf_serializers.ValidationError({"detail": "Salon zaten kapalı günü, izin günü eklenemez"})
            
            # Randevu kontrolü: Sadece system_type == 'booking' ise
            scope = serializer.validated_data.get('override_scope') or mapped_scope
            appointment_count = 0
            if scope == 'full_day_closed' and base_shop.system_type == 'booking':
                if effective_type == 'shop_global':
                    appointment_count = Appointment.objects.filter(
                        shop=base_shop,
                        start_datetime__date=d,
                        status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED, AppointmentStatus.SUGGESTED]
                    ).count()
                else:
                    staff_obj = serializer.validated_data.get('staff')
                    if staff_obj:
                        appointment_count = Appointment.objects.filter(
                            shop=base_shop,
                            staff=staff_obj,
                            start_datetime__date=d,
                            status__in=[AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED, AppointmentStatus.SUGGESTED]
                        ).count()
            
            # Saat aralığı doğrulama
            st = serializer.validated_data.get('start_time')
            et = serializer.validated_data.get('end_time')
            if scope == 'time_range_closed':
                if not st or not et or st >= et:
                    raise drf_serializers.ValidationError({"detail": "Saat aralığı geçersiz"})
                if effective_type == 'shop_global':
                    open_interval, _ = _effective_shop_hours_with_breaks(base_shop, d)
                    if not open_interval or not open_interval[0] or not open_interval[1]:
                        raise drf_serializers.ValidationError({"detail": "O gün dükkan kapalı"})
                    if not (open_interval[0] <= st and et <= open_interval[1]):
                        raise drf_serializers.ValidationError({"detail": "Saat, açık saatlerin dışında seçilemez"})
                else:
                    staff_obj = serializer.validated_data.get('staff')
                    if staff_obj:
                        swh = StaffWorkingHours.objects.filter(staff=staff_obj, day_of_week=day_code, is_closed=False).first()
                        if swh and swh.start_time and swh.end_time:
                            if not (swh.start_time <= st and et <= swh.end_time):
                                raise drf_serializers.ValidationError({"detail": "Saat, personel açık saatlerinin dışında seçilemez"})
                        else:
                            open_interval, _ = _effective_shop_hours_with_breaks(base_shop, d)
                            if not open_interval or not open_interval[0] or not open_interval[1]:
                                raise drf_serializers.ValidationError({"detail": "O gün dükkan kapalı"})
                            if not (open_interval[0] <= st and et <= open_interval[1]):
                                raise drf_serializers.ValidationError({"detail": "Saat, açık saatlerin dışında seçilemez"})
            
            serializer.validated_data['is_active'] = True
            serializer.save(barbershop=base_shop, created_by=self.request.user)
            # Merge same-day overlapping ranges
            if scope == 'time_range_closed':
                sib_qs = Override.objects.filter(
                    barbershop=base_shop,
                    staff=serializer.instance.staff,
                    override_type=serializer.instance.override_type,
                    override_scope=scope,
                    start_date=d
                ).order_by('start_time')
                if sib_qs.count() > 1:
                    times = [(o.start_time, o.end_time) for o in sib_qs if o.start_time and o.end_time]
                    if times:
                        min_st = min(t[0] for t in times)
                        max_et = max(t[1] for t in times)
                        keep = sib_qs.first()
                        sib_qs.exclude(id=keep.id).delete()
                        keep.start_time = min_st
                        keep.end_time = max_et
                        keep.save(update_fields=['start_time','end_time'])
            created.append(serializer.instance)
        
        self._log_action('create', 'Override', serializer.instance.id, serializer.validated_data)

        # Otomatik duyuru oluşturma: 1 hafta önce + izin gününde
        try:
            from app.notifications.models import Notification
            from app.barbers.models import SpecialMessage
            
            for ov in created:
                # Sadece full_day_closed için duyuru oluştur
                if ov.override_scope != 'full_day_closed':
                    continue
                
                leave_date = ov.start_date
                reason = (ov.reason or '').strip()
                
                # Başlık ve içerik
                if ov.staff_id:
                    staff = ov.staff
                    staff_name = f"{getattr(staff.user, 'first_name', '')} {getattr(staff.user, 'last_name', '')}".strip() or staff.user.email
                    title_1_week = f"{leave_date.strftime('%d.%m.%Y')} tarihinde {staff_name} izinli olacaktır."
                    title_today = f"Bugün {staff_name} izinli."
                    target_type = 'specific_staff'
                    
                    # Personel için bildirim
                    Notification.objects.create(
                        user=staff.user,
                        title="İzin Günü Eklendi",
                        body=f"{leave_date.strftime('%d.%m.%Y')} tarihinde izinlisiniz. {reason}",
                        type='system',
                        reference_id=f"override_{ov.id}"
                    )
                else:
                    title_1_week = f"{leave_date.strftime('%d.%m.%Y')} tarihinde salon kapalı olacaktır."
                    title_today = "Bugün salon kapalıdır."
                    target_type = 'all_shop'
                    
                    # Tüm personellere bildirim
                    for staff_member in Staff.objects.filter(barbershop=ov.barbershop):
                        Notification.objects.create(
                            user=staff_member.user,
                            title="Salon İzin Günü",
                            body=f"{leave_date.strftime('%d.%m.%Y')} tarihinde salon kapalı olacaktır. {reason}",
                            type='system',
                            reference_id=f"override_{ov.id}"
                        )
                
                # Duyuru 1: 1 hafta önce (7 gün önce 00:00 - izin günü 00:00)
                announcement_1_start = dj_tz.make_aware(datetime.combine(leave_date - timedelta(days=7), time(0, 0)))
                announcement_1_end = dj_tz.make_aware(datetime.combine(leave_date, time(0, 0)))
                
                SpecialMessage.objects.create(
                    barbershop=ov.barbershop,
                    source='automatic',
                    display_type='banner',
                    target_type=target_type,
                    title=title_1_week,
                    content=reason,
                    start_datetime=announcement_1_start,
                    end_datetime=announcement_1_end,
                    priority=1,
                    created_by=self.request.user,
                    is_active=False,  # 1 hafta önce aktif olacak
                )
                
                # Duyuru 2: İzin gününde (izin günü 00:00 - izin günü + 1 gün 00:00)
                announcement_2_start = dj_tz.make_aware(datetime.combine(leave_date, time(0, 0)))
                announcement_2_end = dj_tz.make_aware(datetime.combine(leave_date + timedelta(days=1), time(0, 0)))
                
                msg2 = SpecialMessage.objects.create(
                    barbershop=ov.barbershop,
                    source='automatic',
                    display_type='banner',
                    target_type=target_type,
                    title=title_today,
                    content=reason,
                    start_datetime=announcement_2_start,
                    end_datetime=announcement_2_end,
                    priority=2,
                    created_by=self.request.user,
                    is_active=False,  # İzin gününde aktif olacak
                )
                
                if target_type == 'specific_staff' and ov.staff_id:
                    # Her iki duyuruyu da personel ile ilişkilendir
                    for msg in SpecialMessage.objects.filter(
                        barbershop=ov.barbershop,
                        source='automatic',
                        start_datetime__date__in=[announcement_1_start.date(), leave_date]
                    ).order_by('-created_at')[:2]:
                        msg.target_staff.set([ov.staff_id])
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Override oluşturulurken duyuru/bildirim hatası: {e}", exc_info=True)

    def create(self, request, *args, **kwargs):
        try:
            # Pre-map legacy client payload before validation
            raw = request.data
            try:
                payload = dict(raw)
            except Exception:
                payload = {**raw}
            scope_in = str(payload.get('scope') or '').lower()
            kind_in = str(payload.get('override_type') or '').lower()
            # Accept single date as start/end
            if (not payload.get('start_date')) and payload.get('date'):
                payload['start_date'] = payload['date']
            if (not payload.get('end_date')) and payload.get('date'):
                payload['end_date'] = payload['date']
            # Map human-friendly fields to model fields
            if scope_in in ('shop', 'global'):
                payload['override_type'] = 'shop_global'
            elif scope_in in ('staff', 'personel'):
                payload['override_type'] = 'staff_individual'
            # override_scope
            if kind_in in ('closed', 'kapali', 'full_day_closed'):
                payload['override_scope'] = 'full_day_closed'
            elif kind_in in ('break', 'mola', 'time_range_closed'):
                payload['override_scope'] = 'time_range_closed'
            elif kind_in in ('early_closing', 'early'):
                payload['override_scope'] = 'early_closing'
            elif kind_in in ('late_opening', 'late'):
                payload['override_scope'] = 'late_opening'
            # If staff scope but no staff provided, default to current user's staff id
            if payload.get('override_type') == 'staff_individual' and not payload.get('staff'):
                my_staff = Staff.objects.filter(user=request.user).first()
                if my_staff:
                    payload['staff'] = my_staff.id

            serializer = self.get_serializer(data=payload)
            if not serializer.is_valid():
                # İlk hattaki doğrulama hataları
                msg = next(iter(serializer.errors.values()))
                return Response({'ok': False, 'error': {'code': 'validation_error', 'message': str(msg)}})
            # perform_create içi ileri doğrulamalar raise edebilir
            self.perform_create(serializer)
            # Cancel overlapping appointments if needed (sadece system_type == 'booking' ise)
            try:
                from datetime import datetime
                from django.utils import timezone as dj_tz
                from app.appointments.models import Appointment
                from app.appointments.models import AppointmentStatus, CancelledBy
                
                # Sadece booking sistemi kullanıyorsa randevu iptal et
                ov = serializer.instance
                if ov.barbershop.system_type != 'booking':
                    # Booking sistemi kullanılmıyorsa randevu iptal etme
                    pass
                else:
                    day = ov.start_date
                    start_time = ov.start_time
                    end_time = ov.end_time
                    # Determine filtering scope
                    base_qs = Appointment.objects.filter(
                        shop=ov.barbershop, start_datetime__date=day
                    ).exclude(status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW])
                    if ov.override_type == 'staff_individual' and ov.staff_id:
                        base_qs = base_qs.filter(staff_id=ov.staff_id)
                    # Compute offending appointments
                    cancel_qs = base_qs
                    if ov.override_scope == 'time_range_closed' and start_time and end_time:
                        sdt = dj_tz.make_aware(datetime.combine(day, start_time))
                        edt = dj_tz.make_aware(datetime.combine(day, end_time))
                        cancel_qs = cancel_qs.filter(end_datetime__gt=sdt, start_datetime__lt=edt)
                    elif ov.override_scope == 'early_closing' and end_time:
                        edt = dj_tz.make_aware(datetime.combine(day, end_time))
                        cancel_qs = cancel_qs.filter(start_datetime__lt=edt, end_datetime__gt=edt)
                    elif ov.override_scope == 'late_opening' and start_time:
                        sdt = dj_tz.make_aware(datetime.combine(day, start_time))
                        cancel_qs = cancel_qs.filter(start_datetime__lt=sdt)
                    # full_day_closed: keep cancel_qs as base_qs
                    # Randevuları iptal et
                    cancelled_count = cancel_qs.update(
                        status=AppointmentStatus.CANCELLED,
                        cancelled_by=CancelledBy.SYSTEM
                    )
                    # Müşterilere bildirim gönder
                    if cancelled_count > 0:
                        from app.notifications.services import create_user_notification
                        for ap in Appointment.objects.filter(
                            shop=ov.barbershop,
                            start_datetime__date=day,
                            status=AppointmentStatus.CANCELLED,
                            cancelled_by=CancelledBy.SYSTEM
                        ).filter(id__in=[a.id for a in cancel_qs]):
                            if ap.customer_id:
                                reason_text = ov.reason or "İzin günü nedeniyle"
                                create_user_notification(
                                    user=ap.customer,
                                    type_="booking",
                                    reference_id=str(ap.id),
                                    title="Randevunuz iptal edildi",
                                    body=f"{ov.barbershop.name} {ap.start_datetime:%d.%m.%Y %H:%M} randevunuz {reason_text} nedeniyle iptal edilmiştir.",
                                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Randevu iptal hatası: {e}", exc_info=True)
            return Response({'ok': True, 'data': self.get_serializer(serializer.instance).data})
        except drf_serializers.ValidationError as e:
            detail = getattr(e, 'detail', None)
            message = ''
            if isinstance(detail, dict):
                # İlk mesajı çek
                try:
                    message = next(iter(detail.values()))
                except Exception:
                    message = str(detail)
            else:
                message = str(e)
            return Response({'ok': False, 'error': {'code': 'validation_error', 'message': str(message)}})
        except Exception as e:
            return Response({'ok': False, 'error': {'code': 'unknown', 'message': str(e)}})

    def perform_destroy(self, instance):
        """İzin günü silme - sadece gelecekteki tarihler silinebilir"""
        from django.utils import timezone
        from app.barbers.models import SpecialMessage
        from app.notifications.models import Notification
        import drf_serializers
        
        today = timezone.localdate()
        
        # Geçmiş veya bugünkü izin günleri silinemez
        if instance.start_date <= today:
            raise drf_serializers.ValidationError({"detail": "Geçmiş veya bugünkü izin günleri silinemez"})
        
        # İlgili SpecialMessage'ı da sil (eğer varsa)
        SpecialMessage.objects.filter(
            barbershop=instance.barbershop,
            source='automatic',
            start_datetime__date=instance.start_date
        ).delete()
        
        # İlgili bildirimleri iptal et (eğer varsa)
        Notification.objects.filter(
            type='system',
            reference_id=f"override_{instance.id}"
        ).delete()
        
        self._log_action('delete', 'Override', instance.id, {})
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response({'ok': True})
        except drf_serializers.ValidationError as e:
            return Response({'ok': False, 'error': {'code': 'validation_error', 'message': str(e.detail)}}, status=400)
        except Exception as e:
            return Response({'ok': False, 'error': {'code': 'unknown', 'message': 'Silinemedi. Lütfen tekrar deneyin.'}})

    @action(detail=False, methods=['get'], url_path='impact')
    def impact(self, request):
        """
        Hesaplama amaçlı etki uç noktası (değişiklik yapmaz).
        Query:
          scope=staff
          override_type=closed|break
          date=YYYY-MM-DD
          start_time=HH:MM (break için)
          end_time=HH:MM   (break için)
          staff_id? (admin için opsiyonel; yoksa çağıranın staff kaydı kullanılır)
        """
        from datetime import datetime as dt
        from django.utils import timezone as dj_tz
        from app.appointments.models import Appointment, AppointmentStatus
        scope = (request.query_params.get('scope') or '').lower()
        kind = (request.query_params.get('override_type') or '').lower()
        date_str = request.query_params.get('date')
        start_time_str = request.query_params.get('start_time')
        end_time_str = request.query_params.get('end_time')
        staff_id = request.query_params.get('staff_id')
        if scope not in ('staff',):
            return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'scope=staff olmalı'}})
        if kind not in ('closed', 'break'):
            return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'override_type closed|break olmalı'}})
        try:
            day = dt.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'Geçersiz tarih'}}, status=200)
        # RBAC: staff_id verilmişse admin aynı dükkandan olmalı; yoksa kendi staff
        staff = None
        if staff_id:
            staff = Staff.objects.filter(id=staff_id, barbershop__staff__user=request.user, barbershop__staff__is_admin=True).first()
            if not staff:
                return Response({'ok': False, 'error': {'code': 'forbidden', 'message': 'Yetkiniz yok'}}, status=200)
        else:
            staff = Staff.objects.filter(user=request.user).order_by('-is_admin', '-id').first()
            if not staff:
                return Response({'ok': False, 'error': {'code': 'not_found', 'message': 'Staff profili bulunamadı'}})
        qs = Appointment.objects.filter(
            shop=staff.barbershop,
            staff=staff,
            start_datetime__date=day
        ).exclude(status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW])
        will_cancel = 0
        if kind == 'closed':
            will_cancel = qs.count()
        else:
            # break => saat aralığı zorunlu
            try:
                from datetime import time as dt_time
                st = dt_time.fromisoformat(start_time_str) if start_time_str else None
                et = dt_time.fromisoformat(end_time_str) if end_time_str else None
            except Exception:
                st = et = None
            if not st or not et or st >= et:
                return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'Saat aralığı geçersiz'}}, status=200)
            sdt = dj_tz.make_aware(dt.combine(day, st))
            edt = dj_tz.make_aware(dt.combine(day, et))
            will_cancel = qs.filter(
                Q(end_datetime__gt=sdt) & Q(start_datetime__lt=edt)
            ).count()
        return Response({'ok': True, 'will_cancel_count': int(will_cancel)})

    def _log_action(self, action_type, target_model, target_id, changes):
        try:
            admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
            CalendarAuditLog.objects.create(
                barbershop=admin_staff.barbershop,
                user=self.request.user,
                action_type=action_type,
                target_model=target_model,
                target_id=target_id,
                changes=_jsonable(changes)
            )
        except Staff.DoesNotExist:
            pass

    @action(detail=False, methods=['post'], url_path='today-quick-set')
    def today_quick_set(self, request):
        """
        Quick set today's override
        Payload: {
          "override_scope": "full_day_closed" | "late_opening" | "early_closing" | "time_range_closed",
          "time": "14:00" (for late_opening/early_closing),
          "start_time": "12:00", "end_time": "13:00" (for time_range_closed),
          "reason": "Optional message"
        }
        """
        from django.utils import timezone
        from datetime import datetime, time as dt_time, timedelta
        
        user = request.user
        admin_staff = Staff.objects.filter(user=user, is_admin=True).first()
        if not admin_staff:
            return Response({"detail": "Admin yetkisi gerekli"}, status=403)
        
        scope = request.data.get('override_scope')
        reason = request.data.get('reason', '')
        today = timezone.now().date()
        
        # Delete any existing today overrides for this shop
        Override.objects.filter(
            barbershop=admin_staff.barbershop,
            override_type='shop_global',
            start_date=today,
            end_date=today
        ).delete()
        
        override_data = {
            'barbershop': admin_staff.barbershop,
            'override_type': 'shop_global',
            'override_scope': scope,
            'start_date': today,
            'end_date': today,
            'reason': reason,
            'created_by': user,
            'is_active': True
        }
        
        if scope == 'late_opening':
            override_data['start_time'] = request.data.get('time', '10:00')
        elif scope == 'early_closing':
            override_data['end_time'] = request.data.get('time', '18:00')
        elif scope == 'time_range_closed':
            override_data['start_time'] = request.data.get('start_time', '12:00')
            override_data['end_time'] = request.data.get('end_time', '13:00')
        
        override = Override.objects.create(**override_data)
        
        # Create announcement if reason provided
        if reason:
            SpecialMessage.objects.create(
                barbershop=admin_staff.barbershop,
                source='automatic',
                target_type='all_shop',
                title='Özel Durum',
                content=reason,
                start_datetime=timezone.now(),
                end_datetime=timezone.now() + timedelta(hours=24),
                created_by=user,
                is_active=True
            )
        
        return Response(OverrideSerializer(override).data, status=201)
    
    @action(detail=False, methods=['get'], url_path='today-active')
    def today_active(self, request):
        """Get today's active overrides for the shop"""
        from django.utils import timezone
        user = request.user
        admin_staff = Staff.objects.filter(user=user, is_admin=True).first()
        if not admin_staff:
            return Response({"detail": "Admin yetkisi gerekli"}, status=403)
        
        today = timezone.now().date()
        overrides = Override.objects.filter(
            barbershop=admin_staff.barbershop,
            override_type='shop_global',
            start_date__lte=today,
            end_date__gte=today,
            is_active=True
        )
        
        return Response(OverrideSerializer(overrides, many=True).data)
    
    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        """Deactivate (undo) an override"""
        override = self.get_object()
        override.is_active = False
        override.save()
        return Response({"detail": "Override deactivated"})

    @action(detail=False, methods=["post"], url_path="quick-override")
    def quick_override(self, request):
        """Hızlı override oluşturma - personel için özel durumlar"""
        staff_id = request.data.get('staff_id')
        override_type = request.data.get('override_type', 'staff_individual')
        scope = request.data.get('scope')
        date = request.data.get('date')
        reason = request.data.get('reason', '')
        
        try:
            admin_staff = Staff.objects.get(user=request.user, is_admin=True)
            staff = Staff.objects.get(id=staff_id, barbershop=admin_staff.barbershop)
            
            override = Override.objects.create(
                barbershop=admin_staff.barbershop,
                staff=staff,
                override_type=override_type,
                override_scope=scope,
                start_date=date,
                reason=reason,
                created_by=request.user
            )
            
            return Response(OverrideSerializer(override).data, status=201)
        except Staff.DoesNotExist:
            return Response({"detail": "Staff not found or no permission"}, status=404)


class PartnerSpecialMessageViewSet(viewsets.ModelViewSet):
    serializer_class = SpecialMessageSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        qs = SpecialMessage.objects.filter(barbershop__staff__user=user, barbershop__staff__is_admin=True)
        barbershop_id = self.request.query_params.get('barbershop')
        if barbershop_id:
            qs = qs.filter(barbershop_id=barbershop_id)
        return qs

    def list(self, request, *args, **kwargs):
        # Bypass serializer to avoid touching view_logs/view_count when DB table is missing
        qs = self.filter_queryset(self.get_queryset())
        data = list(qs.values(
            'id','barbershop_id','source','display_type','target_type','title','content',
            'start_datetime','end_datetime','is_active','created_at','updated_at'
        ))
        return Response(data)

    def create(self, request, *args, **kwargs):
        """Kökten sağlam create: minimum alanlarla duyuru oluştur.
        Beklenen zorunlu alanlar: title, content
        Opsiyoneller: barbershop, target_type, source, start_datetime, end_datetime, target_staff[]
        """
        try:
            title = (request.data.get('title') or '').strip()
            content = (request.data.get('content') or '').strip()
            if not title or not content:
                return Response({"detail": "title and content are required"}, status=400)

            # Barbershop belirle
            target_shop_id = request.data.get('barbershop') or request.query_params.get('barbershop')
            admin_qs = Staff.objects.filter(user=request.user, is_admin=True)
            if target_shop_id:
                admin_qs = admin_qs.filter(barbershop_id=target_shop_id)
            admin_staff = admin_qs.first()
            if not admin_staff:
                return Response({"detail": "No permission for this barbershop"}, status=403)

            # Varsayılanlar
            now = timezone.now()
            start_dt = request.data.get('start_datetime') or now
            end_dt = request.data.get('end_datetime') or (now + timedelta(days=365))
            source = (request.data.get('source') or 'manual')
            target_type = (request.data.get('target_type') or 'all_shop')

            # Serializer ile oluştur: eksikleri biz dolduruyoruz (client'tan bağımsız)
            now = timezone.now()
            payload = {
                'barbershop': admin_staff.barbershop.id,
                'source': source or 'manual',
                'display_type': request.data.get('display_type') or 'banner',
                'target_type': target_type or 'all_shop',
                'title': title,
                'content': content,
                'start_datetime': request.data.get('start_datetime') or now.isoformat(),
                'end_datetime': request.data.get('end_datetime') or (now + timedelta(days=365)).isoformat(),
            }
            # Bypass serializer validation to avoid legacy required fields
            obj = SpecialMessage.objects.create(
                barbershop=admin_staff.barbershop,
                source=payload['source'],
                display_type=payload['display_type'],
                target_type=payload['target_type'],
                title=payload['title'],
                content=payload['content'],
                start_datetime=datetime.fromisoformat(payload['start_datetime']) if isinstance(payload['start_datetime'], str) else payload['start_datetime'],
                end_datetime=datetime.fromisoformat(payload['end_datetime']) if isinstance(payload['end_datetime'], str) else payload['end_datetime'],
                created_by=request.user,
                is_active=True,
            )
            # target_staff ids varsa bağla
            try:
                staff_ids = request.data.get('target_staff') or []
                if isinstance(staff_ids, list) and staff_ids:
                    staff_objs = Staff.objects.filter(id__in=staff_ids, barbershop=admin_staff.barbershop)
                    obj.target_staff.add(*list(staff_objs))
            except Exception:
                pass

            data = {
                'id': obj.id,
                'barbershop': obj.barbershop.id,
                'source': obj.source,
                'display_type': obj.display_type,
                'target_type': obj.target_type,
                'title': obj.title,
                'content': obj.content,
                'start_datetime': obj.start_datetime.isoformat(),
                'end_datetime': obj.end_datetime.isoformat(),
                'is_active': obj.is_active,
                'created_at': obj.created_at.isoformat(),
                'updated_at': obj.updated_at.isoformat(),
            }
            return Response(data, status=201)
        except Exception as e:
            return Response({"detail": f"create_failed: {str(e)}"}, status=400)

    def perform_create(self, serializer):
        # İsteği yapan kullanıcının admin olduğu barbershop'u belirle
        target_shop_id = self.request.data.get('barbershop') or self.request.query_params.get('barbershop')
        admin_qs = Staff.objects.filter(user=self.request.user, is_admin=True)
        if target_shop_id:
            admin_qs = admin_qs.filter(barbershop_id=target_shop_id)
        admin_staff = admin_qs.first()
        if not admin_staff:
            # Fallback: kullanıcının herhangi bir admin barbershop'u varsa onu kullan
            admin_staff = Staff.objects.filter(user=self.request.user, is_admin=True).first()
            if not admin_staff:
                raise drf_serializers.ValidationError("No permission for this barbershop")
        # Varsayılanları ata ve kaydet
        now = timezone.now()
        start_dt = serializer.validated_data.get('start_datetime') or now
        end_dt = serializer.validated_data.get('end_datetime') or (now + timedelta(days=365))
        target_type = serializer.validated_data.get('target_type') or 'all_shop'
        obj = serializer.save(
            barbershop=admin_staff.barbershop,
            created_by=self.request.user,
            source=serializer.validated_data.get('source') or 'manual',
            start_datetime=start_dt,
            end_datetime=end_dt,
            target_type=target_type,
            is_active=True,
        )
        self._log_action('create', 'SpecialMessage', serializer.instance.id, serializer.validated_data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # Otomatik mesajlar düzenlenemez
        if instance.source != 'manual':
            return Response({"detail": "Automatic messages cannot be edited"}, status=403)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.source != 'manual':
            return Response({"detail": "Automatic messages cannot be edited"}, status=403)
        return super().partial_update(request, *args, **kwargs)

    def _log_action(self, action_type, target_model, target_id, changes):
        try:
            admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
            CalendarAuditLog.objects.create(
                barbershop=admin_staff.barbershop,
                user=self.request.user,
                action_type=action_type,
                target_model=target_model,
                target_id=target_id,
                changes=changes
            )
        except Staff.DoesNotExist:
            pass

    @action(detail=False, methods=["get"], url_path="active")
    def active_messages(self, request):
        """Aktif mesajları getir"""
        user = request.user
        try:
            admin_staff = Staff.objects.get(user=user, is_admin=True)
            qs = SpecialMessage.objects.filter(
                barbershop=admin_staff.barbershop,
                is_active=True,
            ).order_by('-created_at')
            data = list(qs.values(
                'id','barbershop_id','source','display_type','target_type','title','content',
                'start_datetime','end_datetime','is_active','created_at','updated_at'
            ))
            return Response(data)
        except Staff.DoesNotExist:
            return Response({"detail": "No permission"}, status=403)

    @action(detail=True, methods=["post", "patch"], url_path="visibility")
    def set_visibility(self, request, pk=None):
        """Duyuru görünürlüğünü aç/kapat. Otomatik dahil tüm mesajlar için izin verilir."""
        instance = self.get_object()
        is_active = request.data.get('is_active')
        if is_active is None:
            return Response({"detail": "is_active required"}, status=400)
        instance.is_active = bool(is_active)
        instance.save(update_fields=["is_active"])
        return Response(SpecialMessageSerializer(instance).data)


@extend_schema(exclude=True)
class AnnouncementsPublicApi(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        barbershop_id = request.query_params.get('barbershop_id')
        if not barbershop_id:
            return Response({"detail": "barbershop_id required"}, status=400)
        try:
            bs = Barbershop.objects.get(id=barbershop_id)
        except Barbershop.DoesNotExist:
            return Response({"detail": "Barbershop not found"}, status=404)
        # Sade ve esnek: is_active=True, tarih kısıtı yok; serializer kullanmadan sözlük döndür
        qs = SpecialMessage.objects.filter(
            barbershop=bs,
            is_active=True,
        ).order_by('-created_at')
        data = list(qs.values(
            'id','barbershop_id','source','display_type','target_type','title','content',
            'start_datetime','end_datetime','is_active','created_at','updated_at'
        ))
        return Response(data)


@extend_schema(exclude=True)
class CalendarStatusViewSet(viewsets.ReadOnlyModelViewSet):
    """Takvim durumu hesaplama ViewSet'i"""
    permission_classes = [permissions.AllowAny]  # Public endpoint
    serializer_class = CalendarStatusSerializer
    schema = None  # şemadan tamamen hariç
    
    @action(detail=False, methods=["get"], url_path="shop-status")
    def shop_status(self, request):
        """Dükkanın belirtilen zamandaki tek-kaynak durumunu hesapla.
        Ana uygulama is_open, opening_time, closing_time beklediği için response zenginleştirilir."""
        barbershop_id = request.query_params.get('barbershop_id')
        ts_str = request.query_params.get('ts')
        date_str = request.query_params.get('date')
        if not barbershop_id:
            return Response({"detail": "barbershop_id required"}, status=400)
        try:
            if ts_str:
                ts = datetime.fromisoformat(ts_str) if isinstance(ts_str, str) else timezone.now()
            elif date_str:
                parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
                ts = timezone.make_aware(datetime.combine(parsed, datetime.min.time()).replace(hour=12, minute=0, second=0, microsecond=0))
            else:
                ts = timezone.now()
        except Exception:
            ts = timezone.now()
        data = _compute_shop_status(int(barbershop_id), ts)
        # Ana uygulama ve diğer client'ların beklediği alanlar (now_status ile uyumlu)
        open_interval = data.get('open_interval') or {}
        payload = {
            **data,
            'is_open': data.get('status') == 'open',
            'opening_time': open_interval.get('start') if open_interval else None,
            'closing_time': open_interval.get('end') if open_interval else None,
            'status_message': data.get('message', ''),  # Ana uygulama status_message bekliyor
        }
        resp = Response(payload)
        try:
            resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp['Pragma'] = 'no-cache'
            resp['Expires'] = '0'
        except Exception:
            pass
        return resp

    @action(detail=False, methods=["get"], url_path="staff-status")
    def staff_status(self, request):
        """Personelin günlük durumunu hesapla"""
        staff_id = request.query_params.get('staff_id')
        date_str = request.query_params.get('date')
        
        if not staff_id or not date_str:
            return Response({"detail": "staff_id and date required"}, status=400)
        
        try:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            staff = Staff.objects.get(id=staff_id)
            
            status = self._calculate_staff_status(staff, date)
            
            return Response(StaffCalendarStatusSerializer(status).data)
        except (Staff.DoesNotExist, ValueError):
            return Response({"detail": "Invalid staff or date"}, status=404)
    
    def _calculate_staff_status(self, staff, date):
        """Personel durumunu hesapla"""
        from django.utils import timezone as dj_tz
        
        # Haftanın günü kodu (MON..SUN)
        weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
        day_code = weekday_code_map.get(date.weekday())
        
        # Salon izin günü kontrolü (tüm personeller izinli) - sadece aktif override
        shop_override = Override.objects.filter(
            barbershop=staff.barbershop,
            override_type='shop_global',
            override_scope='full_day_closed',
            start_date__lte=date,
            end_date__gte=date,
            is_active=True,
        ).first()
        
        if shop_override:
            return {
                'staff_id': staff.id,
                'staff_name': getattr(staff.user, 'full_name', None) or staff.user.email,
                'date': date,
                'is_working': False,
                'is_on_leave': True,
                'is_on_break': False,
                'start_time': None,
                'end_time': None,
                'status_message': f"İzinli: {shop_override.reason or 'Salon izin günü'}",
                'active_overrides': [shop_override]
            }
        
        # Personel override'larını kontrol et - sadece aktif override
        staff_overrides = Override.objects.filter(
            staff=staff,
            start_date__lte=date,
            end_date__gte=date,
            is_active=True,
        ).order_by('-created_at')
        
        if staff_overrides.exists():
            override = staff_overrides.first()
            if override.override_scope == 'full_day_closed':
                return {
                    'staff_id': staff.id,
                    'staff_name': getattr(staff.user, 'full_name', None) or staff.user.email,
                    'date': date,
                    'is_working': False,
                    'is_on_leave': True,
                    'is_on_break': False,
                    'start_time': None,
                    'end_time': None,
                    'status_message': f"İzinli: {override.reason or 'Özel durum'}",
                    'active_overrides': [override]
                }
        
        # Dükkan saatlerini al (personel yoksa dükkan saatine göre çalışıyor say)
        shop_hours = ShopWorkingHours.objects.filter(
            barbershop=staff.barbershop,
            day_of_week=day_code
        ).first()
        
        # Personel saatlerini al (yoksa veya kapalı değilse dükkan saatine düş)
        staff_hours = StaffWorkingHours.objects.filter(
            staff=staff,
            day_of_week=day_code
        ).first()
        
        # Saatleri belirle: personel kaydı varsa onu kullan (yoksa dükkan saatine düş)
        if staff_hours and not staff_hours.is_closed:
            start_time = staff_hours.start_time or (shop_hours.start_time if shop_hours else None)
            end_time = staff_hours.end_time or (shop_hours.end_time if shop_hours else None)
            break_start_time = staff_hours.break_start_time or (shop_hours.break_start_time if shop_hours else None)
            break_end_time = staff_hours.break_end_time or (shop_hours.break_end_time if shop_hours else None)
        elif shop_hours and not shop_hours.is_closed:
            # Personel o gün kendi kaydı yok veya kapalı; dükkan açıksa dükkan saatine göre çalışıyor kabul et
            start_time = shop_hours.start_time
            end_time = shop_hours.end_time
            break_start_time = shop_hours.break_start_time
            break_end_time = shop_hours.break_end_time
        else:
            return {
                'staff_id': staff.id,
                'staff_name': getattr(staff.user, 'full_name', None) or staff.user.email,
                'date': date,
                'is_working': False,
                'is_on_leave': False,
                'is_on_break': False,
                'start_time': None,
                'end_time': None,
                'status_message': "Bu gün çalışmıyor",
                'active_overrides': []
            }
        
        if not start_time or not end_time:
            return {
                'staff_id': staff.id,
                'staff_name': getattr(staff.user, 'full_name', None) or staff.user.email,
                'date': date,
                'is_working': False,
                'is_on_leave': False,
                'is_on_break': False,
                'start_time': None,
                'end_time': None,
                'status_message': "Bu gün çalışmıyor",
                'active_overrides': []
            }
        
        now = dj_tz.now()
        current_time = now.time()
        # Bugün değilse veya şu an çalışma saatleri dışındaysa çalışmıyor
        if date != now.date():
            return {
                'staff_id': staff.id,
                'staff_name': getattr(staff.user, 'full_name', None) or staff.user.email,
                'date': date,
                'is_working': False,
                'is_on_leave': False,
                'is_on_break': False,
                'start_time': start_time,
                'end_time': end_time,
                'status_message': None,
                'active_overrides': []
            }
        if current_time < start_time or current_time >= end_time:
            return {
                'staff_id': staff.id,
                'staff_name': getattr(staff.user, 'full_name', None) or staff.user.email,
                'date': date,
                'is_working': False,
                'is_on_leave': False,
                'is_on_break': False,
                'start_time': start_time,
                'end_time': end_time,
                'status_message': f"Çalışma saatleri {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}",
                'active_overrides': []
            }
        # Mola kontrolü: 1) Haftalık periyodik mola 2) İleri tarihe atanmış BreakWindow
        is_on_break = False
        break_ends_in = None
        if date == now.date():
            # 1) Haftalık periyodik mola (StaffWorkingHours break_start_time/break_end_time)
            if break_start_time and break_end_time and break_start_time <= current_time <= break_end_time:
                is_on_break = True
                break_end_dt = dj_tz.make_aware(datetime.combine(date, break_end_time))
                break_ends_in = int((break_end_dt - now).total_seconds() / 60)
            # 2) İleri tarihe atanmış günlük mola (BreakWindow)
            if not is_on_break:
                from app.barbers.models import BreakWindow
                break_windows = BreakWindow.objects.filter(
                    staff=staff,
                    date=date,
                    start_time__lte=current_time,
                    end_time__gt=current_time
                ).first()
                if break_windows:
                    is_on_break = True
                    break_end_dt = dj_tz.make_aware(datetime.combine(date, break_windows.end_time))
                    break_ends_in = int((break_end_dt - now).total_seconds() / 60)
        
        status_message = None
        if is_on_break and break_end_time:
            status_message = f"Şu an mola'da, {break_end_time.strftime('%H:%M')}'da mola bitecek"
        
        return {
            'staff_id': staff.id,
            'staff_name': getattr(staff.user, 'full_name', None) or staff.user.email,
            'date': date,
            'is_working': True,
            'is_on_leave': False,
            'is_on_break': is_on_break,
            'break_ends_in': break_ends_in,
            'break_start_time': break_start_time,
            'break_end_time': break_end_time,
            'start_time': start_time,
            'end_time': end_time,
            'status_message': status_message,
            'active_overrides': []
        }

    @action(detail=False, methods=["get"], url_path="now")
    def now(self, request):
        """Get current live status for a barbershop with minutes until open info"""
        from django.utils import timezone
        barbershop_id = request.query_params.get('barbershop_id')
        
        if not barbershop_id:
            return Response({"detail": "barbershop_id required"}, status=400)
        
        try:
            barbershop = Barbershop.objects.get(id=barbershop_id)
            now = timezone.now() # aware datetime
            today = now.date()
            current_time = now.time()
            
            # ÖNCE DailyOverride kontrolü yap - bu en yüksek önceliğe sahip
            daily_override = DailyOverride.objects.filter(barbershop=barbershop, date=today).first()
            if daily_override:
                is_open = daily_override.status == 'open'
                status_message = daily_override.note.strip() if daily_override.note and daily_override.note.strip() else ("Bugün açık" if is_open else "Bugün kapalı")
                note = daily_override.note or ""
                weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
                day_code = weekday_code_map.get(today.weekday())
                active_staff_count = StaffWorkingHours.objects.filter(
                    staff__barbershop=barbershop,
                    day_of_week=day_code,
                    start_time__lte=current_time,
                    end_time__gte=current_time,
                    is_closed=False
                ).values('staff').distinct().count() if is_open else 0
                # Manuel aç/kapa: ana uygulamada sadece "Açık" / "Kapalı" yazsın; saat gösterme
                resp_data = {
                    'is_open': is_open,
                    'is_break': False,
                    'status_message': status_message,
                    'note': note,
                    'minutes_until_open': None,
                    'break_end_time': None,
                    'source': 'TOGGLE',
                    'opening_time': None,
                    'closing_time': None,
                    'has_staff_working': active_staff_count > 0,
                    'active_staff_count': active_staff_count,
                }
                # Cache bypass için header ekle
                resp = Response(resp_data, headers={
                    'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                })
                return resp
            
            # Defaults
            is_open = True
            is_break = False
            status_message = ""
            minutes_until_open = None
            break_end_time = None
            
            # 1. Check Override
            override = Override.objects.filter(
                barbershop=barbershop,
                override_type='shop_global',
                start_date__lte=today,
                end_date__gte=today,
                is_active=True
            ).first()
            
            if override:
                if override.override_scope == 'full_day_closed':
                    is_open = False
                    status_message = override.reason or "Dükkan Kapalı"
                elif override.override_scope == 'late_opening':
                    if override.start_time and current_time < override.start_time:
                        is_open = False
                        status_message = f"Geç Açılış ({override.start_time.strftime('%H:%M')})"
                        # Calculate minutes until open
                        open_dt = timezone.make_aware(datetime.combine(today, override.start_time))
                        minutes_until_open = int((open_dt - now).total_seconds() / 60)
                elif override.override_scope == 'early_closing':
                    if override.end_time and current_time >= override.end_time:
                        is_open = False
                        status_message = "Erken Kapanış"
                elif override.override_scope == 'time_range_closed':
                    if override.start_time and override.end_time:
                        if override.start_time <= current_time <= override.end_time:
                            is_open = False
                            is_break = True
                            status_message = f"Mola ({override.end_time.strftime('%H:%M')} bitiş)"
                            break_end_time = override.end_time.strftime('%H:%M')
                            end_dt = timezone.make_aware(datetime.combine(today, override.end_time))
                            minutes_until_open = int((end_dt - now).total_seconds() / 60)

            # 2. Check Holiday Override & Official Holiday (if no specific override block found yet)
            if is_open: # Only check if not already closed by override
                decision = ShopHolidayOverride.objects.filter(barbershop=barbershop, date=today).first()
                if decision:
                    if decision.status == ShopHolidayOverride.Status.CLOSED:
                        is_open = False
                        status_message = f"Bugün Kapalı - {decision.title or 'Özel Gün'}"
                    elif decision.status == ShopHolidayOverride.Status.CUSTOM:
                        # Check custom hours
                        if decision.open_time and current_time < decision.open_time:
                            is_open = False
                            status_message = f"Açılış: {decision.open_time.strftime('%H:%M')}"
                            open_dt = timezone.make_aware(datetime.combine(today, decision.open_time))
                            minutes_until_open = int((open_dt - now).total_seconds() / 60)
                        elif decision.close_time and current_time >= decision.close_time:
                            is_open = False
                            status_message = "Kapalı"
                else:
                    if OfficialHoliday.objects.filter(country_code='TR', date=today).exists():
                        is_open = False
                        status_message = "Bugün Kapalı (Resmi Tatil)"

            # 3. Check Regular Hours (if still open)
            if is_open:
                weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
                day_code = weekday_code_map.get(today.weekday())
                shop_hours = ShopWorkingHours.objects.filter(barbershop=barbershop, day_of_week=day_code).first()
                
                if not shop_hours or shop_hours.is_closed:
                    is_open = False
                    status_message = "Bugün Kapalı"
                else:
                    # Check open/close times - timezone-aware karşılaştırma
                    start_time = shop_hours.start_time
                    end_time = shop_hours.end_time
                    
                    if start_time and end_time:
                        # Açılış saatinden önceyse kapalı
                        if current_time < start_time:
                            is_open = False
                            status_message = f"Açılış: {start_time.strftime('%H:%M')}"
                            open_dt = timezone.make_aware(datetime.combine(today, start_time))
                            minutes_until_open = int((open_dt - now).total_seconds() / 60)
                        # Kapanış saatinden sonra veya eşitse kapalı
                        elif current_time >= end_time:
                            is_open = False
                            status_message = "Kapalı"
                        else:
                            # Çalışma saatleri içindeyse açık (mola kontrolü aşağıda yapılacak)
                            pass
                    else:
                        # Saat bilgisi yoksa kapalı say
                        is_open = False
                        status_message = "Saat bilgisi bulunamadı"
                    
                    # Eğer hala açıksa mola kontrolü yap
                    if is_open:
                        # Within working hours, check breaks
                        # 1. Önce haftalık periyodik mola kontrolü
                        if shop_hours.break_start_time and shop_hours.break_end_time:
                            if shop_hours.break_start_time <= current_time <= shop_hours.break_end_time:
                                is_open = False
                                is_break = True
                                status_message = f"Mola ({shop_hours.break_end_time.strftime('%H:%M')} bitiş)"
                                break_end_time = shop_hours.break_end_time.strftime('%H:%M')
                                end_dt = timezone.make_aware(datetime.combine(today, shop_hours.break_end_time))
                                minutes_until_open = int((end_dt - now).total_seconds() / 60)
                            else:
                                status_message = "Açık"
                        else:
                            # 2. Tarih bazlı özel mola kontrolü (BreakWindow)
                            shop_break = BreakWindow.objects.filter(
                                barbershop=barbershop,
                                scope=BreakWindow.Scope.SHOP,
                                date=today,
                                start_time__lte=current_time,
                                end_time__gte=current_time,
                            ).order_by("start_time").first()
                            
                            if shop_break:
                                is_open = False
                                is_break = True
                                status_message = f"Mola ({shop_break.end_time.strftime('%H:%M')} bitiş)"
                                break_end_time = shop_break.end_time.strftime('%H:%M')
                                end_dt = timezone.make_aware(datetime.combine(today, shop_break.end_time))
                                minutes_until_open = int((end_dt - now).total_seconds() / 60)
                            else:
                                status_message = "Açık"

            # Opening ve closing time'ları hesapla
            opening_time_str = None
            closing_time_str = None
            if is_open and not is_break:
                # Normal çalışma saatleri içindeyse closing time'ı göster
                shop_hours = ShopWorkingHours.objects.filter(barbershop=barbershop, day_of_week=weekday_code_map.get(today.weekday())).first()
                if shop_hours and shop_hours.end_time:
                    closing_time_str = shop_hours.end_time.strftime('%H:%M')
            elif not is_open and not is_break:
                # Kapalıysa ve mola değilse opening time'ı göster
                shop_hours = ShopWorkingHours.objects.filter(barbershop=barbershop, day_of_week=weekday_code_map.get(today.weekday())).first()
                if shop_hours and shop_hours.start_time:
                    opening_time_str = shop_hours.start_time.strftime('%H:%M')
            
            weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
            day_code = weekday_code_map.get(today.weekday())
            active_staff_count = StaffWorkingHours.objects.filter(
                staff__barbershop=barbershop,
                day_of_week=day_code,
                start_time__lte=current_time,
                end_time__gte=current_time,
                is_closed=False
            ).values('staff').distinct().count() if is_open else 0

            resp = Response({
                'is_open': is_open,
                'is_break': is_break,
                'status_message': status_message,
                'minutes_until_open': minutes_until_open,
                'break_end_time': break_end_time,
                'opening_time': opening_time_str,
                'closing_time': closing_time_str,
                'has_staff_working': active_staff_count > 0,
                'active_staff_count': active_staff_count,
            }, headers={
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'Pragma': 'no-cache',
                'Expires': '0'
            })
            return resp
            
        except Barbershop.DoesNotExist:
            return Response({"detail": "Barbershop not found"}, status=404)

    @action(detail=False, methods=["get"], url_path="today-status")
    def today_status(self, request):
        """Get today's status for a barbershop (for customer app)"""
        from django.utils import timezone
        barbershop_id = request.query_params.get('barbershop_id')
        
        if not barbershop_id:
            return Response({"detail": "barbershop_id required"}, status=400)
        
        try:
            barbershop = Barbershop.objects.get(id=barbershop_id)
            today = timezone.now().date()
            
            # Check for active override
            override = Override.objects.filter(
                barbershop=barbershop,
                override_type='shop_global',
                start_date__lte=today,
                end_date__gte=today,
                is_active=True
            ).first()
            
            if override:
                scope_labels = {
                    'full_day_closed': 'Bugün Kapalı',
                    'late_opening': 'Geç Açılış',
                    'early_closing': 'Erken Kapanış',
                    'time_range_closed': 'Mola',
                }
                message = scope_labels.get(override.override_scope, 'Özel Durum')
                if override.reason:
                    message += f' - {override.reason}'
                if override.start_time:
                    message += f' ({override.start_time.strftime("%H:%M")})'
                if override.end_time:
                    message += f' - {override.end_time.strftime("%H:%M")}'
                
                return Response({
                    'is_open': False if override.override_scope == 'full_day_closed' else True,
                    'status_message': message,
                    'active_override': {
                        'scope': override.override_scope,
                        'reason': override.reason,
                        'start_time': override.start_time.strftime("%H:%M") if override.start_time else None,
                        'end_time': override.end_time.strftime("%H:%M") if override.end_time else None,
                    }
                })
            
            # Holiday decisions (shop-specific first, then official default)
            decision = ShopHolidayOverride.objects.filter(barbershop=barbershop, date=today).first()
            if decision:
                if decision.status == ShopHolidayOverride.Status.CLOSED:
                    return Response({
                        'is_open': False,
                        'status_message': f"Bugün Kapalı - {decision.title or 'Özel Gün'}",
                        'active_override': None
                    })
                if decision.status == ShopHolidayOverride.Status.CUSTOM:
                    ot = decision.open_time.strftime('%H:%M') if decision.open_time else None
                    ct = decision.close_time.strftime('%H:%M') if decision.close_time else None
                    return Response({
                        'is_open': True,
                        'status_message': f"Özel Saatler • {ot} - {ct}",
                        'active_override': None
                    })
                # OPEN -> continue
            else:
                if OfficialHoliday.objects.filter(country_code='TR', date=today).exists():
                    return Response({
                        'is_open': False,
                        'status_message': 'Bugün Kapalı (Resmi Tatil)',
                        'active_override': None
                    })

            shop_break = BreakWindow.objects.filter(
                barbershop=barbershop,
                scope=BreakWindow.Scope.SHOP,
                date=today,
                start_time__lte=now.time(),
                end_time__gte=now.time(),
            ).order_by("start_time").first()
            if shop_break:
                return Response({
                    'is_open': False,
                    'status_message': f"Şu an mola vakti, {shop_break.end_time.strftime('%H:%M')}'da mola bitecek.",
                    'active_override': {
                        'scope': 'break',
                        'reason': shop_break.label or 'Mola',
                        'start_time': shop_break.start_time.strftime('%H:%M'),
                        'end_time': shop_break.end_time.strftime('%H:%M'),
                    },
                    })

            # No override/holiday, check regular shop hours
            weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
            day_code = weekday_code_map.get(today.weekday())
            shop_hours = ShopWorkingHours.objects.filter(barbershop=barbershop, day_of_week=day_code).first()
            
            # Aktif personel sayısı hesapla (şu anda çalışan personeller)
            now = timezone.now()
            active_staff_count = 0
            if shop_hours and not shop_hours.is_closed:
                active_staff_count = StaffWorkingHours.objects.filter(
                    staff__barbershop=barbershop,
                    day_of_week=day_code,
                    start_time__lte=now.time(),
                    end_time__gte=now.time(),
                    is_closed=False
                ).values('staff').distinct().count()
            
            if shop_hours and not shop_hours.is_closed:
                return Response({
                    'is_open': True,
                    'status_message': f'Açık • {shop_hours.start_time.strftime("%H:%M")} - {shop_hours.end_time.strftime("%H:%M")}',
                    'active_override': None,
                    'active_staff_count': active_staff_count
                })
            else:
                return Response({
                    'is_open': False,
                    'status_message': 'Bugün Kapalı',
                    'active_override': None,
                    'active_staff_count': 0
                })
        except Barbershop.DoesNotExist:
            return Response({"detail": "Barbershop not found"}, status=404)

    @extend_schema(exclude=True)
    @action(detail=False, methods=["get"], url_path="day-overrides")
    def day_overrides(self, request):
        """Belirli bir gün için shop/staff kapatma bantlarını döndürür."""
        barbershop_id = request.query_params.get('barbershop_id')
        date_str = request.query_params.get('date')
        staff_id = request.query_params.get('staff_id')
        if not barbershop_id or not date_str:
            return Response({"detail": "barbershop_id and date required"}, status=400)
        try:
            from datetime import datetime as _dt
            day = _dt.strptime(date_str, '%Y-%m-%d').date()
            shop = Barbershop.objects.get(id=int(barbershop_id))
        except Exception:
            return Response({"detail": "Invalid parameters"}, status=400)
        # Shop tarafı
        weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
        code = weekday_code_map.get(day.weekday())
        shop_hours = ShopWorkingHours.objects.filter(barbershop=shop, day_of_week=code).first()
        open_window = None
        if shop_hours and not shop_hours.is_closed:
            open_window = {'start': shop_hours.start_time.strftime('%H:%M') if shop_hours.start_time else None,
                           'end': shop_hours.end_time.strftime('%H:%M') if shop_hours.end_time else None}
        # Global overrides for that day
        shop_breaks = []
        ov_qs = Override.objects.filter(barbershop=shop, override_type='shop_global',
                                        start_date__lte=day, end_date__gte=day)
        full_day = False
        for ov in ov_qs:
            if ov.override_scope == 'full_day_closed':
                full_day = True
            elif ov.override_scope == 'time_range_closed' and ov.start_time and ov.end_time:
                shop_breaks.append({'start': ov.start_time.strftime('%H:%M'),
                                    'end': ov.end_time.strftime('%H:%M'),
                                    'label': 'Kapalı'})
            elif ov.override_scope == 'early_closing' and ov.end_time:
                shop_breaks.append({'start': ov.end_time.strftime('%H:%M'),
                                    'end': open_window['end'] if open_window else None,
                                    'label': 'Erken kapanış'})
            elif ov.override_scope == 'late_opening' and ov.start_time:
                shop_breaks.append({'start': open_window['start'] if open_window else None,
                                    'end': ov.start_time.strftime('%H:%M'),
                                    'label': 'Geç açılış'})
        shop_obj = {
            'status': 'closed' if full_day else 'open',
            'open_window': open_window,
            'breaks': shop_breaks
        }
        # Staff tarafı (opsiyonel tek staff)
        staff_list = []
        if staff_id:
            st = Staff.objects.filter(id=int(staff_id), barbershop=shop).first()
            if st:
                s_code = code
                s_hours = StaffWorkingHours.objects.filter(staff=st, day_of_week=s_code).first()
                s_full = False
                s_breaks = []
                s_ov_qs = Override.objects.filter(staff=st, start_date__lte=day, end_date__gte=day)
                for ov in s_ov_qs:
                    if ov.override_scope == 'full_day_closed':
                        s_full = True
                    elif ov.override_scope == 'time_range_closed' and ov.start_time and ov.end_time:
                        s_breaks.append({'start': ov.start_time.strftime('%H:%M'),
                                         'end': ov.end_time.strftime('%H:%M'),
                                         'label': 'Mola'})
                staff_list.append({
                    'id': st.id,
                    'name': getattr(st.user, 'get_full_name', lambda: st.user.email)(),
                    'full_day': s_full,
                    'breaks': s_breaks
                })
        return Response({'shop': shop_obj, 'staff': staff_list})

    @action(detail=False, methods=["get"], url_path="weekly")
    def weekly_calendar(self, request):
        """Haftalık takvim görünümü"""
        barbershop_id = request.query_params.get('barbershop_id')
        week_start_str = request.query_params.get('week_start')
        
        if not barbershop_id or not week_start_str:
            return Response({"detail": "barbershop_id and week_start required"}, status=400)
        
        try:
            from datetime import datetime, timedelta
            week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
            week_end = week_start + timedelta(days=6)
            
            barbershop = Barbershop.objects.get(id=barbershop_id)
            
            # Haftalık verileri topla (values ile serialize edilir; personel molaları dahil)
            shop_hours = list(ShopWorkingHours.objects.filter(barbershop=barbershop).values('day_of_week','is_closed','start_time','end_time','break_start_time','break_end_time'))
            staff_hours = list(StaffWorkingHours.objects.filter(staff__barbershop=barbershop).values('staff_id','day_of_week','is_closed','start_time','end_time','break_start_time','break_end_time'))
            overrides = list(Override.objects.filter(
                barbershop=barbershop,
                start_date__lte=week_end,
                end_date__gte=week_start
            ).values('id','override_type','override_scope','start_date','end_date','start_time','end_time','reason'))
            messages = list(SpecialMessage.objects.filter(
                barbershop=barbershop,
                is_active=True,
                start_datetime__date__lte=week_end,
                end_datetime__date__gte=week_start
            ).values('id','title','content','is_active','start_datetime','end_datetime','source','created_at','updated_at'))
            break_windows = list(
                BreakWindow.objects.filter(barbershop=barbershop, date__range=(week_start, week_end))
                .values('id', 'scope', 'staff_id', 'staff__user__full_name', 'staff__user__email', 'date', 'start_time', 'end_time', 'label')
            )
            
            weekly_data = {
                'barbershop_id': barbershop.id,
                'week_start': week_start,
                'week_end': week_end,
                'shop_hours': shop_hours,
                'staff_hours': staff_hours,
                'overrides': overrides,
                'messages': messages
            }
            
            # Serializer kullanmadan sade dict döndür (500 hatalarını önlemek için)
            def _fmt_time(t):
                return t.strftime('%H:%M') if t else None
            for it in shop_hours:
                it['start_time'] = _fmt_time(it.get('start_time'))
                it['end_time'] = _fmt_time(it.get('end_time'))
                it['break_start_time'] = _fmt_time(it.get('break_start_time'))
                it['break_end_time'] = _fmt_time(it.get('break_end_time'))
            for it in staff_hours:
                it['start_time'] = _fmt_time(it.get('start_time'))
                it['end_time'] = _fmt_time(it.get('end_time'))
                it['break_start_time'] = _fmt_time(it.get('break_start_time'))
                it['break_end_time'] = _fmt_time(it.get('break_end_time'))
            for it in overrides:
                it['start_time'] = _fmt_time(it.get('start_time'))
                it['end_time'] = _fmt_time(it.get('end_time'))
            for it in break_windows:
                it['start_time'] = _fmt_time(it.get('start_time'))
                it['end_time'] = _fmt_time(it.get('end_time'))
                staff_name = it.pop('staff__user__full_name', None) or it.pop('staff__user__email', None)
                if staff_name:
                    it['staff_name'] = staff_name

            return Response({
                'barbershop_id': barbershop.id,
                'week_start': week_start.strftime('%Y-%m-%d'),
                'week_end': week_end.strftime('%Y-%m-%d'),
                'shop_hours': shop_hours,
                'staff_hours': staff_hours,
                'overrides': overrides,
                'messages': messages,
                'break_windows': break_windows,
            })
        except (Barbershop.DoesNotExist, ValueError):
            return Response({"detail": "Invalid barbershop or date"}, status=404)

    @action(detail=False, methods=["get"], url_path="holidays")
    def holidays(self, request):
        """Merged list of official holidays and shop overrides for a given year."""
        barbershop_id = request.query_params.get('barbershop_id')
        year = int(request.query_params.get('year') or timezone.now().year)
        with_feed = str(request.query_params.get('feed') or 'false').lower() in ('1','true','yes')
        if not barbershop_id:
            return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'barbershop_id gerekli'}})
        try:
            barbershop = Barbershop.objects.get(id=barbershop_id)
        except Barbershop.DoesNotExist:
            return Response({'ok': False, 'error': {'code': 'not_found', 'message': 'Dükkan bulunamadı'}})

        # Otomatik tatil seed kontrolü
        current_year = timezone.now().year
        if year in [current_year, current_year + 1]:
            # Mevcut yıl veya gelecek yıl için tatil sayısını kontrol et
            holiday_count = OfficialHoliday.objects.filter(country_code='TR', year=year).count()
            if holiday_count < 6:  # TR'de 6 sabit tatil var
                # Eksik tatilleri otomatik seed et
                from django.core.management import call_command
                call_command('seed_official_holidays', year=year, verbosity=0)

        officials = OfficialHoliday.objects.filter(country_code='TR', year=year)
        overrides = ShopHolidayOverride.objects.filter(barbershop=barbershop, date__year=year)
        data = {
            'officials': OfficialHolidaySerializer(officials, many=True).data,
            'overrides': ShopHolidayOverrideSerializer(overrides, many=True).data,
        }
        if with_feed:
            # Build feed: chronological cards with effective status and range grouping
            from datetime import timedelta as _td
            # Map date->effective
            ov_map = {o.date: o for o in overrides}
            items = []
            for oh in officials.order_by('date'):
                dec = ov_map.get(oh.date)
                eff = dec.status if dec else 'open'  # default open per spec
                items.append({'date': oh.date, 'name': oh.name, 'is_official': True, 'effective_status': eff, 'override_id': getattr(dec,'id',None)})
            # Add all custom special days (even if title is empty)
            for o in overrides.order_by('date'):
                name = getattr(o, 'title', '') or ('Özel Saat' if o.status == 'custom_hours' else 'Özel Gün')
                items.append({
                    'date': o.date,
                    'name': name,
                    'is_official': False,
                    'effective_status': o.status,
                    'override_id': o.id
                })
            # Sort
            items.sort(key=lambda x: x['date'])
            # Merge consecutive same-name ranges with same status
            feed = []
            for it in items:
                if not feed:
                    feed.append({'date_start': it['date'], 'date_end': it['date'], 'name': it['name'], 'is_official': it['is_official'], 'effective_status': it['effective_status'], 'override_id': it['override_id']})
                    continue
                last = feed[-1]
                if last['name'] == it['name'] and last['effective_status'] == it['effective_status'] and (last['date_end'] + _td(days=1) == it['date']):
                    last['date_end'] = it['date']
                else:
                    feed.append({'date_start': it['date'], 'date_end': it['date'], 'name': it['name'], 'is_official': it['is_official'], 'effective_status': it['effective_status'], 'override_id': it['override_id']})
            # Serialize dates
            def _fmt(d):
                return d.strftime('%Y-%m-%d')
            for f in feed:
                f['date_start'] = _fmt(f['date_start'])
                f['date_end'] = _fmt(f['date_end'])
            data['feed'] = feed
        return Response({'ok': True, **data})

    @action(detail=False, methods=["get"], url_path="now")
    def now_status(self, request):
        """Return current open/closed and working staff count for a barbershop."""
        barbershop_id = request.query_params.get('barbershop_id')
        if not barbershop_id:
            return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'barbershop_id gerekli'}})
        try:
            barbershop = Barbershop.objects.get(id=barbershop_id)
        except Barbershop.DoesNotExist:
            return Response({'ok': False, 'error': {'code': 'not_found', 'message': 'Dükkan bulunamadı'}})
        now_ts = timezone.localtime()
        status_data = _compute_shop_status(barbershop.id, now_ts)
        # active_staff_count basit tutuluyor: açık ise gün içi aktif personel sayısı
        weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
        day_code = weekday_code_map.get(now_ts.weekday())
        active_staff_count = StaffWorkingHours.objects.filter(
            staff__barbershop=barbershop,
            day_of_week=day_code,
            start_time__lte=now_ts.time(),
            end_time__gte=now_ts.time(),
            is_closed=False
        ).values('staff').distinct().count() if status_data.get('status') == 'open' else 0
        resp = Response({
            'ok': True,
            'is_open': status_data.get('status') == 'open',
            'opening_time': status_data.get('open_interval', {}).get('start') if status_data.get('open_interval') else None,
            'closing_time': status_data.get('open_interval', {}).get('end') if status_data.get('open_interval') else None,
            'active_staff_count': active_staff_count,
            'has_staff_working': active_staff_count > 0,
            'source': status_data.get('source'),
            'message': status_data.get('message'),
            'note': status_data.get('note', ''),  # DailyOverride note'u
            'next_change': status_data.get('next_change'),
            'active_break': status_data.get('active_break'),
            'breaks': status_data.get('breaks'),
        })
        # Cache bypass için header ekle - DailyOverride değişiklikleri hemen yansısın
        try:
            resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp['Pragma'] = 'no-cache'
            resp['Expires'] = '0'
        except Exception:
            pass
        return resp

    @action(detail=False, methods=["post"], url_path="toggle")
    def toggle_today(self, request):
        """Bugün için dükkan açık/kapalı şalteri (barbershop_id + status). Legacy client fallback.
        Hiçbir koşulda 4xx/5xx dönmez; ok=false + error ile 200.
        """
        try:
            # Django REST Framework JSONParser bazen düz str dönebilir; guard et
            try:
                payload = request.data if isinstance(request.data, (dict,)) else {}
            except Exception:
                payload = {}
            barbershop_id = payload.get('barbershop_id') or request.query_params.get('barbershop_id')
            status_val = payload.get('status') or request.query_params.get('status')
            note = payload.get('note', '')
            if not barbershop_id:
                return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'barbershop_id gerekli'}})
            try:
                shop = Barbershop.objects.get(id=int(barbershop_id))
            except Exception:
                return Response({'ok': False, 'error': {'code': 'not_found', 'message': 'Dükkan bulunamadı'}})
            if status_val not in ('open','closed'):
                return Response({'ok': False, 'error': {'code': 'invalid_status', 'message': "Geçersiz durum. 'open' veya 'closed' olmalı."}})
            user = request.user
            # İzin: aynı dükkanda staff olan herkese izin veriyoruz (admin şartı kaldırıldı)
            if not Staff.objects.filter(user=user, barbershop=shop).exists():
                return Response({'ok': False, 'error': {'code': 'forbidden', 'message': 'Bu işlem için yetkiniz yok.'}})
            local_now = timezone.localtime()
            today = local_now.date()
            expires_at = timezone.make_aware(datetime.combine(today, datetime.max.time())).replace(hour=23, minute=59, second=59, microsecond=0)
            obj, _ = DailyOverride.objects.update_or_create(
                barbershop=shop,
                date=today,
                defaults={
                    'status': status_val,
                    'note': note or ("Manuel kapatma" if status_val=='closed' else "Manuel açma"),
                    'expires_at': expires_at,
                    'created_by': user,
                }
            )
            # Cache temizle
            try:
                from django.core.cache import cache
                key = f"shop_status:{shop.id}:{today.strftime('%Y-%m-%d')}"
                cache.delete(key)
            except Exception:
                pass
            return Response({'ok': True, 'data': DailyOverrideSerializer(obj).data})
        except Exception:
            return Response({'ok': False, 'error': {'code': 'unknown', 'message': 'İşlem tamamlanamadı'}})


@extend_schema(exclude=True)
class ToggleTodayApi(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DailyOverrideSerializer
    schema = None  # şemadan tamamen hariç

    def _handle(self, request, **kwargs):
        try:
            try:
                payload = request.data if isinstance(request.data, (dict,)) else {}
            except Exception:
                payload = {}
            barbershop_id = (
                payload.get('barbershop_id')
                or request.query_params.get('barbershop_id')
                or kwargs.get('barbershop_id')
            )
            status_val = (payload.get('status') or request.query_params.get('status') or '').lower()
            note = payload.get('note', '')
            if not barbershop_id:
                return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'barbershop_id gerekli'}})
            try:
                shop = Barbershop.objects.get(id=int(barbershop_id))
            except Exception:
                return Response({'ok': False, 'error': {'code': 'not_found', 'message': 'Dükkan bulunamadı'}})
            if status_val not in ('open','closed'):
                return Response({'ok': False, 'error': {'code': 'invalid_status', 'message': "Geçersiz durum. 'open' veya 'closed' olmalı."}})
            user = request.user
            if not Staff.objects.filter(user=user, barbershop=shop).exists():
                return Response({'ok': False, 'error': {'code': 'forbidden', 'message': 'Bu işlem için yetkiniz yok.'}})
            local_now = timezone.localtime()
            today = local_now.date()
            expires_at = timezone.make_aware(datetime.combine(today, datetime.max.time())).replace(hour=23, minute=59, second=59, microsecond=0)
            obj, _ = DailyOverride.objects.update_or_create(
                barbershop=shop,
                date=today,
                defaults={
                    'status': status_val,
                    'note': note or ("Manuel kapatma" if status_val=='closed' else "Manuel açma"),
                    'expires_at': expires_at,
                    'created_by': user,
                }
            )
            # Cache'i agresif bir şekilde temizle - tüm ilgili key'leri temizle
            try:
                from django.core.cache import cache
                # Bugünün cache key'i
                key = f"shop_status:{shop.id}:{today.strftime('%Y-%m-%d')}"
                cache.delete(key)
                # Tüm tarih varyasyonlarını da temizle (güvenlik için)
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y%m%d']:
                    alt_key = f"shop_status:{shop.id}:{today.strftime(fmt)}"
                    cache.delete(alt_key)
            except Exception:
                pass
            return Response({'ok': True, 'data': DailyOverrideSerializer(obj).data})
        except Exception:
            return Response({'ok': False, 'error': {'code': 'unknown', 'message': 'İşlem tamamlanamadı'}})

    def post(self, request, *args, **kwargs):
        return self._handle(request, **kwargs)

    def put(self, request, *args, **kwargs):
        return self._handle(request, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self._handle(request, **kwargs)

    def get(self, request, *args, **kwargs):
        # GET'e 405 yerine açıklayıcı ok=false dön (legacy clientlar 405 üretmesin)
        return Response({'ok': False, 'error': {'code': 'method_not_allowed', 'message': 'Sadece POST/PUT/PATCH desteklenir'}})


@extend_schema(exclude=True)
class ImpactPlusApi(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Genişletilmiş etki analizi.
        Params:
          barbershop_id, date (YYYY-MM-DD), scope=shop|staff, status=closed|custom_hours
          [start_time,end_time] (custom_hours için)
          [staff_id] (scope=staff için)
        """
        from datetime import datetime as _dt
        from django.utils import timezone as dj_tz
        from app.appointments.models import Appointment, AppointmentStatus
        barbershop_id = request.query_params.get('barbershop_id')
        scope = (request.query_params.get('scope') or '').lower()
        status_val = (request.query_params.get('status') or '').lower()
        date_str = request.query_params.get('date')
        if not barbershop_id or not date_str or scope not in ('shop','staff'):
            return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'barbershop_id, date ve scope gereklidir'}})
        try:
            day = _dt.strptime(date_str, '%Y-%m-%d').date()
            shop = Barbershop.objects.get(id=int(barbershop_id))
        except Exception:
            return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'Parametreler geçersiz'}})
        qs = Appointment.objects.filter(
            shop=shop, start_datetime__date=day
        ).exclude(status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW])
        if scope == 'staff':
            staff_id = request.query_params.get('staff_id')
            if staff_id:
                qs = qs.filter(staff_id=int(staff_id))
            else:
                me = Staff.objects.filter(user=request.user, barbershop=shop).order_by('-is_admin','-id').first()
                if not me:
                    return Response({'ok': False, 'error': {'code': 'forbidden', 'message': 'staff yok'}})
                qs = qs.filter(staff=me)
        if status_val == 'closed':
            cancel_qs = qs
        elif status_val == 'custom_hours':
            st_str = request.query_params.get('start_time'); et_str = request.query_params.get('end_time')
            try:
                from datetime import time as dt_time
                st = dt_time.fromisoformat(st_str) if st_str else None
                et = dt_time.fromisoformat(et_str) if et_str else None
            except Exception:
                st = et = None
            if not st or not et or st >= et:
                return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'Saat aralığı geçersiz'}})
            sdt = dj_tz.make_aware(_dt.combine(day, st))
            edt = dj_tz.make_aware(_dt.combine(day, et))
            # allowed window [sdt,edt): bunun DIŞINDA veya kesişen tüm randevular iptal
            cancel_qs = qs.filter(Q(end_datetime__gt=sdt) & Q(start_datetime__lt=edt))
        else:
            return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'status closed|custom_hours'}})
        total = cancel_qs.count()
        staff_counts = cancel_qs.values('staff_id').annotate(c=Count('id')).order_by('-c')
        affected_staff = staff_counts.count()
        top = []
        # Eşik: toplam ≥5 veya etkilenen personel ≥3 ise breakdown gönder
        if total >= 5 or affected_staff >= 3:
            staff_map = {s.id: s for s in Staff.objects.filter(id__in=[it['staff_id'] for it in staff_counts])}
            for it in list(staff_counts)[:5]:
                st = staff_map.get(it['staff_id'])
                full_name = ''
                try:
                    fn = getattr(st.user, 'first_name', '') or ''
                    ln = getattr(st.user, 'last_name', '') or ''
                    full_name = (fn + ' ' + ln).strip() or st.user.email
                except Exception:
                    full_name = 'Personel'
                top.append({'staff_id': it['staff_id'], 'name': full_name, 'cancellations': it['c']})
        return Response({'ok': True, 'total_cancellations': total, 'affected_staff_count': affected_staff, 'staff_top': top})

class StaffServiceViewSet(viewsets.ModelViewSet):
    """
    Personellerin kendi hizmetlerini yönetmesi için.
    Sadece personel kendi kaydını düzenleyebilir.
    """
    serializer_class = StaffServiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    pagination_class = None  # Liste ham dizi dönsün (Hizmetlerim ekranı list/results uyumluluğu)

    def get_queryset(self):
        # Staff can only see their own services; optionally scope by barbershop
        user = self.request.user
        barbershop_id = self.request.query_params.get('barbershop')
        staff_qs = Staff.objects.filter(user=user)
        if barbershop_id:
            staff_qs = staff_qs.filter(barbershop_id=barbershop_id)
        staff = staff_qs.order_by('-is_admin', '-id').first()
        if staff:
            return StaffService.objects.filter(staff=staff).select_related('service', 'service__category')
        return StaffService.objects.none()
    
    def create(self, request, *args, **kwargs):
        import logging
        from django.db import IntegrityError
        logger = logging.getLogger(__name__)
        logger.info("[StaffService CREATE] request data: service=%s price=%s duration_minutes=%s",
                    request.data.get('service'), request.data.get('price'), request.data.get('duration_minutes'))

        service_id = request.data.get('service')
        if not service_id:
            return Response({"detail": "'service' field is required"}, status=400)

        try:
            service = Service.objects.get(id=service_id)
        except Service.DoesNotExist:
            return Response({"detail": "Service not found"}, status=404)

        staff = (
            Staff.objects.filter(user=request.user, barbershop=service.barbershop)
            .order_by('-is_admin', '-id')
            .first()
        )
        if not staff:
            logger.error(f"[StaffService CREATE] Staff not found or not in same barbershop. user={request.user} service.barbershop={service.barbershop_id}")
            return Response({"detail": "Staff profile not found for this barbershop"}, status=403)

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"[StaffService CREATE] Validation errors: {serializer.errors}")
            return Response(serializer.errors, status=400)

        try:
            # Manual upsert to avoid MultipleObjectsReturned
            qs = StaffService.objects.filter(staff=staff, service=service).order_by('created_at', 'id')
            if qs.exists():
                instance = qs.first()
                # Clean duplicates quietly
                qs.exclude(id=instance.id).delete()
                instance.price = serializer.validated_data['price']
                instance.duration_minutes = serializer.validated_data['duration_minutes']
                instance.is_active = True
                instance.save(update_fields=['price', 'duration_minutes', 'is_active', 'updated_at'])
                out = self.get_serializer(instance)
                headers = self.get_success_headers(out.data)
                return Response(out.data, status=200, headers=headers)
            else:
                instance = StaffService.objects.create(
                    staff=staff,
                    service=service,
                    price=serializer.validated_data['price'],
                    duration_minutes=serializer.validated_data['duration_minutes'],
                    is_active=True,
                )
                out = self.get_serializer(instance)
                headers = self.get_success_headers(out.data)
                return Response(out.data, status=201, headers=headers)
        except IntegrityError:
            # As a last resort, dedupe and retry once
            qs = StaffService.objects.filter(staff=staff, service=service).order_by('created_at', 'id')
            if qs.exists():
                instance = qs.first()
                qs.exclude(id=instance.id).delete()
                instance.price = serializer.validated_data['price']
                instance.duration_minutes = serializer.validated_data['duration_minutes']
                instance.is_active = True
                instance.save(update_fields=['price', 'duration_minutes', 'is_active', 'updated_at'])
                out = self.get_serializer(instance)
                return Response(out.data, status=200)
            return Response({"detail": "Duplicate staff-service combination"}, status=409)

    @action(detail=False, methods=["post"], url_path="bulk-upsert")
    def bulk_upsert(self, request):
        """Upsert multiple staff services in a single call.
        Payload: { staff: <id>|optional (infer by user+barbershop), items: [{service, use_shop_price|price}]}"""
        items = request.data.get('items', [])
        if not isinstance(items, list) or not items:
            return Response({"detail": "items list required"}, status=400)
        staff_id = request.data.get('staff')
        staff = None
        if staff_id:
            staff = Staff.objects.filter(id=staff_id, user=request.user).first()
        if not staff:
            # Infer from first item's service barbershop
            first_service_id = items[0].get('service')
            try:
                svc = Service.objects.get(id=first_service_id)
            except Service.DoesNotExist:
                return Response({"detail": "service not found"}, status=404)
            staff = Staff.objects.filter(user=request.user, barbershop=svc.barbershop).order_by('-is_admin','-id').first()
        if not staff:
            return Response({"detail": "staff not found for barbershop"}, status=403)
        updated = []
        for it in items:
            sid = it.get('service')
            if not sid:
                continue
            try:
                svc = Service.objects.get(id=sid)
            except Service.DoesNotExist:
                continue
            if svc.barbershop_id != staff.barbershop_id:
                continue
            use_shop = bool(it.get('use_shop_price', False))
            price = svc.price if use_shop else it.get('price', svc.price)
            # Upsert
            ss = StaffService.objects.filter(staff=staff, service=svc).order_by('created_at','id')
            if ss.exists():
                inst = ss.first(); ss.exclude(id=inst.id).delete()
                inst.price = price; inst.is_active = True; inst.save(update_fields=['price','is_active','updated_at'])
                updated.append(inst.id)
            else:
                inst = StaffService.objects.create(staff=staff, service=svc, price=price, duration_minutes=svc.duration or 30, is_active=True)
                updated.append(inst.id)
        return Response({"detail": "ok", "updated_count": len(updated)})


class StaffServiceCategoryViewSet(viewsets.ModelViewSet):
    """
    Personellerin kendi hizmet kategorilerini yönetmesi için.
    Sadece personel kendi kategorilerini düzenleyebilir.
    """
    serializer_class = StaffServiceCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    
    def get_queryset(self):
        # Staff can only see their own categories
        # Use filter().first() to handle multiple staff records safely
        staff = Staff.objects.filter(user=self.request.user).order_by('-is_admin', '-id').first()
        if staff:
            return StaffServiceCategory.objects.filter(staff=staff).select_related('category')
        return StaffServiceCategory.objects.none()
    
    def perform_create(self, serializer):
        # Auto-inject staff from logged-in user
        # Use filter().first() to handle multiple staff records safely
        staff = Staff.objects.filter(user=self.request.user).order_by('-is_admin', '-id').first()
        if staff:
            serializer.save(staff=staff)


class ShopCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Public shop categories endpoint (used on mobile home screens)."""
    serializer_class = ShopCategorySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        # Schema generation safety
        if getattr(self, "swagger_fake_view", False):
            return ShopCategory.objects.none()

        # Eğer hiç aktif kategori yoksa, varsayılan seti seed et / aktif hale getir.
        if ShopCategory.objects.filter(is_active=True).count() == 0:
            default_categories = [
                {"name": "Saç Hizmetleri", "slug": "sac-hizmetleri"},
                {"name": "Güzellik & Estetik", "slug": "guzellik-estetik"},
                {"name": "Nail & El Bakımı", "slug": "nail-el-bakimi"},
                {"name": "Cilt & Yüz Bakımı", "slug": "cilt-yuz-bakimi"},
                {"name": "Profesyonel Bakım", "slug": "profesyonel-bakim"},
            ]
            for item in default_categories:
                # Zaten varsa güncelle, yoksa oluştur (hepsini aktif yap)
                ShopCategory.objects.update_or_create(
                    slug=item["slug"],
                    defaults={"name": item["name"], "is_active": True},
                )

        return ShopCategory.objects.filter(is_active=True).order_by("name")


class PartnerHolidayOverrideViewSet(viewsets.ModelViewSet):
    serializer_class = ShopHolidayOverrideSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        # Admin staff'ı bul ve sadece o barbershop'un holiday override'larını getir
        admin_staff = Staff.objects.filter(user=user, is_admin=True).first()
        if not admin_staff:
            return ShopHolidayOverride.objects.none()
        return ShopHolidayOverride.objects.filter(barbershop=admin_staff.barbershop).distinct()

    @action(detail=False, methods=['get'], url_path='impact')
    def impact(self, request):
        """
        Shop özel günü için etki hesaplama (değişiklik yapmaz).
        Query: date=YYYY-MM-DD, status=closed|custom_hours, open_time=HH:MM, close_time=HH:MM
        """
        from datetime import datetime as dt
        from django.utils import timezone as dj_tz
        from app.appointments.models import Appointment, AppointmentStatus
        admin_staff = Staff.objects.filter(user=request.user, is_admin=True).first()
        if not admin_staff:
            return Response({'ok': False, 'error': {'code': 'forbidden', 'message': 'Yetki yok'}})
        date_str = request.query_params.get('date')
        status_val = (request.query_params.get('status') or '').lower()
        open_time_str = request.query_params.get('open_time')
        close_time_str = request.query_params.get('close_time')
        try:
            day = dt.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'Geçersiz tarih'}})
        base_qs = Appointment.objects.filter(
            shop=admin_staff.barbershop,
            start_datetime__date=day
        ).exclude(status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW])
        will_cancel = 0
        if status_val == 'closed':
            will_cancel = base_qs.count()
        elif status_val == 'custom_hours':
            try:
                from datetime import time as dt_time
                ot = dt_time.fromisoformat(open_time_str) if open_time_str else None
                ct = dt_time.fromisoformat(close_time_str) if close_time_str else None
            except Exception:
                ot = ct = None
            if not ot or not ct or ot >= ct:
                return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'Saat aralığı geçersiz'}})
            sdt = dj_tz.make_aware(dt.combine(day, ot))
            edt = dj_tz.make_aware(dt.combine(day, ct))
            # Allowed window: [sdt, edt). İzinli pencere dışında kalanlar iptal.
            cancel_qs = base_qs.filter(
                Q(end_datetime__lte=sdt) | Q(start_datetime__gte=edt) | Q(end_datetime__gt=edt) | Q(start_datetime__lt=sdt)
            )
            will_cancel = cancel_qs.count()
        else:
            return Response({'ok': False, 'error': {'code': 'bad_request', 'message': 'status closed|custom_hours olmalı'}})
        return Response({'ok': True, 'will_cancel_count': int(will_cancel)})

    def perform_create(self, serializer):
        # Upsert by (barbershop,date) + doğrulama: resmi tatillerde sadece open/closed
        admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
        date = serializer.validated_data.get('date')
        status_val = serializer.validated_data.get('status')
        open_time = serializer.validated_data.get('open_time')
        close_time = serializer.validated_data.get('close_time')
        title = serializer.validated_data.get('title', '')
        note = serializer.validated_data.get('note', '')

        # Engeller: zaten kapalı gün/saatler
        # 1) ShopWorkingHours günü kapalı ise izin verme
        from datetime import datetime as _dt
        weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
        day_code = weekday_code_map.get(date.weekday())
        shop_wh = ShopWorkingHours.objects.filter(barbershop=admin_staff.barbershop, day_of_week=day_code).first()
        if shop_wh and getattr(shop_wh, 'is_closed', False):
            raise drf_serializers.ValidationError({'detail': 'Bu gün mağaza çalışma saatlerinde kapalı olarak işaretli'})
        # 2) Aynı güne shop-level kapatma (DailyOverride closed) varsa
        if DailyOverride.objects.filter(barbershop=admin_staff.barbershop, date=date, status='closed').exists():
            raise drf_serializers.ValidationError({'detail': 'Bu gün zaten kapalı (manuel kapatma)'})
        # 3) Aynı güne shop_global time_range_closed/full_day_closed varsa
        if Override.objects.filter(
            barbershop=admin_staff.barbershop,
            override_type='shop_global',
            start_date__lte=date
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=date)
        ).filter(
            Q(override_scope='time_range_closed') | Q(override_scope='full_day_closed')
        ).exists():
            raise drf_serializers.ValidationError({'detail': 'Bu gün zaten kapalı saat/kapanış bulunmaktadır'})

        # Resmi tatil listesinde ise custom_hours yasak
        is_official = OfficialHoliday.objects.filter(country_code='TR', date=date).exists()
        if is_official and status_val == 'custom_hours':
            raise drf_serializers.ValidationError({'detail': 'Resmi tatillerde sadece Açık/Kapalı seçilebilir'})
        # Saat aralığı girildiyse her iki saat de zorunlu ve start<end
        if status_val == 'custom_hours':
            if not open_time or not close_time or open_time >= close_time:
                raise drf_serializers.ValidationError({'detail': 'Özel saat için başlangıç/bitiş saatleri zorunlu ve geçerli olmalıdır'})
            # Saatler mağaza çalışma saatleri içinde olmalı (tercih: zorunlu kural)
            if not shop_wh or not shop_wh.start_time or not shop_wh.end_time or not (shop_wh.start_time <= open_time < close_time <= shop_wh.end_time):
                raise drf_serializers.ValidationError({'detail': 'Özel saatler mağaza çalışma saatleri içinde olmalıdır'})

        obj, _ = ShopHolidayOverride.objects.update_or_create(
            barbershop=admin_staff.barbershop,
            date=date,
            defaults={
                'status': status_val,
                'open_time': open_time,
                'close_time': close_time,
                'title': title,
                'note': note,
                'created_by': self.request.user,
            }
        )
        serializer.instance = obj
        # Best-effort: cancel overlapping appointments and create announcement at 00:01
        try:
            from datetime import datetime, time as dt_time
            from django.utils import timezone as dj_tz
            from app.appointments.models import Appointment, AppointmentStatus
            # Cancel logic
            base_qs = Appointment.objects.filter(
                shop=admin_staff.barbershop, start_datetime__date=date
            ).exclude(status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW])
            if status_val == 'closed':
                cancel_qs = base_qs
            elif status_val == 'custom_hours' and open_time and close_time and open_time < close_time:
                sdt = dj_tz.make_aware(datetime.combine(date, open_time))
                edt = dj_tz.make_aware(datetime.combine(date, close_time))
                cancel_qs = base_qs.filter(Q(end_datetime__lte=sdt) | Q(start_datetime__gte=edt) | Q(end_datetime__gt=edt) | Q(start_datetime__lt=sdt))
            else:
                cancel_qs = Appointment.objects.none()
            if cancel_qs.exists():
                cancel_qs.update(status=AppointmentStatus.CANCELLED)
            # 00:01 için planlı duyuru (aktif)
            msg_title = "Salon Kapalı" if status_val == 'closed' else "Salon Çalışma Saatleri"
            msg_content = (note or '').strip()
            if status_val == 'custom_hours' and open_time and close_time:
                msg_content = f"Bugün {open_time.strftime('%H:%M')} - {close_time.strftime('%H:%M')} saatleri arasında hizmet vereceğiz. {msg_content}".strip()
            elif status_val == 'closed':
                msg_content = f"Bugün salonumuz kapalıdır. {msg_content}".strip()

            SpecialMessage.objects.update_or_create(
                barbershop=admin_staff.barbershop,
                source='automatic',
                target_type='all_shop',
                start_datetime=dj_tz.make_aware(datetime.combine(date, dt_time(hour=0, minute=1))),
                defaults={
                    'title': msg_title,
                    'content': msg_content,
                    'end_datetime': dj_tz.make_aware(datetime.combine(date, dt_time(hour=23, minute=59))),
                    'created_by': self.request.user,
                    'is_active': True,
                }
            )
        except Exception:
            # No-op on failure; core upsert already completed
            pass

    def perform_update(self, serializer):
        # Ensure barbershop remains same and user is admin + open/closed sınırları
        admin_staff = Staff.objects.get(user=self.request.user, is_admin=True)
        date = serializer.validated_data.get('date') or getattr(serializer.instance, 'date', None)
        status_val = serializer.validated_data.get('status') or getattr(serializer.instance, 'status', None)
        open_time = serializer.validated_data.get('open_time') or getattr(serializer.instance, 'open_time', None)
        close_time = serializer.validated_data.get('close_time') or getattr(serializer.instance, 'close_time', None)
        # Engeller create ile aynı
        weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
        day_code = weekday_code_map.get(date.weekday())
        shop_wh = ShopWorkingHours.objects.filter(barbershop=admin_staff.barbershop, day_of_week=day_code).first()
        if shop_wh and getattr(shop_wh, 'is_closed', False):
            raise drf_serializers.ValidationError({'detail': 'Bu gün mağaza çalışma saatlerinde kapalı olarak işaretli'})
        if DailyOverride.objects.filter(barbershop=admin_staff.barbershop, date=date, status='closed').exists():
            raise drf_serializers.ValidationError({'detail': 'Bu gün zaten kapalı (manuel kapatma)'})
        if Override.objects.filter(
            barbershop=admin_staff.barbershop,
            override_type='shop_global',
            start_date__lte=date
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=date)
        ).filter(
            Q(override_scope='time_range_closed') | Q(override_scope='full_day_closed')
        ).exists():
            raise drf_serializers.ValidationError({'detail': 'Bu gün zaten kapalı saat/kapanış bulunmaktadır'})
        if status_val == 'custom_hours':
            if not open_time or not close_time or open_time >= close_time:
                raise drf_serializers.ValidationError({'detail': 'Özel saat için başlangıç/bitiş saatleri zorunlu ve geçerli olmalıdır'})
            if not shop_wh or not shop_wh.start_time or not shop_wh.end_time or not (shop_wh.start_time <= open_time < close_time <= shop_wh.end_time):
                raise drf_serializers.ValidationError({'detail': 'Özel saatler mağaza çalışma saatleri içinde olmalıdır'})
        serializer.save(barbershop=admin_staff.barbershop)

    @action(detail=False, methods=['get'], url_path='official-holidays', permission_classes=[permissions.IsAuthenticated])
    def official_holidays(self, request):
        """
        Türkiye'nin tüm resmi tatillerini (dini ve milli bayramlar) döndürür.
        Herhangi bir authenticated kullanıcı erişebilir (sadece okuma).
        Query params: year (opsiyonel, varsayılan: mevcut yıl)
        """
        from django.utils import timezone
        year = int(request.query_params.get('year') or timezone.now().year)
        
        # Otomatik tatil seed kontrolü - mevcut yıl ve gelecek yıl için
        current_year = timezone.now().year
        if year in [current_year, current_year + 1, current_year + 2]:
            holiday_count = OfficialHoliday.objects.filter(country_code='TR', year=year).count()
            if holiday_count < 6:  # TR'de en az 6 sabit tatil var
                from django.core.management import call_command
                try:
                    call_command('seed_official_holidays', year=year, verbosity=0)
                    # Seed sonrası tekrar say
                    holiday_count = OfficialHoliday.objects.filter(country_code='TR', year=year).count()
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Official holidays seed failed for year {year}: {e}")
        
        holidays = OfficialHoliday.objects.filter(country_code='TR', year=year).order_by('date')
        return Response({
            'ok': True,
            'data': OfficialHolidaySerializer(holidays, many=True).data,
            'year': year,
            'count': holidays.count()
        })

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if not serializer.is_valid():
                msg = next(iter(serializer.errors.values()))
                return Response({'ok': False, 'error': {'code': 'validation_error', 'message': str(msg)}})
            self.perform_create(serializer)
            return Response({'ok': True, 'data': self.get_serializer(serializer.instance).data})
        except drf_serializers.ValidationError as e:
            detail = getattr(e, 'detail', None)
            message = ''
            if isinstance(detail, dict):
                try:
                    message = next(iter(detail.values()))
                except Exception:
                    message = str(detail)
            else:
                message = str(e)
            return Response({'ok': False, 'error': {'code': 'validation_error', 'message': str(message)}})
        except Exception:
            return Response({'ok': False, 'error': {'code': 'unknown', 'message': 'İşlem tamamlanamadı. Lütfen tekrar deneyin.'}})

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response({'ok': True})
        except Exception:
            return Response({'ok': False, 'error': {'code': 'unknown', 'message': 'Silinemedi. Lütfen tekrar deneyin.'}})

    def _calculate_shop_status(self, barbershop, date):
        """Dükkan durumunu hesapla - öncelik sırasına göre"""
        from datetime import datetime, time
        
        # Haftanın günü kodu (MON..SUN)
        weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
        day_code = weekday_code_map.get(date.weekday())
        
        # 1. Global override kontrolü (en yüksek öncelik)
        global_overrides = Override.objects.filter(
            barbershop=barbershop,
            override_type='shop_global',
            start_date__lte=date,
            end_date__gte=date
        ).order_by('-created_at')
        
        if global_overrides.exists():
            override = global_overrides.first()
            if override.override_scope == 'full_day_closed':
                return {
                    'date': date,
                    'is_open': False,
                    'opening_time': None,
                    'closing_time': None,
                    'status_message': f"Kapalı: {override.reason or 'Özel durum'}",
                    'active_overrides': [override],
                    'active_messages': []
                }
        
        # 2. Dükkan saatlerini al (personel saati yoksa dükkan saatine göre açık/kapalı göster)
        shop_hours = ShopWorkingHours.objects.filter(
            barbershop=barbershop,
            day_of_week=day_code
        ).first()
        
        if not shop_hours or shop_hours.is_closed:
            return {
                'date': date,
                'is_open': False,
                'opening_time': None,
                'closing_time': None,
                'status_message': "Dükkan bugün kapalı",
                'active_overrides': [],
                'active_messages': []
            }
        
        # 3. Personel saatleri varsa onlara göre aralık; yoksa sadece dükkan saatleri
        working_staff = StaffWorkingHours.objects.filter(
            staff__barbershop=barbershop,
            day_of_week=day_code,
            is_closed=False
        )
        
        if working_staff.exists():
            earliest_start = min([swh.start_time or shop_hours.start_time for swh in working_staff])
            latest_end = max([swh.end_time or shop_hours.end_time for swh in working_staff])
        else:
            earliest_start = shop_hours.start_time
            latest_end = shop_hours.end_time
        
        # 5. Aktif mesajları al (ilgili tarih için)
        active_messages = SpecialMessage.objects.filter(
            barbershop=barbershop,
            is_active=True,
            start_datetime__date__lte=date,
            end_datetime__date__gte=date,
            target_type='all_shop'
        ).order_by('-created_at')
        
        return {
            'date': date,
            'is_open': True,
            'opening_time': earliest_start,
            'closing_time': latest_end,
            'status_message': None,
            'active_overrides': list(global_overrides),
            'active_messages': list(active_messages)
        }

    def _calculate_staff_status(self, staff, date):
        """Personel durumunu hesapla"""
        # Haftanın günü kodu (MON..SUN)
        weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
        day_code = weekday_code_map.get(date.weekday())
        # Personel override'larını kontrol et - sadece aktif override
        staff_overrides = Override.objects.filter(
            staff=staff,
            start_date__lte=date,
            end_date__gte=date,
            is_active=True,
        ).order_by('-created_at')
        
        if staff_overrides.exists():
            override = staff_overrides.first()
            if override.override_scope == 'full_day_closed':
                return {
                    'staff_id': staff.id,
                    'staff_name': staff.user.email,
                    'date': date,
                    'is_working': False,
                    'start_time': None,
                    'end_time': None,
                    'status_message': f"İzinli: {override.reason or 'Özel durum'}",
                    'active_overrides': [override]
                }
        
        # Personel saatlerini al
        staff_hours = StaffWorkingHours.objects.filter(
            staff=staff,
            day_of_week=day_code
        ).first()
        
        if not staff_hours or staff_hours.is_closed:
            return {
                'staff_id': staff.id,
                'staff_name': staff.user.email,
                'date': date,
                'is_working': False,
                'start_time': None,
                'end_time': None,
                'status_message': "Bu gün çalışmıyor",
                'active_overrides': []
            }
        
        # Dükkan saatlerini devral
        shop_hours = ShopWorkingHours.objects.filter(
            barbershop=staff.barbershop,
            day_of_week=day_code
        ).first()
        
        start_time = staff_hours.start_time or (shop_hours.start_time if shop_hours else None)
        end_time = staff_hours.end_time or (shop_hours.end_time if shop_hours else None)
        
        # Mola saatlerini kontrol et (personel mola saatleri öncelikli, yoksa dükkan mola saatleri)
        break_start_time = staff_hours.break_start_time or (shop_hours.break_start_time if shop_hours else None)
        break_end_time = staff_hours.break_end_time or (shop_hours.break_end_time if shop_hours else None)
        
        # Şu anki zamanı kontrol et (mola saatinde mi?)
        now = timezone.now()
        current_time = timezone.localtime(now).time()
        is_on_break = False
        break_ends_in = None
        
        if break_start_time and break_end_time:
            if break_start_time <= current_time <= break_end_time:
                is_on_break = True
                # Mola bitişine kalan dakika
                break_end_dt = timezone.make_aware(datetime.combine(date, break_end_time))
                break_ends_in = int((break_end_dt - now).total_seconds() / 60)
        
        return {
            'staff_id': staff.id,
            'staff_name': getattr(staff.user, 'full_name', None) or staff.user.email,
            'date': date,
            'is_working': True,
            'is_on_break': is_on_break,
            'start_time': start_time,
            'end_time': end_time,
            'break_start_time': break_start_time,
            'break_end_time': break_end_time,
            'break_ends_in': break_ends_in,
            'status_message': f"Şu an mola'da, {break_end_time.strftime('%H:%M')}'da mola bitecek" if is_on_break else None,
            'active_overrides': list(staff_overrides)
        }

