import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.management import call_command
from app.barbers.models import OfficialHoliday, DailyOverride


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
        
        # 3. Status precompute (gelecek 30 gün)
        self.stdout.write("3. Precomputing shop statuses...")
        call_command('precompute_day_status', days=30, verbosity=0)
        
        # 4. Duyurular (yaklaşan tatiller)
        self.stdout.write("4. Checking for upcoming announcements...")
        call_command('announce_calendar', mode='upcoming', verbosity=0)
        
        # 5. Bugünkü duyurular (00:01'de çalışacak)
        current_time = timezone.now()
        if current_time.hour == 0 and current_time.minute < 5:  # Gece yarısından sonra 5 dakika içinde
            self.stdout.write("5. Sending today's announcements...")
            call_command('announce_calendar', mode='today', verbosity=0)
        else:
            self.stdout.write("5. Skipping today's announcements (not midnight)")
        
        self.stdout.write(self.style.SUCCESS("Daily maintenance completed successfully"))