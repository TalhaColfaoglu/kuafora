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
                # StaffWorkingHours: unique (staff, day_of_week). Merge row-by-row to avoid IntegrityError
                for h in StaffWorkingHours.objects.filter(staff=loser):
                    exists = StaffWorkingHours.objects.filter(staff=survivor, day_of_week=h.day_of_week).first()
                    if exists:
                        # Prefer explicit hours over closed; keep existing if exists has data else copy
                        if exists.is_closed and not h.is_closed:
                            exists.start_time = h.start_time
                            exists.end_time = h.end_time
                            exists.is_closed = h.is_closed
                            exists.save(update_fields=["start_time", "end_time", "is_closed"]) 
                        h.delete()
                    else:
                        h.staff = survivor
                        h.save(update_fields=["staff"])

                # WorkSchedule: no unique constraint; safe bulk move
                WorkSchedule.objects.filter(staff=loser).update(staff=survivor)

                # StaffService: unique (staff, service) → upsert
                for s in StaffService.objects.filter(staff=loser):
                    dup = StaffService.objects.filter(staff=survivor, service=s.service).first()
                    if dup:
                        # Keep the one with newer updated_at or lower price as heuristic
                        if hasattr(s, 'updated_at') and hasattr(dup, 'updated_at'):
                            if s.updated_at and dup.updated_at and s.updated_at > dup.updated_at:
                                dup.price = s.price
                                dup.duration_minutes = s.duration_minutes
                                dup.save(update_fields=["price", "duration_minutes"]) 
                        else:
                            if s.price and (not dup.price or s.price < dup.price):
                                dup.price = s.price
                                dup.duration_minutes = s.duration_minutes
                                dup.save(update_fields=["price", "duration_minutes"]) 
                        s.delete()
                    else:
                        s.staff = survivor
                        s.save(update_fields=["staff"])

                # StaffServiceCategory: unique (staff, category) → upsert
                for sc in StaffServiceCategory.objects.filter(staff=loser):
                    dup = StaffServiceCategory.objects.filter(staff=survivor, category=sc.category).first()
                    if dup:
                        sc.delete()
                    else:
                        sc.staff = survivor
                        sc.save(update_fields=["staff"])

                # Overrides: straightforward reassign
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


