import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.management import call_command
from app.barbers.models import OfficialHoliday


class Command(BaseCommand):
    help = "Automatically seed holidays for current and next year if missing"

    def handle(self, *args, **opts):
        current_year = timezone.now().year
        next_year = current_year + 1
        
        # Mevcut yıl için tatil sayısını kontrol et
        current_year_holidays = OfficialHoliday.objects.filter(year=current_year).count()
        next_year_holidays = OfficialHoliday.objects.filter(year=next_year).count()
        
        self.stdout.write(f"Current year ({current_year}) holidays: {current_year_holidays}")
        self.stdout.write(f"Next year ({next_year}) holidays: {next_year_holidays}")
        
        # Eksik tatilleri seed et
        if current_year_holidays < 6:  # TR'de 6 sabit tatil var
            self.stdout.write(f"Seeding holidays for current year ({current_year})...")
            call_command('seed_official_holidays', year=current_year, verbosity=0)
        else:
            self.stdout.write(f"Current year ({current_year}) holidays already exist")
            
        if next_year_holidays < 6:
            self.stdout.write(f"Seeding holidays for next year ({next_year})...")
            call_command('seed_official_holidays', year=next_year, verbosity=0)
        else:
            self.stdout.write(f"Next year ({next_year}) holidays already exist")
            
        self.stdout.write(self.style.SUCCESS("Auto-seed holidays completed"))