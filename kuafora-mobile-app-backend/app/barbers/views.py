from __future__ import annotations

from django.db.models import Prefetch, Q
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
    
)
from .serializers import (
    BarbershopWithFavoriteSerializer,
    
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
)
from .filters import BarbershopFilter
from .permissions import IsShopAdmin
from django.conf import settings


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
    queryset = (
        Barbershop.objects.all()
        .select_related()
        .prefetch_related("images", "services", "staff")
    )
    serializer_class = BarbershopSerializer
    filterset_class = BarbershopFilter
    search_fields = ("name", "city", "district")

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated:
            if getattr(user, "gender", None) == "male":
                qs = qs.filter(Q(gender="male") | Q(gender="unisex"))
            elif getattr(user, "gender", None) == "female":
                qs = qs.filter(Q(gender="female") | Q(gender="unisex"))
        return qs

    def get_serializer_class(self):
        # Use detail serializer for retrieve to include is_favorited
        if getattr(self, "action", None) == "retrieve":
            from .serializers import BarbershopDetailSerializer
            return BarbershopDetailSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=["get"], url_path="services")
    def services(self, request, pk=None):
        services = Service.objects.filter(barbershop_id=pk, is_active=True)
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)

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
        staff = Staff.objects.filter(barbershop_id=pk)
        serializer = StaffSerializer(staff, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="services-tree")
    def services_tree(self, request, pk=None):
        """
        Get barbershop's categories and services in tree structure.
        Accessible to authenticated staff of this barbershop.
        """
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

    @action(detail=True, methods=["get", "put"], url_path="working-hours")
    def working_hours(self, request, pk=None):
        """\
        GET: Haftalık tabloyu (7 gün) MON..SUN kodlarıyla, override'lar uygulanmış şekilde döndür.
             - Öncelik: Global override > Staff override > StaffWorkingHours > ShopWorkingHours
             - Daha kısıtlayıcı olan kazanır.
        PUT: Admin kullanıcı için mağazanın çalışma saatlerini günceller (legacy, korunur).
        """
        if request.method == "GET":
            try:
                shop = Barbershop.objects.get(id=pk)
            except Barbershop.DoesNotExist:
                return Response({"detail": "Barbershop not found"}, status=404)

            code_list = ["MON","TUE","WED","THU","FRI","SAT","SUN"]
            result = []
            # Be defensive: never raise 500s here
            result = []
            for code in code_list:
                try:
                    has_full_closed = Override.objects.filter(
                        barbershop=shop,
                        override_type='shop_global',
                        start_date__lte=timezone.localdate(),
                        end_date__gte=timezone.localdate(),
                        override_scope='full_day_closed',
                    ).exists()
                    if has_full_closed:
                        result.append({'day_of_week': code,'start_time': None,'end_time': None,'is_closed': True})
                        continue

                    staff_hours = StaffWorkingHours.objects.filter(
                        staff__barbershop=shop, day_of_week=code, is_closed=False,
                    )
                    shop_hours = ShopWorkingHours.objects.filter(barbershop=shop, day_of_week=code).first()

                    if not staff_hours.exists():
                        # StaffWorkingHours yoksa, ShopWorkingHours'a bak
                        if not shop_hours:
                            result.append({'day_of_week': code,'start_time': None,'end_time': None,'is_closed': True})
                        elif shop_hours.is_closed:
                            result.append({'day_of_week': code,'start_time': None,'end_time': None,'is_closed': True})
                        else:
                            # ShopWorkingHours var ve açık, saatleri döndür
                            result.append({'day_of_week': code,'start_time': shop_hours.start_time,'end_time': shop_hours.end_time,'is_closed': False})
                        continue

                    candidates_start = [sh.start_time or (shop_hours.start_time if shop_hours else None) for sh in staff_hours]
                    candidates_end = [sh.end_time or (shop_hours.end_time if shop_hours else None) for sh in staff_hours]
                    candidates_start = [c for c in candidates_start if c is not None]
                    candidates_end = [c for c in candidates_end if c is not None]
                    if not candidates_start or not candidates_end:
                        result.append({'day_of_week': code,'start_time': None,'end_time': None,'is_closed': True})
                        continue
                    start_time = min(candidates_start)
                    end_time = max(candidates_end)
                    result.append({'day_of_week': code,'start_time': start_time,'end_time': end_time,'is_closed': False})
                except Exception:
                    # Fallback: at least return closed state (no 500)
                    result.append({'day_of_week': code,'start_time': None,'end_time': None,'is_closed': True})
            # stringify times to prevent ProgrammingError in JSON serialization
            def _fmt(t):
                try:
                    return t.strftime('%H:%M') if t else None
                except Exception:
                    return None
            for it in result:
                it['start_time'] = _fmt(it.get('start_time'))
                it['end_time'] = _fmt(it.get('end_time'))
            return Response(result)

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
        for item in week:
            day = (item.get("day") or "").upper()
            is_closed = bool(item.get("is_closed", False))
            open_s = item.get("open")
            close_s = item.get("close")
            if day not in valid_days:
                errors[day or "?"] = "invalid_day"
                continue
            if is_closed:
                normalized.append({"day": day, "is_closed": True, "open": None, "close": None})
                continue
            st = parse_hhmm(open_s)
            et = parse_hhmm(close_s)
            if not st or not et:
                errors[day] = "invalid_time"
                continue
            normalized.append({"day": day, "is_closed": False, "open": st, "close": et})

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
            )
        return Response({"detail": "Updated"})

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
    cached = cache.get(key)
    if cached:
        # Eğer DailyOverride varsa ve cache eski olabilir; 5 sn içinde recheck yap
        do = DailyOverride.objects.filter(barbershop_id=barbershop_id, date=ts.date()).first()
        if do and ((ts - timezone.now()).total_seconds() < 5):
            cache.delete(key)
        else:
            return cached
    # 1) DailyOverride (bugün)
    local_ts = timezone.localtime(ts)
    date = local_ts.date()
    shop = Barbershop.objects.filter(id=barbershop_id).first()
    if not shop:
        return {"status": "closed", "source": "WEEKLY_SCHEDULE", "message": "Bulunamadı", "next_change": None, "open_interval": None, "breaks": []}
    do = DailyOverride.objects.filter(barbershop_id=barbershop_id, date=date).first()
    if do:
        status = 'open' if do.status == 'open' else 'closed'
        msg = "Bugün kapalı" if status == 'closed' else None
        data = {"status": status, "source": "TOGGLE", "message": msg, "next_change": None, "open_interval": None, "breaks": []}
        cache.set(key, data, timeout=60)
        return data
    # 2) SpecialDay (Override - sadece tek gün etkilerini değerlendiriyoruz)
    ov = Override.objects.filter(barbershop_id=barbershop_id, start_date__lte=date, end_date__gte=date, is_active=True).order_by('-created_at')
    if ov.exists():
        top = ov.first()
        if top.override_scope == 'full_day_closed':
            data = {"status": "closed", "source": "SPECIAL_DAY", "message": top.reason or "Bugün kapalı", "next_change": None, "open_interval": None, "breaks": []}
            cache.set(key, data, timeout=60)
            return data
        if top.override_scope == 'time_range_closed':
            # Basit yaklaşım: gün açık kabul; kapalı aralığı mola gibi göster
            open_interval, breaks = _effective_shop_hours_with_breaks(shop, date, extra_closed=[(top.start_time, top.end_time)])
            msg, next_change = _message_for_state(open_interval, breaks, local_ts)
            data = {"status": _open_closed_now(open_interval, breaks, local_ts), "source": "SPECIAL_DAY", "message": msg, "next_change": next_change, "open_interval": _to_dict_interval(open_interval), "breaks": _to_list_breaks(breaks)}
            cache.set(key, data, timeout=60)
            return data
    # 3) OfficialHoliday (shop decision)
    shov = ShopHolidayOverride.objects.filter(barbershop_id=barbershop_id, date=date).first()
    if shov:
        if shov.status == 'closed':
            data = {"status": "closed", "source": "OFFICIAL_HOLIDAY", "message": shov.title or "Bugün kapalı", "next_change": None, "open_interval": None, "breaks": []}
            cache.set(key, data, timeout=60)
            return data
        if shov.status == 'custom_hours':
            open_interval = (shov.open_time, shov.close_time)
            msg, next_change = _message_for_state(open_interval, [], local_ts)
            data = {"status": _open_closed_now(open_interval, [], local_ts), "source": "OFFICIAL_HOLIDAY", "message": msg, "next_change": next_change, "open_interval": _to_dict_interval(open_interval), "breaks": []}
            cache.set(key, data, timeout=60)
            return data
    # 4) WeeklySchedule
    open_interval, breaks = _effective_shop_hours_with_breaks(shop, date)
    msg, next_change = _message_for_state(open_interval, breaks, local_ts)
    data = {"status": _open_closed_now(open_interval, breaks, local_ts), "source": "WEEKLY_SCHEDULE", "message": msg, "next_change": next_change, "open_interval": _to_dict_interval(open_interval), "breaks": _to_list_breaks(breaks)}
    cache.set(key, data, timeout=60)
    return data


