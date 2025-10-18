import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.barbers.models import OfficialHoliday


TR_STATIC = {
    # Ay-gün sabit resmi günler (yıl bağımsız)
    (1, 1): ("Yılbaşı", "national"),
    (4, 23): ("Ulusal Egemenlik ve Çocuk Bayramı", "national"),
    (5, 1): ("Emek ve Dayanışma Günü", "national"),
    (5, 19): ("Atatürk'ü Anma, Gençlik ve Spor Bayramı", "national"),
    (8, 30): ("Zafer Bayramı", "national"),
    (10, 29): ("Cumhuriyet Bayramı", "national"),
}

# Opsiyonel: bazı yıllar için dini bayram tarihleri (örnek 2025)
TR_RELIGIOUS_BY_YEAR = {
    2025: [
        (3, 29, "Ramazan Bayramı Arefesi", "religious"),
        (3, 30, "Ramazan Bayramı 1. Gün", "religious"),
        (3, 31, "Ramazan Bayramı 2. Gün", "religious"),
        (4, 1,  "Ramazan Bayramı 3. Gün", "religious"),
        (6, 5,  "Kurban Bayramı Arefesi", "religious"),
        (6, 6,  "Kurban Bayramı 1. Gün", "religious"),
        (6, 7,  "Kurban Bayramı 2. Gün", "religious"),
        (6, 8,  "Kurban Bayramı 3. Gün", "religious"),
        (6, 9,  "Kurban Bayramı 4. Gün", "religious"),
    ]
}


class Command(BaseCommand):
    help = "Seed TR official holidays automatically for current and next year"

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Specific year to seed (default: auto)')
        parser.add_argument('--auto', action='store_true', help='Auto-seed current and next year')

    def handle(self, *args, **opts):
        if opts.get('year'):
            # Manuel yıl belirtilmişse
            years = [opts['year']]
        else:
            # Otomatik: mevcut yıl ve gelecek yıl
            current_year = timezone.now().year
            years = [current_year, current_year + 1]
            self.stdout.write(f"Auto-seeding holidays for years: {years}")

        total_created, total_updated = 0, 0
        
        for year in years:
            created, updated = self._seed_year(year)
            total_created += created
            total_updated += updated

        self.stdout.write(self.style.SUCCESS(
            f"Seeded TR holidays for {len(years)} year(s) (total created={total_created}, updated={total_updated})"
        ))

    def _seed_year(self, year):
        """Belirli bir yıl için tatilleri seed et"""
        created, updated = 0, 0
        
        # Sabit günler
        for (month, day), (name, typ) in TR_STATIC.items():
            date_str = f"{year:04d}-{month:02d}-{day:02d}"
            obj, is_created = OfficialHoliday.objects.update_or_create(
                country_code='TR',
                date=date_str,
                defaults={'name': name, 'type': typ, 'year': year}
            )
            if is_created:
                created += 1
            else:
                updated += 1

        # Dini bayramlar (varsa o yıl için kaydet)
        for (month, day, name, typ) in TR_RELIGIOUS_BY_YEAR.get(year, []):
            date_str = f"{year:04d}-{month:02d}-{day:02d}"
            obj, is_created = OfficialHoliday.objects.update_or_create(
                country_code='TR',
                date=date_str,
                defaults={'name': name, 'type': typ, 'year': year}
            )
            if is_created:
                created += 1
            else:
                updated += 1

        # Hareketli dini bayramlar (opsiyonel):
        # İhtiyaca göre bir takvim servisi entegre edilebilir.
        # Şimdilik bu komut yalnızca sabit günleri doldurur.

        self.stdout.write(f"  Year {year}: created={created}, updated={updated}")
        return created, updated


