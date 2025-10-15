from django.core.management.base import BaseCommand
from app.barbers.models import OfficialHoliday


TR_STATIC = {
    # Ay-gün sabit resmi günler (yıl bağımsız)
    (1, 1): ("Yılbaşı", "national"),
    (4, 23): ("Ulusal Egemenlik ve Çocuk Bayramı", "national"),
    (5, 1): ("Emek ve Dayanışma Günü", "national"),
    (5, 19): ("Atatürk’ü Anma, Gençlik ve Spor Bayramı", "national"),
    (8, 30): ("Zafer Bayramı", "national"),
    (10, 29): ("Cumhuriyet Bayramı", "national"),
}


class Command(BaseCommand):
    help = "Seed TR official holidays for a given year (static + optional movable days)"

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, required=True)

    def handle(self, *args, **opts):
        year = int(opts['year'])
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

        # Hareketli dini bayramlar (opsiyonel):
        # İhtiyaca göre bir takvim servisi entegre edilebilir.
        # Şimdilik bu komut yalnızca sabit günleri doldurur.

        self.stdout.write(self.style.SUCCESS(f"Seeded TR holidays for {year} (created={created}, updated={updated})"))


