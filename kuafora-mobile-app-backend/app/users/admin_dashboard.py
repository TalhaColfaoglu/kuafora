import calendar
from datetime import date, timedelta, datetime

from django.contrib import admin
from django.utils import timezone
from django.db.models import Count, Q, Avg, Sum, F
from django.template.response import TemplateResponse
from django.db.models.functions import TruncDate

from app.users.models import User, UserAddress
from app.analytics.models import UserSession, AppEvent, UserActivityLog, DailyMetrics
from app.users.email_tracking import (
    get_today_email_count,
    get_weekly_email_count,
    get_monthly_email_count,
    get_yearly_email_count,
    get_email_count_for_range,
)
from app.barbers.models import Barbershop, Favorite, Review
from app.appointments.models import Appointment

# Sadece uygulama kullanıcıları (admin/staff hariç) - dashboard metrikleri gerçek kullanıcı verisini göstersin
APP_USER_FILTER = Q(is_staff=False, is_superuser=False)


def _active_breakdown(*, start_date: date, end_date: date, app_type: str = "main") -> dict:
    """Aktif kullanıcı kırılımı.

    Not: Guest kullanıcılar için server tarafında "kullanıcı" kimliği olmadığı için cihaz (device_id) baz alınır.

    - **auth_users**: giriş yapmış (user != null) benzersiz kullanıcı sayısı (user_id)
    - **auth_devices**: giriş yapmış kullanıcıların benzersiz cihaz sayısı (device_id)
    - **guest_devices**: giriş yapmadan devam eden benzersiz cihaz sayısı (user == null)
    - **guest_only_devices**: aynı aralıkta hiç authenticated aktivitesi olmayan guest cihazlar
    - **active_devices**: toplam benzersiz cihaz (auth+guest union)
    - **net_active**: auth_users + guest_only_devices (yaklaşık benzersiz kişi)
    """
    if not app_type:
        app_type = "main"

    qs = UserActivityLog.objects.filter(
        activity_date__gte=start_date,
        activity_date__lte=end_date,
        app_type=app_type,
    )

    auth_users_qs = qs.filter(user__isnull=False).values_list("user_id", flat=True).distinct()
    auth_devices_qs = qs.filter(user__isnull=False).values_list("device_id", flat=True).distinct()
    guest_devices_qs = qs.filter(user__isnull=True).values_list("device_id", flat=True).distinct()
    guest_only_devices_qs = guest_devices_qs.exclude(device_id__in=auth_devices_qs)

    auth_users = auth_users_qs.count()
    auth_devices = auth_devices_qs.count()
    guest_devices = guest_devices_qs.count()
    guest_only_devices = guest_only_devices_qs.count()
    active_devices = qs.values_list("device_id", flat=True).distinct().count()

    return {
        "auth_users": auth_users,
        "auth_devices": auth_devices,
        "guest_devices": guest_devices,
        "guest_only_devices": guest_only_devices,
        "active_devices": active_devices,
        "net_active": auth_users + guest_only_devices,
    }


