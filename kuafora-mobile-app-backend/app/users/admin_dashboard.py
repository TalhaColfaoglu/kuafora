from django.contrib import admin
from django.utils import timezone
from django.db.models import Count, Q, Avg, Max, Min
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.db.models.functions import TruncDate
from datetime import timedelta, datetime
from app.users.models import User, UserAddress
from app.barbers.models import Barbershop, Favorite, Review
from app.appointments.models import Appointment


def admin_dashboard_view(request):
    """Admin panelinde kullanıcı ve sistem istatistiklerini gösteren dashboard"""
    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    year_ago = today - timedelta(days=365)
    
    # Kullanıcı istatistikleri
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    banned_users = User.objects.filter(is_active=False).count()
    
    # Aktif kullanıcı metrikleri (last_login bazlı)
    # Günlük aktif kullanıcı (son 24 saatte login olanlar)
    daily_active_users = User.objects.filter(
        last_login__gte=now - timedelta(hours=24),
        is_active=True
    ).count()
    
    # Haftalık aktif kullanıcı (son 7 günde login olanlar)
    weekly_active_users = User.objects.filter(
        last_login__gte=now - timedelta(days=7),
        is_active=True
    ).count()
    
    # Aylık aktif kullanıcı (son 30 günde login olanlar)
    monthly_active_users = User.objects.filter(
        last_login__gte=now - timedelta(days=30),
        is_active=True
    ).count()
    
    # Yıllık aktif kullanıcı (son 365 günde login olanlar)
    yearly_active_users = User.objects.filter(
        last_login__gte=now - timedelta(days=365),
        is_active=True
    ).count()
    
    # Son 1 ay içerisinde uygulamaya girmeyen kullanıcılar
    inactive_last_month = User.objects.filter(
        (Q(last_login__lt=now - timedelta(days=30)) | Q(last_login__isnull=True)) & Q(is_active=True)
    ).count()
    
    # Hiç giriş yapmamış kullanıcılar
    never_logged_in = User.objects.filter(
        last_login__isnull=True,
        is_active=True
    ).count()
    
    # Bugün kayıt olanlar
    today_registrations = User.objects.filter(
        created_at__date=today
    ).count()
    
    # Bu hafta kayıt olanlar
    week_registrations = User.objects.filter(
        created_at__gte=timezone.make_aware(datetime.combine(week_ago, datetime.min.time()))
    ).count()
    
    # Bu ay kayıt olanlar
    month_registrations = User.objects.filter(
        created_at__gte=timezone.make_aware(datetime.combine(month_ago, datetime.min.time()))
    ).count()
    
    # Yüzdeler hesaplama
    def calculate_percentage(part, total):
        if total == 0:
            return 0.0
        return round((part / total) * 100, 2)
    
    daily_active_percentage = calculate_percentage(daily_active_users, total_users)
    weekly_active_percentage = calculate_percentage(weekly_active_users, total_users)
    monthly_active_percentage = calculate_percentage(monthly_active_users, total_users)
    yearly_active_percentage = calculate_percentage(yearly_active_users, total_users)
    inactive_percentage = calculate_percentage(inactive_last_month, total_users)
    never_logged_percentage = calculate_percentage(never_logged_in, total_users)
    
    # Son 7 günlük kayıt grafiği için
    registration_chart = []
    max_registration_count = 0
    for i in range(7):
        date = today - timedelta(days=6-i)
        count = User.objects.filter(
            created_at__date=date
        ).count()
        if count > max_registration_count:
            max_registration_count = count
        registration_chart.append({
            'date': date.strftime('%d.%m'),
            'count': count
        })
    
    # Son 30 günlük aktif kullanıcı grafiği (optimize edilmiş)
    daily_active_chart = []
    max_daily_active = 0
    # Tüm aktif kullanıcıları bir kerede çek (optimizasyon)
    active_users_with_login = User.objects.filter(
        is_active=True,
        last_login__isnull=False
    ).values_list('last_login', flat=True)
    
    for i in range(30):
        date = today - timedelta(days=29-i)
        date_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        date_end = timezone.make_aware(datetime.combine(date, datetime.max.time()))
        # In-memory filtering (daha hızlı)
        count = sum(1 for login_time in active_users_with_login 
                   if date_start <= login_time <= date_end)
        if count > max_daily_active:
            max_daily_active = count
        daily_active_chart.append({
            'date': date.strftime('%d.%m'),
            'count': count
        })
    
    # Barbershop istatistikleri
    total_barbershops = Barbershop.objects.count()
    approved_barbershops = Barbershop.objects.filter(is_approved=True, is_verified=True).count()
    pending_barbershops = Barbershop.objects.filter(is_approved=False, is_verified=True).count()
    rejected_barbershops = Barbershop.objects.filter(is_approved=False, is_verified=False).count()
    
    # Randevu istatistikleri (varsa)
    try:
        total_appointments = Appointment.objects.count()
        today_appointments = Appointment.objects.filter(
            start_datetime__date=today
        ).count()
    except:
        total_appointments = 0
        today_appointments = 0
    
    # Email doğrulama istatistikleri
    verified_users = User.objects.filter(email_verified=True).count()
    unverified_users = User.objects.filter(email_verified=False).count()
    
    # Önceki dönem karşılaştırması (büyüme oranı için)
    prev_week_start = timezone.make_aware(datetime.combine(week_ago - timedelta(days=7), datetime.min.time()))
    prev_week_end = timezone.make_aware(datetime.combine(week_ago, datetime.max.time()))
    prev_week_registrations = User.objects.filter(
        created_at__gte=prev_week_start,
        created_at__lt=prev_week_end
    ).count()
    
    prev_month_start = timezone.make_aware(datetime.combine(month_ago - timedelta(days=30), datetime.min.time()))
    prev_month_end = timezone.make_aware(datetime.combine(month_ago, datetime.max.time()))
    prev_month_registrations = User.objects.filter(
        created_at__gte=prev_month_start,
        created_at__lt=prev_month_end
    ).count()
    
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
    
    # Büyüme oranları hesaplama
    def calculate_growth_rate(current, previous):
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 2)
    
    week_growth_rate = calculate_growth_rate(week_registrations, prev_week_registrations)
    month_growth_rate = calculate_growth_rate(month_registrations, prev_month_registrations)
    daily_active_growth = calculate_growth_rate(daily_active_users, prev_week_daily_active)
    
    # Retention Rate (Tutma Oranı) - Bu hafta kayıt olanların kaçı hala aktif
    week_retention_users = User.objects.filter(
        created_at__gte=timezone.make_aware(datetime.combine(week_ago, datetime.min.time())),
        last_login__gte=now - timedelta(days=7),
        is_active=True
    ).count()
    week_retention_rate = calculate_percentage(week_retention_users, week_registrations) if week_registrations > 0 else 0.0
    
    # Churn Rate (Ayrılma Oranı) - Son 30 günde kayıt olup son 7 günde giriş yapmayanlar
    churned_users = User.objects.filter(
        Q(created_at__gte=timezone.make_aware(datetime.combine(month_ago, datetime.min.time()))) &
        (Q(last_login__lt=now - timedelta(days=7)) | Q(last_login__isnull=True)) &
        Q(is_active=True)
    ).count()
    churn_rate = calculate_percentage(churned_users, month_registrations) if month_registrations > 0 else 0.0
    
    # Conversion Rate - Kayıt olanların aktif kullanıcıya dönüşme oranı
    converted_users = User.objects.filter(
        created_at__gte=timezone.make_aware(datetime.combine(month_ago, datetime.min.time())),
        last_login__isnull=False,
        is_active=True
    ).count()
    conversion_rate = calculate_percentage(converted_users, month_registrations) if month_registrations > 0 else 0.0
    
    # Cinsiyet dağılımı
    gender_stats = User.objects.filter(is_active=True).values('gender').annotate(
        count=Count('id')
    ).order_by('-count')
    gender_distribution = {}
    for item in gender_stats:
        gender_distribution[item['gender'] or 'belirtilmemiş'] = item['count']
    
    # Şehir dağılımı (UserAddress'ten)
    city_stats = UserAddress.objects.filter(
        user__is_active=True,
        city__isnull=False
    ).exclude(city='').values('city').annotate(
        count=Count('user', distinct=True)
    ).order_by('-count')[:10]  # Top 10 şehir
    city_distribution = [{'city': item['city'], 'count': item['count']} for item in city_stats]
    
    # Engagement metrikleri
    total_favorites = Favorite.objects.count()
    total_reviews = Review.objects.count()
    users_with_favorites = Favorite.objects.values('user').distinct().count()
    users_with_reviews = Review.objects.values('user').distinct().count()
    
    # Ortalama favori sayısı (favori ekleyen kullanıcılar için)
    avg_favorites_per_user = round(total_favorites / users_with_favorites, 2) if users_with_favorites > 0 else 0
    avg_reviews_per_user = round(total_reviews / users_with_reviews, 2) if users_with_reviews > 0 else 0
    
    # En aktif kullanıcılar (son 7 günde en çok giriş yapanlar - last_login bazlı, gerçek aktivite tracking yok)
    # Şimdilik son giriş zamanına göre sıralıyoruz
    top_active_users = User.objects.filter(
        is_active=True,
        last_login__isnull=False
    ).order_by('-last_login')[:10].values('email', 'full_name', 'last_login', 'created_at')
    
    # Haftalık aktif kullanıcı trendi (son 4 hafta)
    weekly_active_trend = []
    for i in range(4):
        week_start = today - timedelta(days=(3-i)*7 + 6)
        week_end = today - timedelta(days=(3-i)*7)
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
    
    max_weekly_active = max([w['count'] for w in weekly_active_trend]) if weekly_active_trend else 1
    
    context = {
        **admin.site.each_context(request),
        'title': 'Kuafora Dashboard',
        'stats': {
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
            },
            'appointments': {
                'total': total_appointments,
                'today': today_appointments,
            },
            'registration_chart': registration_chart,
            'max_registration_count': max_registration_count if max_registration_count > 0 else 1,
            'daily_active_chart': daily_active_chart,
            'max_daily_active': max_daily_active if max_daily_active > 0 else 1,
        }
    }
    
    return TemplateResponse(request, 'admin/dashboard.html', context)
