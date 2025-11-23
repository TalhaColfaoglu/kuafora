from django.core.management.base import BaseCommand
from django.utils import timezone
from app.appointments.models import Appointment, AppointmentStatus, CancelledBy

class Command(BaseCommand):
    help = 'Reject pending appointments that are past their start time'

    def handle(self, *args, **options):
        now = timezone.now()
        # Find PENDING appointments where start_time < now
        stale_qs = Appointment.objects.filter(
            status=AppointmentStatus.PENDING,
            start_datetime__lte=now
        )
        
        count = stale_qs.count()
        if count > 0:
            stale_qs.update(
                status=AppointmentStatus.CANCELLED,
                cancelled_by=CancelledBy.SYSTEM
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully cancelled {count} stale appointments'))
        else:
            self.stdout.write(self.style.SUCCESS('No stale appointments found'))

