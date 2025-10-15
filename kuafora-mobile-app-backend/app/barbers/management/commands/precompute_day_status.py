import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.barbers.models import Barbershop
from app.barbers.views import _compute_shop_status

class Command(BaseCommand):
    help = 'Precomputes and caches shop statuses for upcoming days.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30,
                            help='Number of upcoming days to precompute status for.')

    def handle(self, *args, **options):
        num_days = options['days']
        self.stdout.write(self.style.SUCCESS(f'Precomputing shop statuses for the next {num_days} days...'))

        today = timezone.now().date()
        for shop in Barbershop.objects.all():
            for i in range(num_days):
                date = today + datetime.timedelta(days=i)
                _compute_shop_status(shop.id, date, force_recompute=True)
                self.stdout.write(self.style.SUCCESS(f'  Precomputed status for {shop.name} on {date}.'))

        self.stdout.write(self.style.SUCCESS(f'Finished precomputing shop statuses.'))