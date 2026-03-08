"""
Personel sayısı 0 olan salonları siler.
Bu salonlara kimse giriş yapıp düzenleyemediği için otomatik temizlenir.
Cron ile günlük çalıştırılabilir veya daily_maintenance içinden çağrılır.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count

from app.barbers.models import Barbershop


class Command(BaseCommand):
    help = "Takım sayısı 0 olan barbershop'ları siler (kimse giriş yapıp düzenleyemiyor)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Sadece silinecek salonları listele, silme.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        qs = Barbershop.objects.annotate(_staff_count=Count("staff")).filter(_staff_count=0)
        to_delete = list(qs.values_list("id", "name", "city"))
        count = len(to_delete)

        if count == 0:
            self.stdout.write("Personel sayısı 0 olan salon yok.")
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry-run: {count} salon silinecek (silinmeyecek):"))
            for pk, name, city in to_delete:
                self.stdout.write(f"  id={pk} name={name!r} city={city or '-'}")
            return

        for pk, name, city in to_delete:
            self.stdout.write(f"Siliniyor: id={pk} name={name!r} city={city or '-'}")
        Barbershop.objects.filter(id__in=[x[0] for x in to_delete]).delete()
        self.stdout.write(self.style.SUCCESS(f"{count} salon silindi."))