def _effective_shop_hours_with_breaks(shop, date, extra_closed=None):
    weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
    code = weekday_code_map.get(date.weekday())
    sh = ShopWorkingHours.objects.filter(barbershop=shop, day_of_week=code).first()
    if not sh or sh.is_closed:
        return (None, None), []
    open_interval = (sh.start_time, sh.end_time)
    breaks = []
    # Merge extra closed as break
    if extra_closed and extra_closed[0][0] and extra_closed[0][1]:
        breaks.append({"start": extra_closed[0][0], "end": extra_closed[0][1]})
    return open_interval, breaks


def _to_dict_interval(interval):
    start, end = interval if interval else (None, None)
    if not start or not end:
        return None
    return {"start": start.strftime('%H:%M'), "end": end.strftime('%H:%M')}


def _to_list_breaks(breaks):
    return [{"start": b["start"].strftime('%H:%M'), "end": b["end"].strftime('%H:%M')} for b in breaks]


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
        # return last 7 viewed for current user, most recent first
        return LastViewed.objects.filter(user=self.request.user).order_by('-viewed_at')[:7]

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
        try:
            ViewEvent.objects.create(user=self.request.user, barbershop_id=self.request.data.get('barbershop'))
        except Exception:
            pass
        # ensure at most 7 entries
        qs = LastViewed.objects.filter(user=self.request.user).order_by('-viewed_at')
        ids = list(qs.values_list('id', flat=True))
        if len(ids) > 7:
            LastViewed.objects.filter(id__in=ids[7:]).delete()
        return



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

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PartnerBarbershopViewSet(viewsets.ModelViewSet):
    serializer_class = BarbershopSerializer
    # Allow any authenticated user; queryset restriction + perform_create will enforce admin ownership
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Partner can manage barbershops where they have admin staff
        user = self.request.user
        return Barbershop.objects.filter(staff__user=user, staff__is_admin=True).distinct()

    # No custom permissions; queryset is already restricted to admin-owned shops
    def update(self, request, *args, **kwargs):
        # Admin kuaför ise salon bilgilerini kısmi güncelleyebilir (override)
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        # Sadece belirli alanlar güncellenebilir
        allowed = {"name", "address", "description", "phone", "phone_number", "latitude", "longitude", "city", "district", "gender"}
        data = {k: v for k, v in request.data.items() if k in allowed}
        # phone alias desteği
        if "phone" in data and "phone_number" not in data:
            data["phone_number"] = data.pop("phone")
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
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

    def perform_create(self, serializer):
        barbershop = serializer.save(is_verified=True)
        # Ensure creator is admin staff of this barbershop
        from .models import Staff
        from django.contrib.auth import get_user_model
        user = self.request.user
        Staff.objects.get_or_create(barbershop=barbershop, user=user, defaults={"email": getattr(user, 'email', ''), "is_admin": True})

    @action(detail=False, methods=["get"], url_path="my", permission_classes=[permissions.IsAuthenticated])
    def my_shops(self, request):
        """Kullanıcının personel olduğu (admin veya normal) tüm dükkanlar"""
        qs = Barbershop.objects.filter(staff__user=request.user).distinct()
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="images")
    def upload_image(self, request, pk=None):
        from .models import BarbershopImage
        bs = self.get_object()
        image = request.FILES.get('image')
        if not image:
            return Response({'detail': 'No image'}, status=400)
        BarbershopImage.objects.create(barbershop=bs, image=image)
        return Response({'detail': 'ok'})

    @action(detail=True, methods=["post"], url_path="main-image")
    def set_main_image(self, request, pk=None):
        bs = self.get_object()
        image = request.FILES.get('image')
        if not image:
            return Response({'detail': 'No image'}, status=400)
        bs.main_image = image
        bs.save(update_fields=["main_image"])
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


