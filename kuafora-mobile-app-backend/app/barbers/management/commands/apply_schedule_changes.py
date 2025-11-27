from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from app.barbers.models import ScheduleChangeRequest, ShopWorkingHours, StaffWorkingHours, Barbershop, Staff
from app.barbers.serializers import ShopWorkingHoursSerializer, StaffWorkingHoursSerializer

class Command(BaseCommand):
    help = 'Applies effective schedule changes'

    def handle(self, *args, **options):
        today = timezone.now().date()
        pending_requests = ScheduleChangeRequest.objects.filter(applied=False, effective_date__lte=today)
        
        self.stdout.write(f"Found {pending_requests.count()} pending schedule changes.")
        
        for req in pending_requests:
            try:
                with transaction.atomic():
                    if req.target_type == ScheduleChangeRequest.TargetType.SHOP:
                        shop = Barbershop.objects.get(id=req.target_id)
                        ShopWorkingHours.objects.filter(barbershop=shop).delete()
                        serializer = ShopWorkingHoursSerializer(data=req.new_schedule_json, many=True)
                        serializer.is_valid(raise_exception=True)
                        serializer.save(barbershop=shop)
                        self.stdout.write(f"Applied shop schedule for {shop.name} (ID: {shop.id})")
                        
                    elif req.target_type == ScheduleChangeRequest.TargetType.STAFF:
                        staff = Staff.objects.get(id=req.target_id)
                        StaffWorkingHours.objects.filter(staff=staff).delete()
                        serializer = StaffWorkingHoursSerializer(data=req.new_schedule_json, many=True)
                        serializer.is_valid(raise_exception=True)
                        serializer.save(staff=staff)
                        self.stdout.write(f"Applied staff schedule for {staff.user.email} (ID: {staff.id})")
                    
                    req.applied = True
                    req.save()
                    
            except Exception as e:
                self.stderr.write(f"Error applying request {req.id}: {e}")

