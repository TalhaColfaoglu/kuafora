from django.core.management.base import BaseCommand
from django.utils import timezone
from app.barbers.models import OfficialHoliday


TR_2025 = [
    ("2025-01-01", "Yılbaşı", "national"),
    ("2025-03-29", "Ramazan Bayramı Arefesi", "religious"),
    ("2025-03-30", "Ramazan Bayramı 1. Gün", "religious"),
    ("2025-03-31", "Ramazan Bayramı 2. Gün", "religious"),
    ("2025-04-01", "Ramazan Bayramı 3. Gün", "religious"),
    ("2025-04-23", "Ulusal Egemenlik ve Çocuk Bayramı", "national"),
    ("2025-05-01", "Emek ve Dayanışma Günü", "national"),
    ("2025-05-19", "Atatürk’ü Anma, Gençlik ve Spor Bayramı", "national"),
    ("2025-06-05", "Kurban Bayramı Arefesi", "religious"),
    ("2025-06-06", "Kurban Bayramı 1. Gün", "religious"),
    ("2025-06-07", "Kurban Bayramı 2. Gün", "religious"),
    ("2025-06-08", "Kurban Bayramı 3. Gün", "religious"),
    ("2025-06-09", "Kurban Bayramı 4. Gün", "religious"),
    ("2025-07-15", "Demokrasi ve Millî Birlik Günü", "national"),
    ("2025-08-30", "Zafer Bayramı", "national"),
    ("2025-10-29", "Cumhuriyet Bayramı", "national"),
]


class Command(BaseCommand):
    help = "Seed TR 2025 official holidays"

    def handle(self, *args, **options):
        created, updated = 0, 0
        for d, name, typ in TR_2025:
            obj, is_created = OfficialHoliday.objects.update_or_create(
                country_code='TR',
                date=d,
                defaults={
                    'name': name,
                    'type': typ,
                    'year': 2025,
                }
            )
            if is_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded official holidays 2025 (created={created}, updated={updated})"))


