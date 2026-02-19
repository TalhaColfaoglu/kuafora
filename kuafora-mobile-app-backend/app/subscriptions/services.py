from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from .models import Coupon, CouponUsage, Subscription


@dataclass(frozen=True)
class ApplyCouponResult:
    ok: bool
    error: Optional[str] = None


def apply_coupon_to_subscription(*, subscription: Subscription, coupon: Coupon) -> ApplyCouponResult:
    """
    Apply a coupon to a subscription with a single source of truth.

    Rules:
    - A coupon can be used only once per barbershop (enforced via CouponUsage lookup).
    - free_months extends trial_ends_at (or current_period_end for active/grace subscriptions).
    - lifetime switches status to 'lifetime'.
    - percent/fixed are reserved for future payment integrations (no date changes currently).
    """
    # Guardrails (cheap checks before transaction).
    if not coupon.is_valid:
        return ApplyCouponResult(ok=False, error="Kupon geçersiz veya süresi dolmuş")

    if CouponUsage.objects.filter(coupon=coupon, subscription__barbershop_id=subscription.barbershop_id).exists():
        return ApplyCouponResult(ok=False, error="Bu kupon bu salon için zaten kullanılmış")

    with transaction.atomic():
        # Re-check in transaction to avoid races.
        if CouponUsage.objects.select_for_update().filter(
            coupon=coupon, subscription__barbershop_id=subscription.barbershop_id
        ).exists():
            return ApplyCouponResult(ok=False, error="Bu kupon bu salon için zaten kullanılmış")

        # Lock coupon row to make current_uses updates safe.
        coupon = Coupon.objects.select_for_update().get(pk=coupon.pk)
        if not coupon.is_valid:
            return ApplyCouponResult(ok=False, error="Kupon geçersiz veya süresi dolmuş")

        subscription.coupon = coupon
        subscription.coupon_applied_at = timezone.now()

        if coupon.discount_type == "lifetime":
            subscription.status = "lifetime"

        elif coupon.discount_type == "free_months":
            # First 200 redemptions get 365 days (legacy marketing rule).
            if coupon.current_uses < 200:
                days = 365
            else:
                days = 30 * int(coupon.discount_value or 0)

            if subscription.status in ["active", "grace_period"] and subscription.current_period_end:
                subscription.current_period_end = subscription.current_period_end + timedelta(days=days)
            else:
                base = subscription.trial_ends_at or timezone.now()
                subscription.trial_ends_at = base + timedelta(days=days)

        # percent/fixed: no changes for now

        subscription.save()

        CouponUsage.objects.create(coupon=coupon, subscription=subscription)
        coupon.current_uses += 1
        coupon.save(update_fields=["current_uses"])

    return ApplyCouponResult(ok=True)

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from .models import Coupon, CouponUsage, Subscription


@dataclass(frozen=True)
class ApplyCouponResult:
    ok: bool
    error: Optional[str] = None


def apply_coupon_to_subscription(*, subscription: Subscription, coupon: Coupon) -> ApplyCouponResult:
    """
    Apply a coupon to a subscription with a single source of truth.

    Rules:
    - A coupon can be used only once per barbershop (enforced via CouponUsage lookup).
    - free_months extends trial_ends_at (or current_period_end for active/grace subscriptions).
    - lifetime switches status to 'lifetime'.
    - percent/fixed are reserved for future payment integrations (no date changes currently).
    """
    # Guardrails (cheap checks before transaction).
    if not coupon.is_valid:
        return ApplyCouponResult(ok=False, error="Kupon geçersiz veya süresi dolmuş")

    if CouponUsage.objects.filter(coupon=coupon, subscription__barbershop_id=subscription.barbershop_id).exists():
        return ApplyCouponResult(ok=False, error="Bu kupon bu salon için zaten kullanılmış")

    with transaction.atomic():
        # Re-check in transaction to avoid races.
        if CouponUsage.objects.select_for_update().filter(
            coupon=coupon, subscription__barbershop_id=subscription.barbershop_id
        ).exists():
            return ApplyCouponResult(ok=False, error="Bu kupon bu salon için zaten kullanılmış")

        # Lock coupon row to make current_uses updates safe.
        coupon = Coupon.objects.select_for_update().get(pk=coupon.pk)
        if not coupon.is_valid:
            return ApplyCouponResult(ok=False, error="Kupon geçersiz veya süresi dolmuş")

        subscription.coupon = coupon
        subscription.coupon_applied_at = timezone.now()

        if coupon.discount_type == "lifetime":
            subscription.status = "lifetime"

        elif coupon.discount_type == "free_months":
            # First 200 redemptions get 365 days (legacy marketing rule).
            if coupon.current_uses < 200:
                days = 365
            else:
                days = 30 * int(coupon.discount_value or 0)

            if subscription.status in ["active", "grace_period"] and subscription.current_period_end:
                subscription.current_period_end = subscription.current_period_end + timedelta(days=days)
            else:
                base = subscription.trial_ends_at or timezone.now()
                subscription.trial_ends_at = base + timedelta(days=days)

        # percent/fixed: no changes for now

        subscription.save()

        CouponUsage.objects.create(coupon=coupon, subscription=subscription)
        coupon.current_uses += 1
        coupon.save(update_fields=["current_uses"])

    return ApplyCouponResult(ok=True)

