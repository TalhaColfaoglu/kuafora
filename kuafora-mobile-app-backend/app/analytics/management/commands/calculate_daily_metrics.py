"""
Management command to calculate and store daily metrics
Run daily via cron: python manage.py calculate_daily_metrics
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Q, Avg
from datetime import datetime, timedelta, date

from app.users.models import User
from app.analytics.models import DailyMetrics, UserActivityLog
from app.barbers.models import Barbershop
from app.appointments.models import Appointment


class Command(BaseCommand):
    help = 'Calculate and store daily metrics for dashboard'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Specific date to calculate (YYYY-MM-DD). Default: yesterday',
        )
        parser.add_argument(
            '--backfill',
            type=int,
            help='Backfill metrics for the last N days',
        )

    def handle(self, *args, **options):
        if options.get('backfill'):
            # Backfill son N gün için metrikleri hesapla
            days = options['backfill']
            self.stdout.write(f"Backfilling metrics for last {days} days...")
            today = timezone.now().date()
            for i in range(days):
                target_date = today - timedelta(days=i)
                self.calculate_metrics_for_date(target_date)
        elif options.get('date'):
            # Belirli bir gün için hesapla
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
                self.calculate_metrics_for_date(target_date)
            except ValueError:
                self.stderr.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
        else:
            # Default: dün için hesapla
            yesterday = timezone.now().date() - timedelta(days=1)
            self.calculate_metrics_for_date(yesterday)

    def calculate_metrics_for_date(self, target_date):
        """Belirli bir gün için tüm metrikleri hesapla ve kaydet"""
        self.stdout.write(f"Calculating metrics for {target_date}...")
        
        # Tarih aralıkları
        day_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
        day_end = timezone.make_aware(datetime.combine(target_date, datetime.max.time()))
        
        week_start_date = target_date - timedelta(days=6)
        week_start = timezone.make_aware(datetime.combine(week_start_date, datetime.min.time()))
        
        month_start_date = target_date - timedelta(days=29)
        month_start = timezone.make_aware(datetime.combine(month_start_date, datetime.min.time()))
        
        year_start_date = target_date - timedelta(days=364)
        year_start = timezone.make_aware(datetime.combine(year_start_date, datetime.min.time()))
        
        # Uygulama kullanıcıları filtresi
        APP_USER_FILTER = Q(is_staff=False, is_superuser=False)
        app_users = User.objects.filter(APP_USER_FILTER)
        
        # Kullanıcı metrikleri
        total_users = User.objects.count()
        app_users_total = app_users.count()
        
        # O gün aktif kullanıcılar (UserActivityLog'dan)
        daily_active_users = UserActivityLog.objects.filter(
            activity_date=target_date,
            app_type='main'
        ).values('device_id').distinct().count()
        
        # O gün kayıt olan kullanıcılar
        daily_registrations = app_users.filter(
            created_at__gte=day_start,
            created_at__lte=day_end
        ).count()
        
        # 7 günlük aktif kullanıcılar
        weekly_active_users = UserActivityLog.objects.filter(
            activity_date__gte=week_start_date,
            activity_date__lte=target_date,
            app_type='main'
        ).values('device_id').distinct().count()
        
        # 7 günlük kayıtlar
        weekly_registrations = app_users.filter(
            created_at__gte=week_start,
            created_at__lte=day_end
        ).count()
        
        # 30 günlük aktif kullanıcılar
        monthly_active_users = UserActivityLog.objects.filter(
            activity_date__gte=month_start_date,
            activity_date__lte=target_date,
            app_type='main'
        ).values('device_id').distinct().count()
        
        # 30 günlük kayıtlar
        monthly_registrations = app_users.filter(
            created_at__gte=month_start,
            created_at__lte=day_end
        ).count()
        
        # 365 günlük aktif kullanıcılar
        yearly_active_users = UserActivityLog.objects.filter(
            activity_date__gte=year_start_date,
            activity_date__lte=target_date,
            app_type='main'
        ).values('device_id').distinct().count()
        
        # 365 günlük kayıtlar
        yearly_registrations = app_users.filter(
            created_at__gte=year_start,
            created_at__lte=day_end
        ).count()
        
        # Barbershop metrikleri
        total_barbershops = Barbershop.objects.filter(
            created_at__lte=day_end
        ).count()
        
        approved_barbershops = Barbershop.objects.filter(
            created_at__lte=day_end,
            is_approved=True,
            is_verified=True
        ).count()
        
        # Randevu metrikleri
        total_appointments = Appointment.objects.filter(
            created_at__lte=day_end
        ).count()
        
        daily_appointments = Appointment.objects.filter(
            start_datetime__gte=day_start,
            start_datetime__lte=day_end
        ).count()
        
        # Retention rate: Son 7 gün kayıt olanların kaçı hala aktif
        week_ago_registrations = app_users.filter(
            created_at__gte=week_start,
            created_at__lte=day_end
        ).count()
        
        if week_ago_registrations > 0:
            # O hafta kayıt olup hala aktif olanlar
            retained_users = UserActivityLog.objects.filter(
                user__created_at__gte=week_start,
                user__created_at__lte=day_end,
                activity_date__gte=target_date - timedelta(days=6),
                activity_date__lte=target_date,
                user__is_staff=False,
                user__is_superuser=False,
                app_type='main'
            ).values('user').distinct().count()
            retention_rate = round((retained_users / week_ago_registrations) * 100, 2)
        else:
            retention_rate = 0.0
        
        # Churn rate: Son 30 gün kayıt olup son 7 günde giriş yapmayanlar
        if monthly_registrations > 0:
            churned = app_users.filter(
                created_at__gte=month_start,
                created_at__lte=day_end,
                is_active=True
            ).exclude(
                id__in=UserActivityLog.objects.filter(
                    activity_date__gte=target_date - timedelta(days=6),
                    activity_date__lte=target_date,
                    user__isnull=False
                ).values_list('user_id', flat=True)
            ).count()
            churn_rate = round((churned / monthly_registrations) * 100, 2)
        else:
            churn_rate = 0.0
        
        # Conversion rate: Son 30 gün kayıt olanların aktif kullanıcıya dönüşme oranı
        if monthly_registrations > 0:
            converted = UserActivityLog.objects.filter(
                user__created_at__gte=month_start,
                user__created_at__lte=day_end,
                user__is_staff=False,
                user__is_superuser=False,
                activity_date__lte=target_date,
                app_type='main'
            ).values('user').distinct().count()
            conversion_rate = round((converted / monthly_registrations) * 100, 2)
        else:
            conversion_rate = 0.0
        
        # DailyMetrics kaydı oluştur veya güncelle
        metrics, created = DailyMetrics.objects.update_or_create(
            date=target_date,
            defaults={
                'total_users': total_users,
                'app_users_total': app_users_total,
                'daily_active_users': daily_active_users,
                'daily_registrations': daily_registrations,
                'weekly_active_users': weekly_active_users,
                'weekly_registrations': weekly_registrations,
                'monthly_active_users': monthly_active_users,
                'monthly_registrations': monthly_registrations,
                'yearly_active_users': yearly_active_users,
                'yearly_registrations': yearly_registrations,
                'total_barbershops': total_barbershops,
                'approved_barbershops': approved_barbershops,
                'total_appointments': total_appointments,
                'daily_appointments': daily_appointments,
                'retention_rate': retention_rate,
                'churn_rate': churn_rate,
                'conversion_rate': conversion_rate,
            }
        )
        
        action = 'Created' if created else 'Updated'
        self.stdout.write(
            self.style.SUCCESS(
                f'{action} metrics for {target_date}: '
                f'DAU={daily_active_users}, WAU={weekly_active_users}, MAU={monthly_active_users}'
            )
        )
