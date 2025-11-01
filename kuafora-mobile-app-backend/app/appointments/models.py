from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
import uuid


class AppointmentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    SUGGESTED = "suggested", "Suggested"
    CANCELLED = "cancelled", "Cancelled"
    COMPLETED = "completed", "Completed"
    NO_SHOW = "no_show", "No Show"


class AppointmentSource(models.TextChoices):
    PARTNER = "partner", "Partner"
    MOBILE_CUSTOMER = "mobile_customer", "Mobile Customer"


class CancelledBy(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    STAFF = "staff", "Staff"
    SYSTEM = "system", "System"
    SYSTEM_SWITCH = "system_switch", "System Switch"


class RefundStatus(models.TextChoices):
    NONE = "none", "None"
    QUEUED = "queued", "Queued"
    PROCESSING = "processing", "Processing"
    REFUNDED = "refunded", "Refunded"
    FAILED = "failed", "Failed"


class PaymentStatus(models.TextChoices):
    NONE = "none", "None"
    REQUIRES_ACTION = "requires_action", "Requires Action"
    AUTHORIZED = "authorized", "Authorized"
    CAPTURED = "captured", "Captured"
    FAILED = "failed", "Failed"


class Appointment(models.Model):
    """Appointment entity guarded by partial-unique constraint for active statuses."""

    shop = models.ForeignKey("barbers.Barbershop", on_delete=models.CASCADE, related_name="appointments")
    staff = models.ForeignKey("barbers.Staff", on_delete=models.CASCADE, related_name="appointments")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments")

    status = models.CharField(max_length=20, choices=AppointmentStatus.choices, db_index=True)
    start_datetime = models.DateTimeField(db_index=True)
    end_datetime = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()

    service_items = models.JSONField(default=list, blank=True)
    price_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    note = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=AppointmentSource.choices, default=AppointmentSource.PARTNER)

    payment_intent_id = models.CharField(max_length=120, null=True, blank=True)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.NONE)

    cancelled_by = models.CharField(max_length=20, choices=CancelledBy.choices, default=CancelledBy.SYSTEM, blank=True)
    refund_status = models.CharField(max_length=20, choices=RefundStatus.choices, default=RefundStatus.NONE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["staff", "start_datetime"]),
            models.Index(fields=["shop", "start_datetime"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["staff", "start_datetime", "end_datetime"],
                condition=Q(status__in=[
                    AppointmentStatus.PENDING,
                    AppointmentStatus.CONFIRMED,
                    AppointmentStatus.SUGGESTED,
                ]),
                name="uniq_staff_time_active_status",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.staff_id} {self.start_datetime} {self.status}"

    def save(self, *args, **kwargs):  # type: ignore[override]
        # Guard: booking sistemi kapalıysa kayda izin verme
        shop = self.shop
        if getattr(shop, "system_type", "info") != "booking":
            from django.core.exceptions import ValidationError
            raise ValidationError("BOOKING_DISABLED")
        super().save(*args, **kwargs)


class Hold(models.Model):
    """Soft lock for a candidate time window. TTL-enforced by expires_at."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey("barbers.Barbershop", on_delete=models.CASCADE, related_name="holds")
    staff = models.ForeignKey("barbers.Staff", on_delete=models.CASCADE, related_name="holds")
    start_datetime = models.DateTimeField(db_index=True)
    end_datetime = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["staff", "start_datetime"]),
            models.Index(fields=["shop", "start_datetime"]),
            models.Index(fields=["expires_at"]),
        ]


class IdempotencyKey(models.Model):
    """DB-backed idempotency storage to avoid infra dependency on Redis."""

    key = models.CharField(max_length=120, unique=True)
    actor = models.CharField(max_length=120, blank=True)
    request_hash = models.CharField(max_length=128)
    response_json = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class ShopSystemSwitchHistory(models.Model):
    shop = models.ForeignKey("barbers.Barbershop", on_delete=models.CASCADE, related_name="system_switches")
    from_type = models.CharField(max_length=10)
    to_type = models.CharField(max_length=10)
    reason = models.CharField(max_length=200, blank=True)
    actor = models.CharField(max_length=120, blank=True)
    idempotency_key = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class NotificationEvent(models.Model):
    """Outbox for push notifications to be delivered by a worker."""
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.CharField(max_length=120, db_index=True)
    payload = models.JSONField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    retries = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)




