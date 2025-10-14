from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from app.barbers.models import (
    Staff,
    StaffWorkingHours,
    WorkSchedule,
    StaffService,
    StaffServiceCategory,
    Override,
    ServiceCategory,
    Service,
)


class Command(BaseCommand):
    help = "Deduplicate Staff and ServiceCategory records safely by merging related objects."

    def handle(self, *args, **options):
        with transaction.atomic():
            staff_fixed = self._dedupe_staff()
            cat_fixed = self._dedupe_service_categories()
        self.stdout.write(self.style.SUCCESS(
            f"Deduplication completed. Staff merged: {staff_fixed}, ServiceCategory merged: {cat_fixed}"))

    def _dedupe_staff(self) -> int:
        merged = 0
        dups_groups = (
            Staff.objects.values('user_id', 'barbershop_id', 'is_admin')
            .annotate(c=Count('id')).filter(c__gt=1)
        )
        for g in dups_groups:
            dups = list(Staff.objects.filter(user_id=g['user_id'], barbershop_id=g['barbershop_id'], is_admin=g['is_admin']).order_by('id'))
            if len(dups) <= 1:
                continue
            survivor = dups[-1]
            for loser in dups[:-1]:
                # Reassign related objects to survivor, then delete loser
                StaffWorkingHours.objects.filter(staff=loser).update(staff=survivor)
                WorkSchedule.objects.filter(staff=loser).update(staff=survivor)
                StaffService.objects.filter(staff=loser).update(staff=survivor)
                StaffServiceCategory.objects.filter(staff=loser).update(staff=survivor)
                Override.objects.filter(staff=loser).update(staff=survivor)
                loser.delete()
                merged += 1
        return merged

    def _dedupe_service_categories(self) -> int:
        merged = 0
        dups_groups = (
            ServiceCategory.objects.values('barbershop_id', 'name')
            .annotate(c=Count('id')).filter(c__gt=1)
        )
        for g in dups_groups:
            dups = list(ServiceCategory.objects.filter(barbershop_id=g['barbershop_id'], name=g['name']).order_by('id'))
            if len(dups) <= 1:
                continue
            survivor = dups[-1]
            for loser in dups[:-1]:
                Service.objects.filter(category=loser).update(category=survivor)
                # StaffServiceCategory points to ServiceCategory via 'category'
                StaffServiceCategory.objects.filter(category=loser).update(category=survivor)
                loser.delete()
                merged += 1
        return merged