def _usage_stats(now, today, week_start_date, month_ago):
    """Analytics tablolarından kullanım metrikleri: harita yükleme, uygulama açılma, salon görüntülenmesi, en çok kullanılan özellikler/ekranlar.
    week_start_date: son 7 günün ilk günü (today - 6) için date."""
    try:
        from app.analytics.models import FeatureUsage, AppEvent, ScreenView, UserSession
    except Exception:
        return {
            "map_loads_today": 0,
            "map_loads_week": 0,
            "map_loads_month": 0,
            "app_opens_today": 0,
            "app_opens_week": 0,
            "app_opens_month": 0,
            "shop_views_today": 0,
            "shop_views_week": 0,
            "shop_views_month": 0,
            "shop_views_total": 0,
            "top_features": [],
            "top_screens": [],
        }
    today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    week_start = timezone.make_aware(datetime.combine(week_start_date, datetime.min.time()))
    month_start = timezone.make_aware(datetime.combine(month_ago, datetime.min.time()))
    
    # Harita yükleme (map_view) – FeatureUsage (eğer veri yoksa 0 döner)
    map_today = FeatureUsage.objects.filter(feature_type="map_view", timestamp__gte=today_start).count()
    map_week = FeatureUsage.objects.filter(feature_type="map_view", timestamp__gte=week_start).count()
    map_month = FeatureUsage.objects.filter(feature_type="map_view", timestamp__gte=month_start).count()
    
    # Uygulama açılma – AppEvent (eğer veri yoksa UserSession'dan türet)
    app_open_today = AppEvent.objects.filter(event_type="app_open", timestamp__gte=today_start).count()
    app_open_week = AppEvent.objects.filter(event_type="app_open", timestamp__gte=week_start).count()
    app_open_month = AppEvent.objects.filter(event_type="app_open", timestamp__gte=month_start).count()
    
    # Eğer AppEvent boşsa, UserSession sayısından türet (her session = bir app open)
    if app_open_today == 0:
        app_open_today = UserSession.objects.filter(
            start_time__gte=today_start,
            app_type='main'
        ).count()
    if app_open_week == 0:
        app_open_week = UserSession.objects.filter(
            start_time__gte=week_start,
            app_type='main'
        ).count()
    if app_open_month == 0:
        app_open_month = UserSession.objects.filter(
            start_time__gte=month_start,
            app_type='main'
        ).count()
    
    # Toplam salon görüntülenmesi – ScreenView (BarberDetailScreen = salon detay ekranı)
    shop_view_q = Q(screen_name="BarberDetailScreen")
    shop_views_today = ScreenView.objects.filter(shop_view_q, timestamp__gte=today_start).count()
    shop_views_week = ScreenView.objects.filter(shop_view_q, timestamp__gte=week_start).count()
    shop_views_month = ScreenView.objects.filter(shop_view_q, timestamp__gte=month_start).count()
    
    # Tüm zamanlar için toplam salon görüntülenmesi
    shop_views_total = ScreenView.objects.filter(shop_view_q).count()
    
    # Eğer ScreenView verisi yoksa, toplam randevu sayısını göster (alternatif metrik)
    if shop_views_total == 0:
        try:
            from app.appointments.models import Appointment
            shop_views_total = Appointment.objects.all().count()
            # Not: Bu aslında randevu sayısı, ScreenView verisi henüz toplanmıyor
        except Exception:
            shop_views_total = 0
    
    # En çok kullanılan özellikler (son 30 gün)
    top_features = (
        FeatureUsage.objects.filter(timestamp__gte=month_start)
        .values("feature_type")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )
    # En çok görüntülenen ekranlar (son 30 gün)
    top_screens = (
        ScreenView.objects.filter(timestamp__gte=month_start)
        .values("screen_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )
    return {
        "map_loads_today": map_today,
        "map_loads_week": map_week,
        "map_loads_month": map_month,
        "app_opens_today": app_open_today,
        "app_opens_week": app_open_week,
        "app_opens_month": app_open_month,
        "shop_views_today": shop_views_today,
        "shop_views_week": shop_views_week,
        "shop_views_month": shop_views_month,
        "shop_views_total": shop_views_total,
        "top_features": list(top_features),
        "top_screens": list(top_screens),
    }


def _period_dates(period, month_param, today):
    """
    period: 'daily' | 'weekly' | 'monthly' | 'yearly' | 'all_time'
    month_param: 'YYYY-MM' veya None (sadece monthly'de kullanılır)
    Returns: (period_start, period_end, prev_period_start, prev_period_end) as date objects.
    """
    period_start = period_end = prev_period_start = prev_period_end = today
    if period == "daily":
        period_start = period_end = today
        prev_period_start = prev_period_end = today - timedelta(days=1)
    elif period == "weekly":
        period_end = today
        period_start = today - timedelta(days=6)
        prev_period_end = period_start - timedelta(days=1)
        prev_period_start = prev_period_end - timedelta(days=6)
    elif period == "monthly":
        if month_param:
            try:
                y, m = int(month_param[:4]), int(month_param[5:7])
                period_start = date(y, m, 1)
                _, last = calendar.monthrange(y, m)
                period_end = date(y, m, last)
                if period_end > today:
                    period_end = today
            except (ValueError, IndexError):
                period_start = date(today.year, today.month, 1)
                _, last = calendar.monthrange(today.year, today.month)
                period_end = min(date(today.year, today.month, last), today)
        else:
            period_start = date(today.year, today.month, 1)
            _, last = calendar.monthrange(today.year, today.month)
            period_end = min(date(today.year, today.month, last), today)
        # Önceki ay
        if period_start.month == 1:
            prev_period_start = date(period_start.year - 1, 12, 1)
            prev_period_end = date(period_start.year - 1, 12, 31)
        else:
            prev_period_start = date(period_start.year, period_start.month - 1, 1)
            _, last = calendar.monthrange(prev_period_start.year, prev_period_start.month)
            prev_period_end = date(prev_period_start.year, prev_period_start.month, last)
    elif period == "all_time":
        # Tüm zamanlar: İlk kayıt tarihinden bugüne kadar
        try:
            first_user = User.objects.filter(APP_USER_FILTER).order_by('created_at').first()
            if first_user and first_user.created_at:
                period_start = first_user.created_at.date()
            else:
                # Eğer hiç kullanıcı yoksa, bugünden 1 yıl öncesini al
                period_start = date(today.year - 1, 1, 1)
        except Exception:
            # Hata durumunda bugünden 1 yıl öncesini al
            period_start = date(today.year - 1, 1, 1)
        period_end = today
        # Önceki dönem: Tüm zamanlar için önceki dönem yok, aynı değerleri kullan
        prev_period_start = period_start
        prev_period_end = period_end
    else:  # yearly
        period_start = date(today.year, 1, 1)
        period_end = today
        prev_period_start = date(today.year - 1, 1, 1)
        prev_period_end = date(today.year - 1, 12, 31)
    return period_start, period_end, prev_period_start, prev_period_end


def _period_stats(period_start, period_end, now):
    """Seçili tarih aralığında kayıt, aktif kullanıcı, randevu, e-posta, yeni kuaför sayıları (uygulama kullanıcıları = staff hariç).

    Not: Analytics tabloları veya UserSession migrasyonları eksik olsa bile dashboard'un tamamen hata vermemesi için
    dış bağımlı tüm sorguları try/except ile sarıyoruz ve güvenli fallback olarak 0 döndürüyoruz.
    """
    start_dt = timezone.make_aware(datetime.combine(period_start, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(period_end, datetime.max.time()))
    if end_dt > now:
        end_dt = now
    base_users = User.objects.filter(APP_USER_FILTER)
    registrations = base_users.filter(
        created_at__date__gte=period_start,
        created_at__date__lte=period_end,
    ).count()

    # Aktif kullanıcılar: kırılım (auth vs guest) + net tahmin
    try:
        active_breakdown = _active_breakdown(start_date=period_start, end_date=period_end, app_type="main")
    except Exception as e:
        print(f"Error calculating active users for period: {e}")
        active_breakdown = {
            "auth_users": 0,
            "auth_devices": 0,
            "guest_devices": 0,
            "guest_only_devices": 0,
            "active_devices": 0,
            "net_active": 0,
        }
    appointments = Appointment.objects.filter(
        start_datetime__gte=start_dt,
        start_datetime__lte=end_dt,
    ).count()
    emails = get_email_count_for_range(period_start, period_end)
    barbershops_created = Barbershop.objects.filter(
        created_at__date__gte=period_start,
        created_at__date__lte=period_end,
    ).count()
    return {
        "registrations": registrations,
        # net "aktif kullanıcı" = giriş yapmış benzersiz kullanıcı + guest-only benzersiz cihaz
        "active_users": active_breakdown["net_active"],
        "active_auth_users": active_breakdown["auth_users"],
        "active_guest_only_devices": active_breakdown["guest_only_devices"],
        "active_devices": active_breakdown["active_devices"],
        "appointments": appointments,
        "emails": emails,
        "barbershops_created": barbershops_created,
    }


def _month_options(today, count=24):
    """Son count ay için {value: 'YYYY-MM', label: 'Ocak 2025'} listesi."""
    months_tr = [
        "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
        "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
    ]
    options = []
    y, m = today.year, today.month
    for _ in range(count):
        options.append({
            "value": f"{y:04d}-{m:02d}",
            "label": f"{months_tr[m - 1]} {y}",
        })
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    return options


def admin_dashboard_view(request):
    """Admin panelinde kullanıcı ve sistem istatistiklerini gösteren dashboard - Günlük/Haftalık/Aylık/Yıllık periyot ve ay seçimi."""
    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    # Son 7 gün = tam 7 gün (bugün dahil): (today - 6) 00:00 -> şimdi
    week_start_date = today - timedelta(days=6)
    month_ago = today - timedelta(days=30)
    year_ago = today - timedelta(days=365)

    # Periyot ve ay seçimi (GET)
    period = (request.GET.get("period") or "monthly").strip().lower()
    if period not in ("daily", "weekly", "monthly", "yearly", "all_time"):
        period = "monthly"
    selected_month = request.GET.get("month") or ""
    if period != "monthly":
        selected_month = ""

    period_start, period_end, prev_period_start, prev_period_end = _period_dates(period, selected_month or None, today)
    period_stats = _period_stats(period_start, period_end, now)
    prev_period_stats = _period_stats(prev_period_start, prev_period_end, now)

    def growth(current, previous):
        if previous == 0:
            return (100.0 if current > 0 else 0.0)
        return round(((current - previous) / previous) * 100, 2)

    period_growth = {
        "registrations": growth(period_stats["registrations"], prev_period_stats["registrations"]),
        "active_users": growth(period_stats["active_users"], prev_period_stats["active_users"]),
        "appointments": growth(period_stats["appointments"], prev_period_stats["appointments"]),
        "emails": growth(period_stats["emails"], prev_period_stats["emails"]),
        "barbershops_created": growth(period_stats["barbershops_created"], prev_period_stats["barbershops_created"]),
    }

    period_labels = {
        "daily": "Günlük",
        "weekly": "Haftalık",
        "monthly": "Aylık",
        "yearly": "Yıllık",
        "all_time": "Tüm Zamanlar",
    }
    period_label = period_labels.get(period, "Aylık")
    if period == "all_time":
        period_range_label = f"{period_start.strftime('%d.%m.%Y')} – {period_end.strftime('%d.%m.%Y')} (Tüm Zamanlar)"
        prev_period_range_label = "—"
    else:
        period_range_label = f"{period_start.strftime('%d.%m.%Y')} – {period_end.strftime('%d.%m.%Y')}"
        prev_period_range_label = f"{prev_period_start.strftime('%d.%m.%Y')} – {prev_period_end.strftime('%d.%m.%Y')}"
    month_options = _month_options(today, 24)

    # Helper functions
    def calculate_percentage(part, total):
        if total == 0:
            return 0.0
        return round((part / total) * 100, 2)

    def calculate_growth_rate(current, previous):
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 2)
    
    # ==================== KULLANICI İSTATİSTİKLERİ ====================
    
    # Temel kullanıcı sayıları (tüm hesaplar - staff dahil)
    user_stats = User.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
        banned=Count('id', filter=Q(is_active=False)),
        verified=Count('id', filter=Q(email_verified=True)),
        unverified=Count('id', filter=Q(email_verified=False)),
    )
    total_users = user_stats['total']
    active_users = user_stats['active']
    banned_users = user_stats['banned']
    verified_users = user_stats['verified']
    unverified_users = user_stats['unverified']

    # Uygulama kullanıcıları (staff/superuser hariç - gerçek mobil kullanıcı metrikleri)
    app_users_qs = User.objects.filter(APP_USER_FILTER)
    app_user_stats = app_users_qs.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
    )
    app_users_total = app_user_stats['total']
    app_users_active = app_user_stats['active']
    
    # Kayıt istatistikleri için tarih aralıkları (son 7 gün = tam 7 gün: week_start_date 00:00 -> şimdi)
    week_start = timezone.make_aware(datetime.combine(week_start_date, datetime.min.time()))
    month_start = timezone.make_aware(datetime.combine(month_ago, datetime.min.time()))
    
    # Aktif kullanıcı metrikleri (UserActivityLog):
    # - cihaz bazlı (geriye dönük uyumluluk)
    # - giriş yapmış vs giriş yapmadan devam eden kırılımı
    # - net aktif kullanıcı (auth user + guest-only device)
    today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    year_start = timezone.make_aware(datetime.combine(year_ago, datetime.min.time()))

    # epoch_date sabit olarak tanımla - date() fonksiyonunu loop değişkeni gölgelemez
    epoch_date = date(1970, 1, 1)

    try:
        daily_breakdown = _active_breakdown(start_date=today, end_date=today, app_type="main")
        weekly_breakdown = _active_breakdown(start_date=week_start_date, end_date=today, app_type="main")
        monthly_breakdown = _active_breakdown(start_date=month_ago, end_date=today, app_type="main")
        yearly_breakdown = _active_breakdown(start_date=year_ago, end_date=today, app_type="main")
        all_time_breakdown = _active_breakdown(start_date=epoch_date, end_date=today, app_type="main")

        # Cihaz bazlı metrikler (UserActivityLog)
        daily_active_users = daily_breakdown["active_devices"]
        weekly_active_users = weekly_breakdown["active_devices"]
        monthly_active_users = monthly_breakdown["active_devices"]
        yearly_active_users = yearly_breakdown["active_devices"]
        all_time_active_users = all_time_breakdown["active_devices"]

        # Net aktif kullanıcı tahmini
        daily_active_net = daily_breakdown["net_active"]
        weekly_active_net = weekly_breakdown["net_active"]
        monthly_active_net = monthly_breakdown["net_active"]
        yearly_active_net = yearly_breakdown["net_active"]
        all_time_active_net = all_time_breakdown["net_active"]

        # Kırılım
        daily_active_auth_users = daily_breakdown["auth_users"]
        weekly_active_auth_users = weekly_breakdown["auth_users"]
        monthly_active_auth_users = monthly_breakdown["auth_users"]
        yearly_active_auth_users = yearly_breakdown["auth_users"]
        all_time_active_auth_users = all_time_breakdown["auth_users"]

        daily_active_guest_only_devices = daily_breakdown["guest_only_devices"]
        weekly_active_guest_only_devices = weekly_breakdown["guest_only_devices"]
        monthly_active_guest_only_devices = monthly_breakdown["guest_only_devices"]
        yearly_active_guest_only_devices = yearly_breakdown["guest_only_devices"]
        all_time_active_guest_only_devices = all_time_breakdown["guest_only_devices"]

        # Fallback: UserActivityLog henüz veri içermiyorsa last_login bazlı hesapla
        if daily_active_users == 0 and weekly_active_users == 0:
            daily_active_auth_users = app_users_qs.filter(last_login__date=today).count()
            weekly_active_auth_users = app_users_qs.filter(last_login__gte=week_start).count()
            monthly_active_auth_users = app_users_qs.filter(last_login__gte=month_start).count()
            yearly_active_auth_users = app_users_qs.filter(last_login__gte=year_start).count()
            all_time_active_auth_users = app_users_qs.filter(last_login__isnull=False).count()
            daily_active_users = daily_active_auth_users
            weekly_active_users = weekly_active_auth_users
            monthly_active_users = monthly_active_auth_users
            yearly_active_users = yearly_active_auth_users
            all_time_active_users = all_time_active_auth_users
            daily_active_net = daily_active_auth_users
            weekly_active_net = weekly_active_auth_users
            monthly_active_net = monthly_active_auth_users
            yearly_active_net = yearly_active_auth_users
            all_time_active_net = all_time_active_auth_users
            daily_active_guest_only_devices = 0
            weekly_active_guest_only_devices = 0
            monthly_active_guest_only_devices = 0
            yearly_active_guest_only_devices = 0
            all_time_active_guest_only_devices = 0

    except Exception as e:
        print(f"Error calculating active users: {e}")
        # Fallback son çare: last_login bazlı
        try:
            daily_active_auth_users = app_users_qs.filter(last_login__date=today).count()
            weekly_active_auth_users = app_users_qs.filter(last_login__gte=week_start).count()
            monthly_active_auth_users = app_users_qs.filter(last_login__gte=month_start).count()
            yearly_active_auth_users = app_users_qs.filter(last_login__gte=year_start).count()
            all_time_active_auth_users = app_users_qs.filter(last_login__isnull=False).count()
        except Exception:
            daily_active_auth_users = weekly_active_auth_users = monthly_active_auth_users = 0
            yearly_active_auth_users = all_time_active_auth_users = 0
        daily_active_users = daily_active_auth_users
        weekly_active_users = weekly_active_auth_users
        monthly_active_users = monthly_active_auth_users
        yearly_active_users = yearly_active_auth_users
        all_time_active_users = all_time_active_auth_users
        daily_active_net = daily_active_auth_users
        weekly_active_net = weekly_active_auth_users
        monthly_active_net = monthly_active_auth_users
        yearly_active_net = yearly_active_auth_users
        all_time_active_net = all_time_active_auth_users
        daily_active_guest_only_devices = 0
        weekly_active_guest_only_devices = 0
        monthly_active_guest_only_devices = 0
        yearly_active_guest_only_devices = 0
        all_time_active_guest_only_devices = 0
    
    # Son 1 ay içerisinde uygulamaya girmeyen aktif kullanıcılar (uygulama kullanıcıları)
    inactive_last_month = app_users_qs.filter(
        Q(is_active=True) &
        (
            Q(last_login__lt=month_start) | 
            Q(last_login__isnull=True, updated_at__lt=month_start)
        )
    ).distinct().count()
    
    # Hiç giriş yapmamış aktif kullanıcılar (uygulama kullanıcıları)
    never_logged_in = app_users_qs.filter(
        last_login__isnull=True,
        is_active=True
    ).count()
    
    # Kayıt istatistikleri (sadece uygulama kullanıcıları - staff hariç)
    today_registrations = app_users_qs.filter(
        created_at__date=today
    ).count()
    
    week_registrations = app_users_qs.filter(
        created_at__gte=week_start
    ).count()
    
    month_registrations = app_users_qs.filter(
        created_at__gte=month_start
    ).count()
    
    # Yüzdeler hesaplama (payda: uygulama kullanıcı sayısı, böylece gerçek oran görünür)
    _denom = app_users_total if app_users_total > 0 else 1
    # Not: Guest kullanıcılar için doğru payda olmadığı için, yüzdeler sadece giriş yapmış (auth) kullanıcılar bazında hesaplanır.
    daily_active_percentage = calculate_percentage(daily_active_auth_users, _denom)
    weekly_active_percentage = calculate_percentage(weekly_active_auth_users, _denom)
    monthly_active_percentage = calculate_percentage(monthly_active_auth_users, _denom)
    yearly_active_percentage = calculate_percentage(yearly_active_auth_users, _denom)
    inactive_percentage = calculate_percentage(inactive_last_month, _denom)
    never_logged_percentage = calculate_percentage(never_logged_in, _denom)
    
    # ==================== GRAFİKLER (OPTİMİZE EDİLMİŞ) ====================
    
    # Son 7 günlük kayıt grafiği (database sorgusu ile)
    registration_chart = []
    max_registration_count = 0
    
    # Tek sorgu ile tüm günlerin kayıt sayılarını al (sadece uygulama kullanıcıları)
    registration_data = app_users_qs.filter(
        created_at__gte=timezone.make_aware(datetime.combine(today - timedelta(days=6), datetime.min.time()))
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Dictionary'ye çevir (hızlı erişim için)
    registration_dict = {item['date']: item['count'] for item in registration_data}
    
    for i in range(7):
        day = today - timedelta(days=6-i)
        count = registration_dict.get(day, 0)
        if count > max_registration_count:
            max_registration_count = count
        registration_chart.append({
            'date': day.strftime('%d.%m'),
            'count': count
        })
    
    # Son 30 günlük aktif kullanıcı grafiği (benzersiz cihaz bazlı)
    daily_active_chart = []
    max_daily_active = 0
    
    # UserActivityLog'dan günlük aktif kullanıcı verilerini toplu olarak al
    activity_data = UserActivityLog.objects.filter(
        activity_date__gte=today - timedelta(days=29),
        activity_date__lte=today,
        app_type='main'
    ).values('activity_date').annotate(
        count=Count('device_id', distinct=True)
    ).order_by('activity_date')
    
    # Dictionary'ye çevir (hızlı erişim için)
    activity_dict = {item['activity_date']: item['count'] for item in activity_data}
    
    # Her gün için veriyi chart'a ekle
    for i in range(30):
        day = today - timedelta(days=29-i)
        count = activity_dict.get(day, 0)
        
        if count > max_daily_active:
            max_daily_active = count
        daily_active_chart.append({
            'date': day.strftime('%d.%m'),
            'count': count
        })
    
    # ==================== BARBERSHOP İSTATİSTİKLERİ ====================
    
    # Barbershop istatistikleri (subscription durumu da dahil)
    barbershop_stats = Barbershop.objects.aggregate(
        total=Count('id'),
        approved=Count('id', filter=Q(is_approved=True, is_verified=True)),
        pending=Count('id', filter=Q(is_approved=False, is_verified=True)),
        rejected=Count('id', filter=Q(is_approved=False, is_verified=False, rejection_reason__isnull=False)),
    )
    
    total_barbershops = barbershop_stats['total']
    approved_barbershops = barbershop_stats['approved']
    pending_barbershops = barbershop_stats['pending']
    rejected_barbershops = barbershop_stats['rejected']
    
    # Aktif aboneliği olan barbershop sayısı
    active_subscription_shops = Barbershop.objects.filter(
        subscription__status__in=['trial', 'active', 'lifetime', 'grace_period'],
        is_approved=True,
        is_verified=True
    ).count()
    
    # ==================== RANDEVU İSTATİSTİKLERİ ====================
    
    try:
        appointment_stats = Appointment.objects.aggregate(
            total=Count('id'),
            today=Count('id', filter=Q(start_datetime__date=today)),
            this_week=Count('id', filter=Q(start_datetime__gte=week_start)),
            this_month=Count('id', filter=Q(start_datetime__gte=month_start)),
        )
        
        total_appointments = appointment_stats['total']
        today_appointments = appointment_stats['today']
        week_appointments = appointment_stats['this_week']
        month_appointments = appointment_stats['this_month']
        
        # Randevu durumları
        appointment_statuses = Appointment.objects.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
    except Exception as e:
        total_appointments = 0
        today_appointments = 0
        week_appointments = 0
        month_appointments = 0
        appointment_statuses = []
    
    # ==================== BÜYÜME VE TREND METRİKLERİ ====================
    
    # Önceki 7 günlük dönem (büyüme oranı için)
    prev_week_start_date = week_start_date - timedelta(days=7)
    prev_week_start = timezone.make_aware(datetime.combine(prev_week_start_date, datetime.min.time()))
    prev_week_end = week_start
    prev_week_registrations = app_users_qs.filter(
        created_at__gte=prev_week_start,
        created_at__lt=prev_week_end
    ).count()
    
    prev_month_start = timezone.make_aware(datetime.combine(month_ago - timedelta(days=30), datetime.min.time()))
    prev_month_end = month_start
    prev_month_registrations = app_users_qs.filter(
        created_at__gte=prev_month_start,
        created_at__lt=prev_month_end
    ).count()
    
    # Önceki dönem aktif kullanıcı sayıları (benzersiz cihaz bazlı, fallback: last_login)
    try:
        prev_week_start_date_obj = prev_week_start.date()
        prev_week_end_date_obj = prev_week_end.date()

        prev_week_daily_active = UserActivityLog.objects.filter(
            activity_date__gte=prev_week_start_date_obj,
            activity_date__lt=prev_week_end_date_obj,
            app_type='main'
        ).values('device_id').distinct().count()

        if prev_week_daily_active == 0:
            prev_week_daily_active = app_users_qs.filter(
                last_login__gte=prev_week_start,
                last_login__lt=prev_week_end,
            ).count()
    except Exception as e:
        print(f"Error calculating prev week active: {e}")
        prev_week_daily_active = 0

    try:
        prev_month_start_date_obj = prev_month_start.date()
        prev_month_end_date_obj = prev_month_end.date()

        prev_month_daily_active = UserActivityLog.objects.filter(
            activity_date__gte=prev_month_start_date_obj,
            activity_date__lt=prev_month_end_date_obj,
            app_type='main'
        ).values('device_id').distinct().count()

        if prev_month_daily_active == 0:
            prev_month_daily_active = app_users_qs.filter(
                last_login__gte=prev_month_start,
                last_login__lt=prev_month_end,
            ).count()
    except Exception as e:
        print(f"Error calculating prev month active: {e}")
        prev_month_daily_active = 0
    
    # Büyüme oranları
    week_growth_rate = calculate_growth_rate(week_registrations, prev_week_registrations)
    month_growth_rate = calculate_growth_rate(month_registrations, prev_month_registrations)
    daily_active_growth = calculate_growth_rate(daily_active_users, prev_week_daily_active)
    
    # ==================== GİRİŞ SIKLIĞI METRİKLERİ ====================
    
    # Günlük ortalama giriş sayısı (bugün giriş yapan kullanıcıların ortalama login_count'u)
    try:
        daily_login_frequency = UserActivityLog.objects.filter(
            activity_date=today,
            app_type='main'
        ).aggregate(avg_logins=Avg('login_count'))['avg_logins'] or 0.0
    except Exception:
        daily_login_frequency = 0.0
    
    # Haftalık ortalama giriş sayısı (son 7 günde aktif olan kullanıcıların toplam login sayısı / aktif kullanıcı sayısı)
    try:
        weekly_total_logins = UserActivityLog.objects.filter(
            activity_date__gte=week_start_date,
            activity_date__lte=today,
            app_type='main'
        ).aggregate(total=Sum('login_count'))['total'] or 0
        weekly_avg_logins = (weekly_total_logins / weekly_active_users) if weekly_active_users > 0 else 0.0
    except Exception:
        weekly_avg_logins = 0.0
    
    # Aylık ortalama giriş sayısı (son 30 günde aktif olan kullanıcıların toplam login sayısı / aktif kullanıcı sayısı)
    try:
        monthly_total_logins = UserActivityLog.objects.filter(
            activity_date__gte=month_ago,
            activity_date__lte=today,
            app_type='main'
        ).aggregate(total=Sum('login_count'))['total'] or 0
        monthly_avg_logins = (monthly_total_logins / monthly_active_users) if monthly_active_users > 0 else 0.0
    except Exception:
        monthly_avg_logins = 0.0
    
    # En sık giriş yapan kullanıcılar (son 30 gün)
    try:
        top_frequent_users_raw = UserActivityLog.objects.filter(
            activity_date__gte=month_ago,
            activity_date__lte=today,
            app_type='main',
            user__isnull=False
        ).values('user', 'user__email', 'user__full_name').annotate(
            total_logins=Sum('login_count'),
            days_active=Count('activity_date', distinct=True)
        ).order_by('-total_logins')[:10]
        
        # Ortalama giriş/gün hesapla
        top_frequent_users = []
        for item in top_frequent_users_raw:
            avg_per_day = round(item['total_logins'] / item['days_active'], 1) if item['days_active'] > 0 else 0
            top_frequent_users.append({
                'user__email': item['user__email'],
                'user__full_name': item['user__full_name'],
                'total_logins': item['total_logins'],
                'days_active': item['days_active'],
                'avg_per_day': avg_per_day,
            })
    except Exception:
        top_frequent_users = []
    
    # ==================== RETENTION VE CHURN METRİKLERİ (PROFESYONEL) ====================
    
    # 7-Day Retention (7 gün önce kayıt olanlardan hala aktif olanlar - Industry Standard)
    seven_days_ago_date = today - timedelta(days=7)
    try:
        users_registered_7_days_ago = app_users_qs.filter(
            created_at__date=seven_days_ago_date
        ).count()
        
        # 7 gün önce kayıt olanlardan son 7 günde aktif olanlar
        if users_registered_7_days_ago > 0:
            active_from_7_days_ago = UserActivityLog.objects.filter(
                user__created_at__date=seven_days_ago_date,
                activity_date__gte=seven_days_ago_date,
                activity_date__lte=today,
                app_type='main',
                user__isnull=False
            ).values('user').distinct().count()
        else:
            active_from_7_days_ago = 0
        
        day_7_retention_rate = calculate_percentage(active_from_7_days_ago, users_registered_7_days_ago) if users_registered_7_days_ago > 0 else 0.0
    except Exception:
        day_7_retention_rate = 0.0
        users_registered_7_days_ago = 0
        active_from_7_days_ago = 0
    
    # 30-Day Retention (30 gün önce kayıt olanlardan hala aktif olanlar - Long-term engagement)
    thirty_days_ago_date = today - timedelta(days=30)
    try:
        users_registered_30_days_ago = app_users_qs.filter(
            created_at__date=thirty_days_ago_date
        ).count()
        
        # 30 gün önce kayıt olanlardan son 30 günde aktif olanlar
        if users_registered_30_days_ago > 0:
            active_from_30_days_ago = UserActivityLog.objects.filter(
                user__created_at__date=thirty_days_ago_date,
                activity_date__gte=thirty_days_ago_date,
                activity_date__lte=today,
                app_type='main',
                user__isnull=False
            ).values('user').distinct().count()
        else:
            active_from_30_days_ago = 0
        
        day_30_retention_rate = calculate_percentage(active_from_30_days_ago, users_registered_30_days_ago) if users_registered_30_days_ago > 0 else 0.0
    except Exception:
        day_30_retention_rate = 0.0
        users_registered_30_days_ago = 0
        active_from_30_days_ago = 0
    
    # Monthly Churn Rate (Son 30 günde aktif olan ama son 7 günde hiç giriş yapmayan - Industry Standard)
    try:
        # Son 30 günde aktif olan kullanıcılar (ActivityLog + last_login fallback)
        active_in_last_30_days = UserActivityLog.objects.filter(
            activity_date__gte=month_ago,
            activity_date__lte=today,
            app_type='main',
            user__isnull=False
        ).values('user').distinct().count()

        active_in_last_7_days = UserActivityLog.objects.filter(
            activity_date__gte=week_start_date,
            activity_date__lte=today,
            app_type='main',
            user__isnull=False
        ).values('user').distinct().count()

        # Fallback: UserActivityLog boşsa last_login kullan
        if active_in_last_30_days == 0:
            active_in_last_30_days = app_users_qs.filter(last_login__gte=month_start).count()
            active_in_last_7_days = app_users_qs.filter(last_login__gte=week_start).count()

        # Churned = Son 30 günde aktif ama son 7 günde değil
        churned_users = max(active_in_last_30_days - active_in_last_7_days, 0)

        churn_rate = calculate_percentage(churned_users, active_in_last_30_days) if active_in_last_30_days > 0 else 0.0
    except Exception:
        churn_rate = 0.0
        churned_users = 0
        active_in_last_30_days = 0
    
    # Activation Rate (İlk 24 saat içinde giriş yapan kullanıcılar - Onboarding başarısı)
    try:
        # Son 7 günde kayıt olanlar (aktivasyon için yeterli zaman geçmiş)
        recent_registrations_for_activation = app_users_qs.filter(
            created_at__gte=now - timedelta(days=7),
            created_at__lt=now - timedelta(days=1)  # En az 1 gün geçmiş olmalı
        ).count()
        
        # Bu kullanıcılardan ilk 24 saat içinde aktif olanlar
        activated_users = 0
        if recent_registrations_for_activation > 0:
            for user in app_users_qs.filter(
                created_at__gte=now - timedelta(days=7),
                created_at__lt=now - timedelta(days=1)
            ).values('id', 'created_at'):
                first_day_end = user['created_at'] + timedelta(days=1)
                has_activity = UserActivityLog.objects.filter(
                    user_id=user['id'],
                    activity_date__gte=user['created_at'].date(),
                    activity_date__lte=first_day_end.date(),
                    app_type='main'
                ).exists()
                if has_activity:
                    activated_users += 1
        
        activation_rate = calculate_percentage(activated_users, recent_registrations_for_activation) if recent_registrations_for_activation > 0 else 0.0
    except Exception:
        activation_rate = 0.0
        activated_users = 0
        recent_registrations_for_activation = 0
    
    # ==================== DEMOGRAFİK ANALİZ ====================
    
    # Cinsiyet dağılımı (sadece uygulama kullanıcıları, aktif)
    gender_stats = app_users_qs.filter(is_active=True).values('gender').annotate(
        count=Count('id')
    ).order_by('-count')
    gender_distribution = {}
    for item in gender_stats:
        gender_key = item['gender'] if item['gender'] else 'belirtilmemiş'
        gender_distribution[gender_key] = item['count']
    
    # Şehir dağılımı (UserAddress - sadece uygulama kullanıcıları)
    city_stats = UserAddress.objects.filter(
        user__is_active=True,
        user__is_staff=False,
        user__is_superuser=False,
        city__isnull=False
    ).exclude(city='').values('city').annotate(
        count=Count('user', distinct=True)
    ).order_by('-count')[:10]
    city_distribution = [{'city': item['city'], 'count': item['count']} for item in city_stats]
    
    # ==================== ENGAGEMENT METRİKLERİ ====================
    
    # Favori ve yorum istatistikleri
    engagement_stats = Favorite.objects.aggregate(
        total_favorites=Count('id'),
        users_with_favorites=Count('user', distinct=True)
    )
    
    review_stats = Review.objects.aggregate(
        total_reviews=Count('id'),
        users_with_reviews=Count('user', distinct=True),
        avg_rating=Avg('rating')
    )
    
    total_favorites = engagement_stats['total_favorites']
    users_with_favorites = engagement_stats['users_with_favorites']
    total_reviews = review_stats['total_reviews']
    users_with_reviews = review_stats['users_with_reviews']
    avg_rating = review_stats['avg_rating'] or 0.0
    
    # Ortalama favori ve yorum sayıları
    avg_favorites_per_user = round(total_favorites / users_with_favorites, 2) if users_with_favorites > 0 else 0
    avg_reviews_per_user = round(total_reviews / users_with_reviews, 2) if users_with_reviews > 0 else 0
    
    # ==================== TOP KULLANICILAR ====================
    
    # En aktif uygulama kullanıcıları (son girişe göre)
    top_active_users = app_users_qs.filter(
        is_active=True,
        last_login__isnull=False
    ).order_by('-last_login')[:10].values('email', 'full_name', 'last_login', 'created_at')
    
    # ==================== HAFTALIK TREND ====================
    
    # Haftalık aktif kullanıcı trendi (son 4 hafta - benzersiz cihaz bazlı, UserActivityLog)
    weekly_active_trend = []
    for i in range(4):
        trend_week_end = today - timedelta(days=i*7)
        trend_week_start = trend_week_end - timedelta(days=6)

        try:
            count = UserActivityLog.objects.filter(
                activity_date__gte=trend_week_start,
                activity_date__lte=trend_week_end,
                app_type='main'
            ).values('device_id').distinct().count()
            if count == 0:
                # Fallback: last_login bazlı
                count = app_users_qs.filter(
                    last_login__date__gte=trend_week_start,
                    last_login__date__lte=trend_week_end,
                ).count()
        except Exception as e:
            print(f"Error calculating weekly trend: {e}")
            count = 0

        weekly_active_trend.append({
            'week': f"Hafta {4-i}",
            'count': count,
            'date_range': f"{trend_week_start.strftime('%d.%m')} - {trend_week_end.strftime('%d.%m')}"
        })
    
    max_weekly_active = max([w['count'] for w in weekly_active_trend]) if weekly_active_trend and any(w['count'] > 0 for w in weekly_active_trend) else 1
    
    # ==================== E-POSTA İSTATİSTİKLERİ (GÜNLÜK / HAFTALIK / AYLIK / YILLIK) ====================
    today_email_count = get_today_email_count()
    week_email_count = get_weekly_email_count()
    month_email_count = get_monthly_email_count()
    year_email_count = get_yearly_email_count()
    daily_email_alert_threshold = 400

    # ==================== KULLANIM / ANALYTICS (Harita, uygulama açılma, özellik/ekran) ====================
    usage_stats = _usage_stats(now, today, week_start_date, month_ago)
    
    # ==================== VERSİYON YÖNETİMİ ====================
    try:
        from app.core.models import AppVersion
        
        # Ana uygulama versiyonları
        main_android = AppVersion.objects.filter(
            platform='android', app_type='main', is_active=True
        ).order_by('-version_code').first()
        
        main_ios = AppVersion.objects.filter(
            platform='ios', app_type='main', is_active=True
        ).order_by('-version_code').first()
        
        # Partner uygulama versiyonları
        partner_android = AppVersion.objects.filter(
            platform='android', app_type='partner', is_active=True
        ).order_by('-version_code').first()
        
        partner_ios = AppVersion.objects.filter(
            platform='ios', app_type='partner', is_active=True
        ).order_by('-version_code').first()
        
        app_versions = {
            'main_android': main_android,
            'main_ios': main_ios,
            'partner_android': partner_android,
            'partner_ios': partner_ios,
        }
    except Exception as e:
        print(f"Error loading app versions: {e}")
        app_versions = {}
    
    # ==================== CONTEXT OLUŞTURMA ====================

    context = {
        **admin.site.each_context(request),
        "title": "Kuafora Dashboard",
        "period": period,
        "period_label": period_label,
        "period_range_label": period_range_label,
        "prev_period_range_label": prev_period_range_label,
        "period_start": period_start,
        "period_end": period_end,
        "period_stats": period_stats,
        "prev_period_stats": prev_period_stats,
        "period_growth": period_growth,
        "month_options": month_options,
        "selected_month": selected_month,
        "stats": {
            'users': {
                'total': total_users,
                'active': active_users,
                'banned': banned_users,
                'app_users_total': app_users_total,
                'app_users_active': app_users_active,
                'daily_active': daily_active_users,
                'weekly_active': weekly_active_users,
                'monthly_active': monthly_active_users,
                'yearly_active': yearly_active_users,
                'all_time_active': all_time_active_users,
                # Net aktif kullanıcı tahmini (auth user + guest-only device)
                'daily_active_net': daily_active_net,
                'weekly_active_net': weekly_active_net,
                'monthly_active_net': monthly_active_net,
                'yearly_active_net': yearly_active_net,
                'all_time_active_net': all_time_active_net,
                # Giriş kırılımı
                'daily_active_auth_users': daily_active_auth_users,
                'weekly_active_auth_users': weekly_active_auth_users,
                'monthly_active_auth_users': monthly_active_auth_users,
                'yearly_active_auth_users': yearly_active_auth_users,
                'all_time_active_auth_users': all_time_active_auth_users,
                'daily_active_guest_only_devices': daily_active_guest_only_devices,
                'weekly_active_guest_only_devices': weekly_active_guest_only_devices,
                'monthly_active_guest_only_devices': monthly_active_guest_only_devices,
                'yearly_active_guest_only_devices': yearly_active_guest_only_devices,
                'all_time_active_guest_only_devices': all_time_active_guest_only_devices,
                'inactive_last_month': inactive_last_month,
                'never_logged_in': never_logged_in,
                'daily_active_percentage': daily_active_percentage,
                'weekly_active_percentage': weekly_active_percentage,
                'monthly_active_percentage': monthly_active_percentage,
                'yearly_active_percentage': yearly_active_percentage,
                'inactive_percentage': inactive_percentage,
                'never_logged_percentage': never_logged_percentage,
                'today_registrations': today_registrations,
                'week_registrations': week_registrations,
                'month_registrations': month_registrations,
                'verified': verified_users,
                'unverified': unverified_users,
                # Büyüme ve trend metrikleri
                'week_growth_rate': week_growth_rate,
                'month_growth_rate': month_growth_rate,
                'daily_active_growth': daily_active_growth,
                # Retention & Churn (Professional Metrics)
                'day_7_retention_rate': day_7_retention_rate,
                'day_30_retention_rate': day_30_retention_rate,
                'churn_rate': churn_rate,
                'activation_rate': activation_rate,
                'churned_users': churned_users,
                # Dağılımlar
                'gender_distribution': gender_distribution,
                'city_distribution': city_distribution,
                # Engagement
                'total_favorites': total_favorites,
                'total_reviews': total_reviews,
                'users_with_favorites': users_with_favorites,
                'users_with_reviews': users_with_reviews,
                'avg_favorites_per_user': avg_favorites_per_user,
                'avg_reviews_per_user': avg_reviews_per_user,
                'avg_rating': round(avg_rating, 2) if avg_rating else 0.0,
                # Trend
                'weekly_active_trend': weekly_active_trend,
                'max_weekly_active': max_weekly_active,
                'has_weekly_active_trend': any(w['count'] > 0 for w in weekly_active_trend),
                # Top kullanıcılar
                'top_active_users': list(top_active_users),
                # Giriş sıklığı metrikleri
                'daily_login_frequency': round(daily_login_frequency, 1),
                'weekly_avg_logins': round(weekly_avg_logins, 1),
                'monthly_avg_logins': round(monthly_avg_logins, 1),
                'top_frequent_users': list(top_frequent_users),
            },
            'barbershops': {
                'total': total_barbershops,
                'approved': approved_barbershops,
                'pending': pending_barbershops,
                'rejected': rejected_barbershops,
                'active_subscription': active_subscription_shops,
            },
            'appointments': {
                'total': total_appointments,
                'today': today_appointments,
                'this_week': week_appointments,
                'this_month': month_appointments,
                'statuses': list(appointment_statuses),
            },
            'registration_chart': registration_chart,
            'max_registration_count': max_registration_count if max_registration_count > 0 else 1,
            'has_registration_trend': max_registration_count > 0,
            'daily_active_chart': daily_active_chart,
            'max_daily_active': max_daily_active if max_daily_active > 0 else 1,
            'has_daily_active_trend': max_daily_active > 0,
            'emails': {
                'today_count': today_email_count,
                'week_count': week_email_count,
                'month_count': month_email_count,
                'year_count': year_email_count,
                'alert_threshold': daily_email_alert_threshold,
                'over_threshold': today_email_count > daily_email_alert_threshold,
            },
            'usage': usage_stats,
            'app_versions': app_versions,
        }
    }
    
    return TemplateResponse(request, 'admin/dashboard.html', context)
