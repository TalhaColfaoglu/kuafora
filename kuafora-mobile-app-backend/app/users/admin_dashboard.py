import calendar
from datetime import date, timedelta, datetime

from django.contrib import admin
from django.utils import timezone
from django.db.models import Count, Q, Avg, Sum
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
    """Seçili tarih aralığında kayıt, aktif kullanıcı, randevu, e-posta, yeni kuaför sayıları."""
    start_dt = timezone.make_aware(datetime.combine(period_start, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(period_end, datetime.max.time()))
    if end_dt > now:
        end_dt = now
    registrations = User.objects.filter(
        created_at__date__gte=period_start,
        created_at__date__lte=period_end,
    ).count()
    active_users = User.objects.filter(
        is_active=True,
        last_login__gte=start_dt,
        last_login__lte=end_dt,
    ).count()
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
    
    # Temel kullanıcı sayıları (optimize edilmiş - tek sorgu)
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
    
    # Aktif kullanıcı metrikleri (last_login bazlı)
    daily_active_users = User.objects.filter(
        last_login__gte=now - timedelta(hours=24),
        is_active=True
    ).count()
    
    weekly_active_users = User.objects.filter(
        last_login__gte=now - timedelta(days=7),
        is_active=True
    ).count()
    
    monthly_active_users = User.objects.filter(
        last_login__gte=now - timedelta(days=30),
        is_active=True
    ).count()
    
    yearly_active_users = User.objects.filter(
        last_login__gte=now - timedelta(days=365),
        is_active=True
    ).count()
    
    # Son 1 ay içerisinde uygulamaya girmeyen aktif kullanıcılar
    inactive_last_month = User.objects.filter(
        Q(is_active=True) &
        (Q(last_login__lt=now - timedelta(days=30)) | Q(last_login__isnull=True))
    ).count()
    
    # Hiç giriş yapmamış aktif kullanıcılar
    never_logged_in = User.objects.filter(
        last_login__isnull=True,
        is_active=True
    ).count()
    
    # Kayıt istatistikleri (DOĞRU TARİH HESAPLAMALARI)
    week_start = timezone.make_aware(datetime.combine(week_ago, datetime.min.time()))
    month_start = timezone.make_aware(datetime.combine(month_ago, datetime.min.time()))
    
    today_registrations = User.objects.filter(
        created_at__date=today
    ).count()
    
    week_registrations = User.objects.filter(
        created_at__gte=week_start
    ).count()
    
    month_registrations = User.objects.filter(
        created_at__gte=month_start
    ).count()
    
    # Yüzdeler hesaplama
    daily_active_percentage = calculate_percentage(daily_active_users, total_users)
    weekly_active_percentage = calculate_percentage(weekly_active_users, total_users)
    monthly_active_percentage = calculate_percentage(monthly_active_users, total_users)
    yearly_active_percentage = calculate_percentage(yearly_active_users, total_users)
    inactive_percentage = calculate_percentage(inactive_last_month, total_users)
    never_logged_percentage = calculate_percentage(never_logged_in, total_users)
    
    # ==================== GRAFİKLER (OPTİMİZE EDİLMİŞ) ====================
    
    # Son 7 günlük kayıt grafiği (database sorgusu ile)
    registration_chart = []
    max_registration_count = 0
    
    # Tek sorgu ile tüm günlerin kayıt sayılarını al
    registration_data = User.objects.filter(
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
    
    # Her gün için aktif kullanıcı sayısını database'den al (doğru ve hızlı)
    for i in range(30):
        date = today - timedelta(days=29-i)
        date_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        date_end = timezone.make_aware(datetime.combine(date, datetime.max.time()))
        
        # Database sorgusu ile (in-memory filtering yerine)
        count = User.objects.filter(
            is_active=True,
            last_login__gte=date_start,
            last_login__lte=date_end
        ).count()
        
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
    prev_week_registrations = User.objects.filter(
        created_at__gte=prev_week_start,
        created_at__lt=prev_week_end
    ).count()
    
    prev_month_start = timezone.make_aware(datetime.combine(month_ago - timedelta(days=30), datetime.min.time()))
    prev_month_end = month_start
    prev_month_registrations = User.objects.filter(
        created_at__gte=prev_month_start,
        created_at__lt=prev_month_end
    ).count()
    
    # Önceki dönem aktif kullanıcı sayıları
    prev_week_daily_active = User.objects.filter(
        last_login__gte=prev_week_start,
        last_login__lt=prev_week_end,
        is_active=True
    ).count()
    
    prev_month_daily_active = User.objects.filter(
        last_login__gte=prev_month_start,
        last_login__lt=prev_month_end,
        is_active=True
    ).count()
    
    # Büyüme oranları
    week_growth_rate = calculate_growth_rate(week_registrations, prev_week_registrations)
    month_growth_rate = calculate_growth_rate(month_registrations, prev_month_registrations)
    daily_active_growth = calculate_growth_rate(daily_active_users, prev_week_daily_active)
    
    # ==================== RETENTION VE CHURN METRİKLERİ ====================
    
    # Retention Rate (Tutma Oranı) - Bu hafta kayıt olanların kaçı hala aktif
    week_retention_users = User.objects.filter(
        created_at__gte=week_start,
        last_login__gte=now - timedelta(days=7),
        is_active=True
    ).count()
    week_retention_rate = calculate_percentage(week_retention_users, week_registrations) if week_registrations > 0 else 0.0
    
    # Churn Rate (Ayrılma Oranı) - Son 30 günde kayıt olup son 7 günde giriş yapmayanlar
    churned_users = User.objects.filter(
        Q(created_at__gte=month_start) &
        (Q(last_login__lt=now - timedelta(days=7)) | Q(last_login__isnull=True)) &
        Q(is_active=True)
    ).count()
    churn_rate = calculate_percentage(churned_users, month_registrations) if month_registrations > 0 else 0.0
    
    # Conversion Rate - Kayıt olanların aktif kullanıcıya dönüşme oranı
    converted_users = User.objects.filter(
        created_at__gte=month_start,
        last_login__isnull=False,
        is_active=True
    ).count()
    conversion_rate = calculate_percentage(converted_users, month_registrations) if month_registrations > 0 else 0.0
    
    # ==================== DEMOGRAFİK ANALİZ ====================
    
    # Cinsiyet dağılımı (sadece aktif kullanıcılar)
    gender_stats = User.objects.filter(is_active=True).values('gender').annotate(
        count=Count('id')
    ).order_by('-count')
    gender_distribution = {}
    for item in gender_stats:
        gender_key = item['gender'] if item['gender'] else 'belirtilmemiş'
        gender_distribution[gender_key] = item['count']
    
    # Şehir dağılımı (UserAddress'ten - optimize edilmiş)
    city_stats = UserAddress.objects.filter(
        user__is_active=True,
        city__isnull=False
    ).exclude(city='').values('city').annotate(
        count=Count('user', distinct=True)
    ).order_by('-count')[:10]  # Top 10 şehir
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
    
    # En aktif kullanıcılar (son giriş zamanına göre - gerçek aktivite tracking yok)
    top_active_users = User.objects.filter(
        is_active=True,
        last_login__isnull=False
    ).order_by('-last_login')[:10].values('email', 'full_name', 'last_login', 'created_at')
    
    # ==================== HAFTALIK TREND ====================
    
    # Haftalık aktif kullanıcı trendi (son 4 hafta - DOĞRU HESAPLAMA)
    weekly_active_trend = []
    for i in range(4):
        week_end = today - timedelta(days=i*7)
        week_start = week_end - timedelta(days=6)
        week_start_dt = timezone.make_aware(datetime.combine(week_start, datetime.min.time()))
        week_end_dt = timezone.make_aware(datetime.combine(week_end, datetime.max.time()))
        
        count = User.objects.filter(
            last_login__gte=week_start_dt,
            last_login__lte=week_end_dt,
            is_active=True
        ).count()
        
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
            'daily_active_chart': daily_active_chart,
            'max_daily_active': max_daily_active if max_daily_active > 0 else 1,
            'emails': {
                'today_count': today_email_count,
                'week_count': week_email_count,
                'month_count': month_email_count,
                'year_count': year_email_count,
                'alert_threshold': daily_email_alert_threshold,
                'over_threshold': today_email_count > daily_email_alert_threshold,
            },
        }
    }
    
    return TemplateResponse(request, 'admin/dashboard.html', context)
