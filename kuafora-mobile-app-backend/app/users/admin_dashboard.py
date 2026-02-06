import calendar
from datetime import date, timedelta, datetime

from django.contrib import admin
from django.utils import timezone
from django.db.models import Count, Q, Avg, Sum, F
from django.template.response import TemplateResponse
from django.db.models.functions import TruncDate

from app.users.models import User, UserAddress
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


def _usage_stats(now, today, week_ago, month_ago):
    """Analytics tablolarından kullanım metrikleri: harita yükleme, uygulama açılma, en çok kullanılan özellikler/ekranlar."""
    try:
        from app.analytics.models import FeatureUsage, AppEvent, ScreenView
    except Exception:
        return {
            "map_loads_today": 0,
            "map_loads_week": 0,
            "map_loads_month": 0,
            "app_opens_today": 0,
            "app_opens_week": 0,
            "app_opens_month": 0,
            "top_features": [],
            "top_screens": [],
        }
    today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    week_start = timezone.make_aware(datetime.combine(week_ago, datetime.min.time()))
    month_start = timezone.make_aware(datetime.combine(month_ago, datetime.min.time()))
    # Harita yükleme (map_view) – FeatureUsage
    map_today = FeatureUsage.objects.filter(feature_type="map_view", timestamp__gte=today_start).count()
    map_week = FeatureUsage.objects.filter(feature_type="map_view", timestamp__gte=week_start).count()
    map_month = FeatureUsage.objects.filter(feature_type="map_view", timestamp__gte=month_start).count()
    # Uygulama açılma – AppEvent
    app_open_today = AppEvent.objects.filter(event_type="app_open", timestamp__gte=today_start).count()
    app_open_week = AppEvent.objects.filter(event_type="app_open", timestamp__gte=week_start).count()
    app_open_month = AppEvent.objects.filter(event_type="app_open", timestamp__gte=month_start).count()
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
        "top_features": list(top_features),
        "top_screens": list(top_screens),
    }


