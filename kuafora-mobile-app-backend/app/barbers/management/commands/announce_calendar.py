import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.barbers.models import OfficialHoliday, Override, SpecialMessage, Barbershop, Staff
from app.barbers.views import _compute_shop_status

class Command(BaseCommand):
    help = 'Sends automated announcements for upcoming and today\'s calendar events.'

    def add_arguments(self, parser):
        parser.add_argument('--mode', type=str, choices=['today', 'upcoming'], required=True,
                            help='Announcement mode: "today" for 00:01 announcements, "upcoming" for T-3 announcements.')

    def handle(self, *args, **options):
        mode = options['mode']
        today = timezone.now().date()

        if mode == 'today':
            self.stdout.write(self.style.SUCCESS(f'Checking for today\'s announcements ({today})...'))
            # 00:01: daha önce planlanan otomatik mesajları aktif et
            activated = SpecialMessage.objects.filter(
                source='automatic',
                is_active=False,
                start_datetime__date=today
            ).update(is_active=True)
            if activated:
                self.stdout.write(self.style.SUCCESS(f'  Activated {activated} scheduled messages for today'))
            for shop in Barbershop.objects.all():
                status_data = _compute_shop_status(shop.id, today)
                if status_data['status'] == 'closed' and status_data['source'] in ['SPECIAL_DAY', 'OFFICIAL_HOLIDAY', 'TOGGLE']:
                    message_title = "Bugün Salon Kapalı"
                    message_content = status_data['message'] or "Özel bir durum nedeniyle bugün kapalıyız."
                    if not SpecialMessage.objects.filter(
                        barbershop=shop,
                        source='automatic',
                        title=message_title,
                        start_datetime__date=today
                    ).exists():
                        SpecialMessage.objects.create(
                            barbershop=shop,
                            source='automatic',
                            display_type='banner',
                            target_type='all_shop',
                            title=message_title,
                            content=message_content,
                            start_datetime=timezone.now(),
                            end_datetime=timezone.now() + datetime.timedelta(days=1),
                            is_active=True,
                        )
                        self.stdout.write(self.style.SUCCESS(f'  Sent "Today Closed" announcement for {shop.name}.'))

        elif mode == 'upcoming':
            self.stdout.write(self.style.SUCCESS(f'Checking for upcoming announcements ({today})...'))
            three_days_later = today + datetime.timedelta(days=3)
            for shop in Barbershop.objects.all():
                upcoming_holidays = OfficialHoliday.objects.filter(date=three_days_later)
                for holiday in upcoming_holidays:
                    status_data = _compute_shop_status(shop.id, holiday.date)
                    if status_data['status'] == 'closed' and status_data['source'] in ['SPECIAL_DAY', 'OFFICIAL_HOLIDAY']:
                        message_title = "Yaklaşan Tatil Duyurusu"
                        message_content = f"{holiday.name} tatili {holiday.date.strftime('%d %B')} tarihinde. Salonumuz kapalı olacaktır."
                        if not SpecialMessage.objects.filter(
                            barbershop=shop,
                            source='automatic',
                            title=message_title,
                            start_datetime__date=today,
                            content__icontains=holiday.name
                        ).exists():
                            SpecialMessage.objects.create(
                                barbershop=shop,
                                source='automatic',
                                display_type='banner',
                                target_type='all_shop',
                                title=message_title,
                                content=message_content,
                                start_datetime=timezone.now(),
                                end_datetime=timezone.now() + datetime.timedelta(days=4),
                                is_active=True,
                            )
                            self.stdout.write(self.style.SUCCESS(f'  Sent "Upcoming Holiday" announcement for {shop.name} - {holiday.name}.'))

        self.stdout.write(self.style.SUCCESS(f'Finished checking for {mode} announcements.'))