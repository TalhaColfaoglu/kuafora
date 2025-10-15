from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime, time
from app.barbers.models import ShopHolidayOverride, SpecialMessage, Barbershop


class Command(BaseCommand):
    help = "Announce upcoming holidays (T-3) and today's closures (00:01)"

    def add_arguments(self, parser):
        parser.add_argument('--mode', choices=['upcoming', 'today'], default='upcoming')

    def handle(self, *args, **opts):
        mode = opts['mode']
        now = timezone.localtime()
        if mode == 'today':
            target = now.date()
            qs = ShopHolidayOverride.objects.filter(date=target, status='closed')
            created = 0
            for o in qs:
                title = 'Bugün salon kapalı'
                content = o.note or o.title or ''
                start_dt = timezone.make_aware(datetime.combine(target, time(0, 1)))
                end_dt = timezone.make_aware(datetime.combine(target, time(23, 59)))
                SpecialMessage.objects.get_or_create(
                    barbershop=o.barbershop,
                    title=title,
                    defaults={
                        'source': 'automatic',
                        'display_type': 'banner',
                        'target_type': 'all_shop',
                        'content': content,
                        'start_datetime': start_dt,
                        'end_datetime': end_dt,
                        'is_active': True,
                    }
                )
                created += 1
            self.stdout.write(self.style.SUCCESS(f"Announced today's closures for {created} shops"))
        else:
            target = now.date() + timedelta(days=3)
            qs = ShopHolidayOverride.objects.filter(date=target, status='closed')
            created = 0
            for o in qs:
                title = 'Yaklaşan tatil'
                content = o.title or o.note or ''
                start_dt = timezone.make_aware(datetime.combine(now.date(), time(9, 0)))
                end_dt = timezone.make_aware(datetime.combine(target, time(0, 0)))
                SpecialMessage.objects.get_or_create(
                    barbershop=o.barbershop,
                    title=title,
                    defaults={
                        'source': 'automatic',
                        'display_type': 'banner',
                        'target_type': 'all_shop',
                        'content': content,
                        'start_datetime': start_dt,
                        'end_datetime': end_dt,
                        'is_active': True,
                    }
                )
                created += 1
            self.stdout.write(self.style.SUCCESS(f"Announced upcoming holidays for {created} shops"))


