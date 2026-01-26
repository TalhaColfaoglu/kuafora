from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from app.barbers.models import Override
from app.notifications.models import Notification
from app.barbers.models import Staff


class Command(BaseCommand):
    help = "Send reminders for upcoming leave days (1 week before and 1 day before)"

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Process once and exit')

    def handle(self, *args, **options):
        once = options.get('once')
        
        while True:
            try:
                today = timezone.localdate()
                one_week_later = today + timedelta(days=7)
                one_day_later = today + timedelta(days=1)
                
                # Find overrides that start in 1 week or 1 day
                overrides_1_week = Override.objects.filter(
                    start_date=one_week_later,
                    is_active=True
                )
                
                overrides_1_day = Override.objects.filter(
                    start_date=one_day_later,
                    is_active=True
                )
                
                sent_count = 0
                
                # Send 1 week before reminders
                for ov in overrides_1_week:
                    if ov.override_type == 'staff_individual' and ov.staff_id:
                        # Check if notification already sent
                        if not Notification.objects.filter(
                            user=ov.staff.user,
                            type='system',
                            reference_id=f"override_{ov.id}_reminder_1week"
                        ).exists():
                            Notification.objects.create(
                                user=ov.staff.user,
                                title="İzin Günü Hatırlatması",
                                body=f"1 hafta sonra ({ov.start_date.strftime('%d.%m.%Y')}) izinlisiniz. {ov.reason or ''}",
                                type='system',
                                reference_id=f"override_{ov.id}_reminder_1week"
                            )
                            sent_count += 1
                    elif ov.override_type == 'shop_global':
                        # Send to all staff
                        for staff_member in Staff.objects.filter(barbershop=ov.barbershop, is_active=True):
                            if not Notification.objects.filter(
                                user=staff_member.user,
                                type='system',
                                reference_id=f"override_{ov.id}_reminder_1week"
                            ).exists():
                                Notification.objects.create(
                                    user=staff_member.user,
                                    title="Salon İzin Günü Hatırlatması",
                                    body=f"1 hafta sonra ({ov.start_date.strftime('%d.%m.%Y')}) salon kapalı olacaktır. {ov.reason or ''}",
                                    type='system',
                                    reference_id=f"override_{ov.id}_reminder_1week"
                                )
                                sent_count += 1
                
                # Send 1 day before reminders
                for ov in overrides_1_day:
                    if ov.override_type == 'staff_individual' and ov.staff_id:
                        # Check if notification already sent
                        if not Notification.objects.filter(
                            user=ov.staff.user,
                            type='system',
                            reference_id=f"override_{ov.id}_reminder_1day"
                        ).exists():
                            Notification.objects.create(
                                user=ov.staff.user,
                                title="İzin Günü Hatırlatması",
                                body=f"Yarın ({ov.start_date.strftime('%d.%m.%Y')}) izinlisiniz. {ov.reason or ''}",
                                type='system',
                                reference_id=f"override_{ov.id}_reminder_1day"
                            )
                            sent_count += 1
                    elif ov.override_type == 'shop_global':
                        # Send to all staff
                        for staff_member in Staff.objects.filter(barbershop=ov.barbershop, is_active=True):
                            if not Notification.objects.filter(
                                user=staff_member.user,
                                type='system',
                                reference_id=f"override_{ov.id}_reminder_1day"
                            ).exists():
                                Notification.objects.create(
                                    user=staff_member.user,
                                    title="Salon İzin Günü Hatırlatması",
                                    body=f"Yarın ({ov.start_date.strftime('%d.%m.%Y')}) salon kapalı olacaktır. {ov.reason or ''}",
                                    type='system',
                                    reference_id=f"override_{ov.id}_reminder_1day"
                                )
                                sent_count += 1
                
                if sent_count > 0:
                    self.stdout.write(self.style.SUCCESS(f"Sent {sent_count} reminder notifications"))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing reminders: {e}"))
            
            if once:
                break
            
            # Run every hour
            import time
            time.sleep(3600)

