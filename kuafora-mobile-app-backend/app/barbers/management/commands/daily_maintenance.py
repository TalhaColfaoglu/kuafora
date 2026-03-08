import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.management import call_command
from app.barbers.models import OfficialHoliday, DailyOverride, SpecialMessage


class Command(BaseCommand):
    help = "Daily maintenance tasks: seed holidays, clean expired overrides, precompute status"

    def handle(self, *args, **opts):
        self.stdout.write("Starting daily maintenance...")
        
        # 1. Otomatik tatil seed (mevcut yıl ve gelecek yıl)
        self.stdout.write("1. Checking and seeding holidays...")
        call_command('auto_seed_holidays', verbosity=0)
        
        # 2. Süresi dolmuş DailyOverride'ları temizle
        self.stdout.write("2. Cleaning expired daily overrides...")
        expired_count = DailyOverride.objects.filter(
            expires_at__lt=timezone.now()
        ).count()
        if expired_count > 0:
            DailyOverride.objects.filter(
                expires_at__lt=timezone.now()
            ).delete()
            self.stdout.write(f"  Cleaned {expired_count} expired daily overrides")
        else:
            self.stdout.write("  No expired daily overrides found")
        
        # 3. Süresi dolmuş otomatik duyuruları temizle (izin günü geçtikten sonra)
        self.stdout.write("3. Cleaning expired automatic announcements...")
        now = timezone.now()
        expired_messages = SpecialMessage.objects.filter(
            source='automatic',
            end_datetime__lt=now
        )
        expired_msg_count = expired_messages.count()
        if expired_msg_count > 0:
            expired_messages.delete()
            self.stdout.write(f"  Cleaned {expired_msg_count} expired automatic announcements")
        else:
            self.stdout.write("  No expired automatic announcements found")
        
        # 4. Takım sayısı 0 olan salonları sil (kimse giriş yapıp düzenleyemiyor)
        self.stdout.write("4. Deleting barbershops with zero staff...")
        call_command('delete_zero_staff_barbershops', verbosity=1)

        # 5. Status precompute (gelecek 30 gün)
        self.stdout.write("5. Precomputing shop statuses...")
        call_command('precompute_day_status', days=30, verbosity=0)
        
        # 6. Duyurular (yaklaşan tatiller)
        self.stdout.write("6. Checking for upcoming announcements...")
        call_command('announce_calendar', mode='upcoming', verbosity=0)
        
        # 7. Bugünkü duyurular (00:01'de çalışacak)
        current_time = timezone.now()
        if current_time.hour == 0 and current_time.minute < 5:  # Gece yarısından sonra 5 dakika içinde
            self.stdout.write("7. Activating today's announcements...")
            call_command('announce_calendar', mode='today', verbosity=0)
            
            # 1 hafta önce duyurularını aktif et
            self.stdout.write("8. Activating 1-week-before announcements...")
            one_week_from_now = now + datetime.timedelta(days=7)
            one_week_messages = SpecialMessage.objects.filter(
                source='automatic',
                is_active=False,
                start_datetime__date=one_week_from_now.date()
            )
            activated_count = one_week_messages.update(is_active=True)
            if activated_count > 0:
                self.stdout.write(f"  Activated {activated_count} 1-week-before announcements")
        else:
            self.stdout.write("7. Skipping today's announcements (not midnight)")
        
        self.stdout.write(self.style.SUCCESS("Daily maintenance completed successfully"))