def _period_dates(period, month_param, today):
    """
    period: 'daily' | 'weekly' | 'monthly' | 'yearly'
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
    else:  # yearly
        period_start = date(today.year, 1, 1)
        period_end = today
        prev_period_start = date(today.year - 1, 1, 1)
        prev_period_end = date(today.year - 1, 12, 31)
    return period_start, period_end, prev_period_start, prev_period_end


def _period_stats(period_start, period_end, now):
    """Seçili tarih aralığında kayıt, aktif kullanıcı, randevu, e-posta, yeni kuaför sayıları (uygulama kullanıcıları = staff hariç)."""
    start_dt = timezone.make_aware(datetime.combine(period_start, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(period_end, datetime.max.time()))
    if end_dt > now:
        end_dt = now
    base_users = User.objects.filter(APP_USER_FILTER)
    registrations = base_users.filter(
        created_at__date__gte=period_start,
        created_at__date__lte=period_end,
    ).count()
    # Aktif kullanıcılar: last_login, updated_at veya analytics verilerini kullan
    # Önce analytics'ten aktif kullanıcıları bul
    try:
        from app.analytics.models import AppEvent
        active_from_analytics = AppEvent.objects.filter(
            timestamp__gte=start_dt,
            timestamp__lte=end_dt,
            user__isnull=False
        ).values('user').distinct().count()
    except Exception:
        active_from_analytics = 0
    
    # last_login veya updated_at bazlı aktif kullanıcılar
    active_from_db = base_users.filter(
        is_active=True
    ).filter(
        Q(last_login__gte=start_dt, last_login__lte=end_dt) |
        Q(last_login__isnull=True, updated_at__gte=start_dt, updated_at__lte=end_dt)
    ).distinct().count()
    
    # En yüksek değeri kullan (analytics daha doğru olabilir)
    active_users = max(active_from_db, active_from_analytics)
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
        "active_users": active_users,
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
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    year_ago = today - timedelta(days=365)

    # Periyot ve ay seçimi (GET)
    period = (request.GET.get("period") or "monthly").strip().lower()
    if period not in ("daily", "weekly", "monthly", "yearly"):
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
    }
    period_label = period_labels.get(period, "Aylık")
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
    
    # Kayıt istatistikleri için tarih aralıkları (önce tanımla)
    week_start = timezone.make_aware(datetime.combine(week_ago, datetime.min.time()))
    month_start = timezone.make_aware(datetime.combine(month_ago, datetime.min.time()))
    
    # Aktif kullanıcı metrikleri (last_login bazlı - yoksa updated_at veya analytics kullan)
    # Önce analytics verilerinden aktif kullanıcıları bulalım
    try:
        from app.analytics.models import AppEvent, FeatureUsage
        today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        year_start = timezone.make_aware(datetime.combine(year_ago, datetime.min.time()))
        
        # Analytics'ten aktif kullanıcıları bul
        daily_active_from_analytics = AppEvent.objects.filter(
            timestamp__gte=now - timedelta(hours=24),
            user__isnull=False
        ).values('user').distinct().count()
        
        weekly_active_from_analytics = AppEvent.objects.filter(
            timestamp__gte=week_start,
            user__isnull=False
        ).values('user').distinct().count()
        
        monthly_active_from_analytics = AppEvent.objects.filter(
            timestamp__gte=month_start,
            user__isnull=False
        ).values('user').distinct().count()
        
        yearly_active_from_analytics = AppEvent.objects.filter(
            timestamp__gte=year_start,
            user__isnull=False
        ).values('user').distinct().count()
    except Exception:
        daily_active_from_analytics = 0
        weekly_active_from_analytics = 0
        monthly_active_from_analytics = 0
        yearly_active_from_analytics = 0
    
    # last_login veya updated_at bazlı aktif kullanıcılar
    daily_active_users = app_users_qs.filter(
        is_active=True
    ).filter(
        Q(last_login__gte=now - timedelta(hours=24)) |
        Q(last_login__isnull=True, updated_at__gte=now - timedelta(hours=24))
    ).distinct().count()
    
    weekly_active_users = app_users_qs.filter(
        is_active=True
    ).filter(
        Q(last_login__gte=week_start) |
        Q(last_login__isnull=True, updated_at__gte=week_start)
    ).distinct().count()
    
    monthly_active_users = app_users_qs.filter(
        is_active=True
    ).filter(
        Q(last_login__gte=month_start) |
        Q(last_login__isnull=True, updated_at__gte=month_start)
    ).distinct().count()
    
    yearly_active_users = app_users_qs.filter(
        is_active=True
    ).filter(
        Q(last_login__gte=year_start) |
        Q(last_login__isnull=True, updated_at__gte=year_start)
    ).distinct().count()
    
    # Analytics verilerini de dahil et (daha doğru sonuç için)
    daily_active_users = max(daily_active_users, daily_active_from_analytics)
    weekly_active_users = max(weekly_active_users, weekly_active_from_analytics)
    monthly_active_users = max(monthly_active_users, monthly_active_from_analytics)
    yearly_active_users = max(yearly_active_users, yearly_active_from_analytics)
    
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
    daily_active_percentage = calculate_percentage(daily_active_users, _denom)
    weekly_active_percentage = calculate_percentage(weekly_active_users, _denom)
    monthly_active_percentage = calculate_percentage(monthly_active_users, _denom)
    yearly_active_percentage = calculate_percentage(yearly_active_users, _denom)
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
        date = today - timedelta(days=6-i)
        count = registration_dict.get(date, 0)
        if count > max_registration_count:
            max_registration_count = count
        registration_chart.append({
            'date': date.strftime('%d.%m'),
            'count': count
        })
    
    # Son 30 günlük aktif kullanıcı grafiği (OPTİMİZE EDİLMİŞ - database sorgusu)
    daily_active_chart = []
    max_daily_active = 0
    
    # Her gün için aktif kullanıcı sayısını database'den al (sadece uygulama kullanıcıları)
    # Analytics verilerini de kontrol et
    try:
        from app.analytics.models import AppEvent
    except Exception:
        AppEvent = None
    
    for i in range(30):
        date = today - timedelta(days=29-i)
        date_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        date_end = timezone.make_aware(datetime.combine(date, datetime.max.time()))
        
        # last_login veya updated_at bazlı
        count = app_users_qs.filter(
            is_active=True
        ).filter(
            Q(last_login__gte=date_start, last_login__lte=date_end) |
            Q(last_login__isnull=True, updated_at__gte=date_start, updated_at__lte=date_end)
        ).distinct().count()
        
        # Analytics'ten de kontrol et
        if AppEvent:
            analytics_count = AppEvent.objects.filter(
                timestamp__gte=date_start,
                timestamp__lte=date_end,
                user__isnull=False
            ).values('user').distinct().count()
            count = max(count, analytics_count)
        
        if count > max_daily_active:
            max_daily_active = count
        daily_active_chart.append({
            'date': date.strftime('%d.%m'),
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
    
    # Önceki dönem karşılaştırması (büyüme oranı için)
    prev_week_start = timezone.make_aware(datetime.combine(week_ago - timedelta(days=7), datetime.min.time()))
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
    
    # Önceki dönem aktif kullanıcı sayıları (uygulama kullanıcıları)
    prev_week_daily_active = app_users_qs.filter(
        is_active=True
    ).filter(
        Q(last_login__gte=prev_week_start, last_login__lt=prev_week_end) |
        Q(last_login__isnull=True, updated_at__gte=prev_week_start, updated_at__lt=prev_week_end)
    ).distinct().count()
    
    prev_month_daily_active = app_users_qs.filter(
        is_active=True
    ).filter(
        Q(last_login__gte=prev_month_start, last_login__lt=prev_month_end) |
        Q(last_login__isnull=True, updated_at__gte=prev_month_start, updated_at__lt=prev_month_end)
    ).distinct().count()
    
    # Analytics'ten de kontrol et
    try:
        from app.analytics.models import AppEvent
        prev_week_from_analytics = AppEvent.objects.filter(
            timestamp__gte=prev_week_start,
            timestamp__lt=prev_week_end,
            user__isnull=False
        ).values('user').distinct().count()
        prev_week_daily_active = max(prev_week_daily_active, prev_week_from_analytics)
        
        prev_month_from_analytics = AppEvent.objects.filter(
            timestamp__gte=prev_month_start,
            timestamp__lt=prev_month_end,
            user__isnull=False
        ).values('user').distinct().count()
        prev_month_daily_active = max(prev_month_daily_active, prev_month_from_analytics)
    except Exception:
        pass
    
    # Büyüme oranları
    week_growth_rate = calculate_growth_rate(week_registrations, prev_week_registrations)
    month_growth_rate = calculate_growth_rate(month_registrations, prev_month_registrations)
    daily_active_growth = calculate_growth_rate(daily_active_users, prev_week_daily_active)
    
    # ==================== RETENTION VE CHURN METRİKLERİ ====================
    
    # Retention Rate (Tutma Oranı) - Bu hafta kayıt olanların kaçı hala aktif (uygulama kullanıcıları)
    week_retention_users = app_users_qs.filter(
        created_at__gte=week_start,
        is_active=True
    ).filter(
        Q(last_login__gte=now - timedelta(days=7)) |
        Q(last_login__isnull=True, updated_at__gte=now - timedelta(days=7))
    ).distinct().count()
    
    # Analytics'ten de kontrol et
    try:
        from app.analytics.models import AppEvent
        week_retention_from_analytics = AppEvent.objects.filter(
            user__created_at__gte=week_start,
            timestamp__gte=now - timedelta(days=7),
            user__isnull=False
        ).values('user').distinct().count()
        week_retention_users = max(week_retention_users, week_retention_from_analytics)
    except Exception:
        pass
    
    week_retention_rate = calculate_percentage(week_retention_users, week_registrations) if week_registrations > 0 else 0.0
    
    # Churn Rate (Ayrılma Oranı) - Son 30 günde kayıt olup son 7 günde giriş yapmayanlar
    churned_users = app_users_qs.filter(
        Q(created_at__gte=month_start) &
        Q(is_active=True) &
        (
            Q(last_login__lt=now - timedelta(days=7)) | 
            Q(last_login__isnull=True, updated_at__lt=now - timedelta(days=7))
        )
    ).distinct().count()
    churn_rate = calculate_percentage(churned_users, month_registrations) if month_registrations > 0 else 0.0
    
    # Conversion Rate - Kayıt olanların aktif kullanıcıya dönüşme oranı
    converted_users = app_users_qs.filter(
        created_at__gte=month_start,
        is_active=True
    ).filter(
        Q(last_login__isnull=False) |
        Q(last_login__isnull=True, updated_at__gt=F('created_at'))
    ).distinct().count()
    
    # Analytics'ten de kontrol et
    try:
        from app.analytics.models import AppEvent
        converted_from_analytics = AppEvent.objects.filter(
            user__created_at__gte=month_start,
            user__isnull=False
        ).values('user').distinct().count()
        converted_users = max(converted_users, converted_from_analytics)
    except Exception:
        pass
    
    conversion_rate = calculate_percentage(converted_users, month_registrations) if month_registrations > 0 else 0.0
    
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
    
    # Haftalık aktif kullanıcı trendi (son 4 hafta - DOĞRU HESAPLAMA)
    weekly_active_trend = []
    try:
        from app.analytics.models import AppEvent
    except Exception:
        AppEvent = None
    
    for i in range(4):
        week_end = today - timedelta(days=i*7)
        week_start = week_end - timedelta(days=6)
        week_start_dt = timezone.make_aware(datetime.combine(week_start, datetime.min.time()))
        week_end_dt = timezone.make_aware(datetime.combine(week_end, datetime.max.time()))
        
        count = app_users_qs.filter(
            is_active=True
        ).filter(
            Q(last_login__gte=week_start_dt, last_login__lte=week_end_dt) |
            Q(last_login__isnull=True, updated_at__gte=week_start_dt, updated_at__lte=week_end_dt)
        ).distinct().count()
        
        # Analytics'ten de kontrol et
        if AppEvent:
            analytics_count = AppEvent.objects.filter(
                timestamp__gte=week_start_dt,
                timestamp__lte=week_end_dt,
                user__isnull=False
            ).values('user').distinct().count()
            count = max(count, analytics_count)
        
        weekly_active_trend.append({
            'week': f"Hafta {4-i}",
            'count': count,
            'date_range': f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}"
        })
    
    max_weekly_active = max([w['count'] for w in weekly_active_trend]) if weekly_active_trend and any(w['count'] > 0 for w in weekly_active_trend) else 1
    
    # ==================== E-POSTA İSTATİSTİKLERİ (GÜNLÜK / HAFTALIK / AYLIK / YILLIK) ====================
    today_email_count = get_today_email_count()
    week_email_count = get_weekly_email_count()
    month_email_count = get_monthly_email_count()
    year_email_count = get_yearly_email_count()
    daily_email_alert_threshold = 400

    # ==================== KULLANIM / ANALYTICS (Harita, uygulama açılma, özellik/ekran) ====================
    usage_stats = _usage_stats(now, today, week_ago, month_ago)
    
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
                'week_retention_rate': week_retention_rate,
                'churn_rate': churn_rate,
                'conversion_rate': conversion_rate,
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
        }
    }
    
    return TemplateResponse(request, 'admin/dashboard.html', context)