class ReviewUpsertApi(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ReviewThrottle]

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


class ReviewHighlightsApi(generics.GenericAPIView):
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


class BarbershopReviewsListApi(generics.GenericAPIView):
    """Public list endpoint for all reviews of a barbershop with pagination and filters."""
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
        return Response({"detail": "Updated"})



class FavoriteListView(generics.ListAPIView):
    serializer_class = BarbershopWithFavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Barbershop.objects.filter(
            favorited_by__user=self.request.user
        ).order_by("-favorited_by__created_at")


class FavoriteToggleView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, barbershop_id):
        try:
            barbershop = Barbershop.objects.get(id=barbershop_id)
        except Barbershop.DoesNotExist:
            return Response({"error": "Barbershop not found"}, status=404)
        
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
        try:
            serializer.save(barbershop=admin_staff.barbershop)
        except Exception as e:
            from django.db import IntegrityError
            if isinstance(e, IntegrityError):
                return Response({"detail": str(e)}, status=400)
            raise
        headers = self.get_success_headers(serializer.data)
        # Otomatik duyuru devre dışı
        return Response(serializer.data, status=201, headers=headers)

    def perform_update(self, serializer):
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
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

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


# Takvim ve Mesaj Yönetimi ViewSet'leri
class PartnerShopWorkingHoursViewSet(viewsets.ModelViewSet):
    serializer_class = ShopWorkingHoursSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

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
            # Parse time strings to time objects
            start_time_str = request.data.get('start_time')
            end_time_str = request.data.get('end_time')
            
            from datetime import datetime
            start_time = None
            end_time = None
            
            if start_time_str:
                try:
                    start_time = datetime.strptime(start_time_str, '%H:%M:%S').time()
                except ValueError:
                    try:
                        start_time = datetime.strptime(start_time_str, '%H:%M').time()
                    except ValueError:
                        return Response({"detail": f"Invalid start_time format: {start_time_str}"}, status=400)
            
            if end_time_str:
                try:
                    end_time = datetime.strptime(end_time_str, '%H:%M:%S').time()
                except ValueError:
                    try:
                        end_time = datetime.strptime(end_time_str, '%H:%M').time()
                    except ValueError:
                        return Response({"detail": f"Invalid end_time format: {end_time_str}"}, status=400)

            day_code = (request.data.get('day_of_week') or '').upper()
            valid_days = {'MON','TUE','WED','THU','FRI','SAT','SUN'}
            if day_code not in valid_days:
                return Response({"detail": f"Invalid day_of_week: {day_code}"}, status=400)

            is_closed = bool(request.data.get('is_closed', False))
            if is_closed:
                start_time = None
                end_time = None

            # Upsert to avoid unique_together IntegrityError
            obj, _created = ShopWorkingHours.objects.update_or_create(
                barbershop=admin_staff.barbershop,
                day_of_week=day_code,
                defaults={
                    'start_time': start_time,
                    'end_time': end_time,
                    'is_closed': is_closed,
                }
            )
            print(f"DEBUG: Created ShopWorkingHours: {obj.id}")
            serializer = self.get_serializer(obj)
            return Response(serializer.data, status=201)
        except Exception as e:
            print(f"DEBUG: Exception in create: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({"detail": f"Creation failed: {str(e)}"}, status=400)

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
                changes=changes
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
                            "source": "staff",
                        })
                    else:
                        # Shop saatleri olmayabilir; güvenli fallback
                        result.append({
                            "day": day,
                            "is_closed": bool(getattr(shop, 'is_closed', False)) if shop else True,
                            "open": (shop.start_time.strftime("%H:%M") if getattr(shop, 'start_time', None) else None),
                            "close": (shop.end_time.strftime("%H:%M") if getattr(shop, 'end_time', None) else None),
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
            normalized.append({"day": day, "is_closed": False, "open": st, "close": et})
        if errors:
            return Response({"detail": "invalid_payload", "errors": errors}, status=400)

        # Conflict validation against shop hours
        conflict_errors = {}
        for it in normalized:
            if it["is_closed"]:
                continue
            shop_hours = ShopWorkingHours.objects.filter(barbershop=staff.barbershop, day_of_week=it["day"]).first()
            if not shop_hours or shop_hours.is_closed:
                conflict_errors[it["day"]] = "invalid_time_shop_closed"
                continue
            sh_start = shop_hours.start_time
            sh_end = shop_hours.end_time
            if sh_start and sh_end:
                if (it["open"] < sh_start) or (it["close"] > sh_end):
                    conflict_errors[it["day"]] = "out_of_shop_hours"
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
                changes=changes
            )
        except Staff.DoesNotExist:
            pass


class PartnerOverrideViewSet(viewsets.ModelViewSet):
    serializer_class = OverrideSerializer
    # Personel kendi özel gününü oluşturabilsin; dükkan genel override için RBAC aşağıda kontrol ediliyor
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Politika: Shop-level override'lar (admin) + kendi personel override'ları
        my_staff = Staff.objects.filter(user=user).first()
        shop_ids = list(Staff.objects.filter(user=user, is_admin=True).values_list('barbershop_id', flat=True))
        return Override.objects.filter(
            (Q(staff=my_staff) | Q(barbershop_id__in=shop_ids, override_type='shop_global'))
        )

    def perform_create(self, serializer):
        from datetime import datetime, time, timedelta
        from django.utils import timezone as dj_tz
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
        dates = self.request.data.get('dates')
        created = []
        if isinstance(dates, list) and dates:
            # Tür bazlı doğrulama
            scope = serializer.validated_data.get('override_scope') or mapped_scope
            st = serializer.validated_data.get('start_time')
            et = serializer.validated_data.get('end_time')
            if scope == 'full_day_closed' and (st or et):
                raise drf_serializers.ValidationError("Tam gün kapalı için saat girilmemelidir")
            if scope == 'time_range_closed' and (not st or not et):
                raise drf_serializers.ValidationError("Saat aralığı kapalı için başlangıç ve bitiş saatleri zorunludur")
            if scope == 'early_closing' and not et:
                raise drf_serializers.ValidationError("Erken kapanış için bitiş saati zorunludur")
            if scope == 'late_opening' and not st:
                raise drf_serializers.ValidationError("Geç açılış için başlangıç saati zorunludur")
            # Duplicate ve saat aralığı doğrulama
            for d in dates:
                # Geçmiş ve bugün yasak
                if d <= dj_tz.localdate():
                    raise drf_serializers.ValidationError("Geçmiş ve bugün seçilemez")
                # Duplicate: aynı gün aynı hedefe ikinci kayıt yok
                if effective_type == 'shop_global':
                    if Override.objects.filter(barbershop=base_shop, start_date__lte=d, end_date__gte=d, override_type='shop_global').exists():
                        raise drf_serializers.ValidationError({"detail": "Bu tarih zaten özel gün."})
                else:
                    if Override.objects.filter(staff=serializer.validated_data.get('staff'), start_date__lte=d, end_date__gte=d, override_type='staff_individual').exists():
                        raise drf_serializers.ValidationError({"detail": "Bu tarih zaten özel gün."})
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
                        # Personel çalışma saatleri; yoksa dükkan saatleri
                        weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
                        code = weekday_code_map.get(d.weekday())
                        swh = StaffWorkingHours.objects.filter(staff=serializer.validated_data.get('staff'), day_of_week=code, is_closed=False).first()
                        if swh and swh.start_time and swh.end_time:
                            if not (swh.start_time <= st and et <= swh.end_time):
                                raise drf_serializers.ValidationError({"detail": "Saat, personel açık saatlerinin dışında seçilemez"})
                        else:
                            open_interval, _ = _effective_shop_hours_with_breaks(base_shop, d)
                            if not open_interval or not open_interval[0] or not open_interval[1]:
                                raise drf_serializers.ValidationError({"detail": "O gün dükkan kapalı"})
                            if not (open_interval[0] <= st and et <= open_interval[1]):
                                raise drf_serializers.ValidationError({"detail": "Saat, açık saatlerin dışında seçilemez"})
            # tek serializer instance yerine tek tek create
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
            if d <= dj_tz.localdate():
                raise drf_serializers.ValidationError({"detail": "Geçmiş ve bugün seçilemez"})
            # Duplicate kontrol
            if effective_type == 'shop_global':
                if Override.objects.filter(barbershop=base_shop, start_date__lte=d, end_date__gte=d, override_type='shop_global').exists():
                    raise drf_serializers.ValidationError({"detail": "Bu tarih zaten özel gün."})
            else:
                if Override.objects.filter(staff=serializer.validated_data.get('staff'), start_date__lte=d, end_date__gte=d, override_type='staff_individual').exists():
                    raise drf_serializers.ValidationError({"detail": "Bu tarih zaten özel gün."})
            # Saat aralığı doğrulama
            scope = serializer.validated_data.get('override_scope') or mapped_scope
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
                    weekday_code_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
                    code = weekday_code_map.get(d.weekday())
                    swh = StaffWorkingHours.objects.filter(staff=serializer.validated_data.get('staff'), day_of_week=code, is_closed=False).first()
                    if swh and swh.start_time and swh.end_time:
                        if not (swh.start_time <= st and et <= swh.end_time):
                            raise drf_serializers.ValidationError({"detail": "Saat, personel açık saatlerinin dışında seçilemez"})
                    else:
                        open_interval, _ = _effective_shop_hours_with_breaks(base_shop, d)
                        if not open_interval or not open_interval[0] or not open_interval[1]:
                            raise drf_serializers.ValidationError({"detail": "O gün dükkan kapalı"})
                        if not (open_interval[0] <= st and et <= open_interval[1]):
                            raise drf_serializers.ValidationError({"detail": "Saat, açık saatlerin dışında seçilemez"})
            serializer.save(barbershop=base_shop, created_by=self.request.user)
            created.append(serializer.instance)
        self._log_action('create', 'Override', serializer.instance.id, serializer.validated_data)

        # create_message desteği
        create_message_flag = payload.get('create_message')
        try:
            create_message = str(create_message_flag).lower() in ('1', 'true', 'yes')
        except Exception:
            create_message = False

        if create_message:
            for ov in created:
                staff_part = f" - {getattr(getattr(ov, 'staff', None), 'user', None) and ov.staff.user.email}" if ov.staff else ''
                title = "Uygun değil" if ov.override_scope == 'full_day_closed' else (
                    'Mola / Kısıtlı hizmet' if ov.override_scope == 'time_range_closed' else (
                        'Geç açılış' if ov.override_scope == 'late_opening' else 'Erken kapanış'
                    )
                )
                title = f"{title}{staff_part}"
                content = ov.reason or ""
                start_dt = dj_tz.make_aware(datetime.combine(ov.start_date, ov.start_time or time(0, 0)))
                end_dt = dj_tz.make_aware(datetime.combine(ov.end_date or ov.start_date, ov.end_time or time(23, 59)))
                msg = SpecialMessage.objects.create(
                    barbershop=ov.barbershop,
                    source='automatic',
                    target_type='all_shop' if not ov.staff else 'specific_staff',
                    title=title, content=content,
                    start_datetime=start_dt, end_datetime=end_dt,
                    created_by=self.request.user, is_active=True,
                )
                if ov.staff and msg.target_type == 'specific_staff':
                    msg.target_staff.add(ov.staff)
                msg.save()

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
            # Cancel overlapping appointments if needed (best-effort)
            try:
                from datetime import datetime
                from django.utils import timezone as dj_tz
                from app.appointments.models import Appointment
                from app.appointments.models import AppointmentStatus
                # For single created or last of batch
                ov = serializer.instance
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
                cancel_qs.update(status=AppointmentStatus.CANCELLED)
            except Exception:
                pass
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
        except Exception:
            return Response({'ok': False, 'error': {'code': 'unknown', 'message': 'İşlem tamamlanamadı. Lütfen tekrar deneyin.'}})

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response({'ok': True})
        except Exception:
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
                models.Q(end_datetime__gt=sdt) & models.Q(start_datetime__lt=edt)
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
                changes=changes
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


class CalendarStatusViewSet(viewsets.ReadOnlyModelViewSet):
    """Takvim durumu hesaplama ViewSet'i"""
    permission_classes = [permissions.AllowAny]  # Public endpoint
    
    @action(detail=False, methods=["get"], url_path="shop-status")
    def shop_status(self, request):
        """Dükkanın belirtilen zamandaki tek-kaynak durumunu hesapla"""
        barbershop_id = request.query_params.get('barbershop_id')
        ts_str = request.query_params.get('ts')
        if not barbershop_id:
            return Response({"detail": "barbershop_id required"}, status=400)
        try:
            ts = datetime.fromisoformat(ts_str) if ts_str else timezone.now()
        except Exception:
            ts = timezone.now()
        data = _compute_shop_status(int(barbershop_id), ts)
        return Response(data)

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
            
            # Haftalık verileri topla (values ile serialize edilir)
            shop_hours = list(ShopWorkingHours.objects.filter(barbershop=barbershop).values('day_of_week','is_closed','start_time','end_time'))
            staff_hours = list(StaffWorkingHours.objects.filter(staff__barbershop=barbershop).values('staff_id','day_of_week','is_closed','start_time','end_time'))
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
            for it in staff_hours:
                it['start_time'] = _fmt_time(it.get('start_time'))
                it['end_time'] = _fmt_time(it.get('end_time'))
            for it in overrides:
                it['start_time'] = _fmt_time(it.get('start_time'))
                it['end_time'] = _fmt_time(it.get('end_time'))

            return Response({
                'barbershop_id': barbershop.id,
                'week_start': week_start.strftime('%Y-%m-%d'),
                'week_end': week_end.strftime('%Y-%m-%d'),
                'shop_hours': shop_hours,
                'staff_hours': staff_hours,
                'overrides': overrides,
                'messages': messages,
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
            'source': status_data.get('source'),
            'message': status_data.get('message'),
            'next_change': status_data.get('next_change'),
        })
        try:
            resp['Cache-Control'] = 'no-store, max-age=0'
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


class ToggleTodayApi(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

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
            try:
                from django.core.cache import cache
                key = f"shop_status:{shop.id}:{today.strftime('%Y-%m-%d')}"
                cache.delete(key)
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


class StaffServiceViewSet(viewsets.ModelViewSet):
    """
    Personellerin kendi hizmetlerini yönetmesi için.
    Sadece personel kendi kaydını düzenleyebilir.
    """
    serializer_class = StaffServiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffMember]
    
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
        logger.error(f"[StaffService CREATE] Request data: {request.data}")

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


class PartnerHolidayOverrideViewSet(viewsets.ModelViewSet):
    serializer_class = ShopHolidayOverrideSerializer
    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get_queryset(self):
        user = self.request.user
        return ShopHolidayOverride.objects.filter(barbershop__staff__user=user, barbershop__staff__is_admin=True)

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
                models.Q(end_datetime__lte=sdt) | models.Q(start_datetime__gte=edt) | models.Q(end_datetime__gt=edt) | models.Q(start_datetime__lt=sdt)
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
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=date)
        ).filter(
            models.Q(override_scope='time_range_closed') | models.Q(override_scope='full_day_closed')
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
                cancel_qs = base_qs.filter(models.Q(end_datetime__lte=sdt) | models.Q(start_datetime__gte=edt) | models.Q(end_datetime__gt=edt) | models.Q(start_datetime__lt=sdt))
            else:
                cancel_qs = Appointment.objects.none()
            if cancel_qs.exists():
                cancel_qs.update(status=AppointmentStatus.CANCELLED)
            # Announcement scheduling (start of day)
            msg_title = title or ('Bugün Kapalı' if status_val == 'closed' else 'Bugün Özel Saat')
            msg_content = note or (title or '')
            SpecialMessage.objects.create(
                barbershop=admin_staff.barbershop,
                source='automatic',
                target_type='all_shop',
                title=msg_title,
                content=msg_content,
                start_datetime=dj_tz.make_aware(datetime.combine(date, dt_time(hour=0, minute=1))),
                end_datetime=dj_tz.make_aware(datetime.combine(date, dt_time(hour=23, minute=59))),
                created_by=self.request.user,
                is_active=True,
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
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=date)
        ).filter(
            models.Q(override_scope='time_range_closed') | models.Q(override_scope='full_day_closed')
        ).exists():
            raise drf_serializers.ValidationError({'detail': 'Bu gün zaten kapalı saat/kapanış bulunmaktadır'})
        if status_val == 'custom_hours':
            if not open_time or not close_time or open_time >= close_time:
                raise drf_serializers.ValidationError({'detail': 'Özel saat için başlangıç/bitiş saatleri zorunlu ve geçerli olmalıdır'})
            if not shop_wh or not shop_wh.start_time or not shop_wh.end_time or not (shop_wh.start_time <= open_time < close_time <= shop_wh.end_time):
                raise drf_serializers.ValidationError({'detail': 'Özel saatler mağaza çalışma saatleri içinde olmalıdır'})
        serializer.save(barbershop=admin_staff.barbershop)

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
        
        # 2. Personel saatlerini kontrol et
        working_staff = StaffWorkingHours.objects.filter(
            staff__barbershop=barbershop,
            day_of_week=day_code,
            is_closed=False
        )
        
        if not working_staff.exists():
            return {
                'date': date,
                'is_open': False,
                'opening_time': None,
                'closing_time': None,
                'status_message': "Bugün çalışan personel yok",
                'active_overrides': [],
                'active_messages': []
            }
        
        # 3. Dükkan saatlerini al
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
        
        # 4. Personel saatlerine göre dükkan saatlerini ayarla
        earliest_start = min([swh.start_time or shop_hours.start_time for swh in working_staff])
        latest_end = max([swh.end_time or shop_hours.end_time for swh in working_staff])
        
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
        # Personel override'larını kontrol et
        staff_overrides = Override.objects.filter(
            staff=staff,
            start_date__lte=date,
            end_date__gte=date
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
        
        return {
            'staff_id': staff.id,
            'staff_name': staff.user.email,
            'date': date,
            'is_working': True,
            'start_time': start_time,
            'end_time': end_time,
            'status_message': None,
            'active_overrides': list(staff_overrides)
        }

