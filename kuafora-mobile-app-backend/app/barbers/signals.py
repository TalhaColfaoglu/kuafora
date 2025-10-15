from __future__ import annotations

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction

from .models import Review, Barbershop, DailyOverride, ShopHolidayOverride, Override
from django.core.cache import cache
from django.utils import timezone


def _status_cache_key(shop_id: int, date_str: str) -> str:
    return f"shop_status:{shop_id}:{date_str}"


def _bust_shop_status_cache(shop_id: int, date):
    try:
        key = _status_cache_key(shop_id, date.strftime('%Y-%m-%d'))
        cache.delete(key)
    except Exception:
        pass


def _recompute_aggregates(shop_id: int) -> None:
    qs = Review.objects.filter(barbershop_id=shop_id)
    counts = {i: 0 for i in range(1, 6)}
    total = 0
    sum_rating = 0
    for r in qs.values_list("rating", flat=True):
        counts[int(r)] = counts.get(int(r), 0) + 1
        total += 1
        sum_rating += int(r)
    avg = round((sum_rating / total), 2) if total > 0 else 0

    Barbershop.objects.filter(id=shop_id).update(
        rating_avg=avg,
        total_reviews=total,
        star_1_count=counts[1],
        star_2_count=counts[2],
        star_3_count=counts[3],
        star_4_count=counts[4],
        star_5_count=counts[5],
    )


@receiver(post_save, sender=Review)
def on_review_saved(sender, instance: Review, created, **kwargs):
    transaction.on_commit(lambda: _recompute_aggregates(instance.barbershop_id))


@receiver(post_delete, sender=Review)
def on_review_deleted(sender, instance: Review, **kwargs):
    transaction.on_commit(lambda: _recompute_aggregates(instance.barbershop_id))


@receiver(post_save, sender=DailyOverride)
def on_daily_override_saved(sender, instance: DailyOverride, created, **kwargs):
    transaction.on_commit(lambda: _bust_shop_status_cache(instance.barbershop_id, instance.date))


@receiver(post_delete, sender=DailyOverride)
def on_daily_override_deleted(sender, instance: DailyOverride, **kwargs):
    transaction.on_commit(lambda: _bust_shop_status_cache(instance.barbershop_id, instance.date))


@receiver(post_save, sender=ShopHolidayOverride)
def on_shop_holiday_override_saved(sender, instance: ShopHolidayOverride, created, **kwargs):
    transaction.on_commit(lambda: _bust_shop_status_cache(instance.barbershop_id, instance.date))


@receiver(post_delete, sender=ShopHolidayOverride)
def on_shop_holiday_override_deleted(sender, instance: ShopHolidayOverride, **kwargs):
    transaction.on_commit(lambda: _bust_shop_status_cache(instance.barbershop_id, instance.date))


@receiver(post_save, sender=Override)
def on_override_saved(sender, instance: Override, created, **kwargs):
    # For simplicity, bust at start_date; clients cache is short-lived (60s)
    transaction.on_commit(lambda: _bust_shop_status_cache(instance.barbershop_id, instance.start_date))


@receiver(post_delete, sender=Override)
def on_override_deleted(sender, instance: Override, **kwargs):
    transaction.on_commit(lambda: _bust_shop_status_cache(instance.barbershop_id, instance.start_date))

