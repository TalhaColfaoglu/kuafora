from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime
from app.barbers.models import Barbershop
from app.barbers.views import _compute_shop_status


class Command(BaseCommand):
    help = "Precompute and cache today's effective status for all shops"

    def handle(self, *args, **options):
        now = timezone.localtime()
        count = 0
        for shop in Barbershop.objects.all().only('id'):
            _ = _compute_shop_status(shop.id, now)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Precomputed status for {count} shops"))


