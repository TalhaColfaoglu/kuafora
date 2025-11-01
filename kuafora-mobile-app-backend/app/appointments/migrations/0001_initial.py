from __future__ import annotations

import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("barbers", "0006_add_service_created_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Appointment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[
                    ("pending", "Pending"),
                    ("confirmed", "Confirmed"),
                    ("suggested", "Suggested"),
                    ("cancelled", "Cancelled"),
                    ("completed", "Completed"),
                    ("no_show", "No Show"),
                ], db_index=True, max_length=20)),
                ("start_datetime", models.DateTimeField(db_index=True)),
                ("end_datetime", models.DateTimeField()),
                ("duration_minutes", models.PositiveIntegerField()),
                ("service_items", models.JSONField(blank=True, default=list)),
                ("price_total", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("note", models.TextField(blank=True)),
                ("source", models.CharField(choices=[
                    ("partner", "Partner"),
                    ("mobile_customer", "Mobile Customer"),
                ], default="partner", max_length=20)),
                ("payment_intent_id", models.CharField(blank=True, max_length=120, null=True)),
                ("payment_status", models.CharField(choices=[
                    ("none", "None"),
                    ("requires_action", "Requires Action"),
                    ("authorized", "Authorized"),
                    ("captured", "Captured"),
                    ("failed", "Failed"),
                ], default="none", max_length=20)),
                ("cancelled_by", models.CharField(blank=True, choices=[
                    ("customer", "Customer"),
                    ("staff", "Staff"),
                    ("system", "System"),
                    ("system_switch", "System Switch"),
                ], default="system", max_length=20)),
                ("refund_status", models.CharField(choices=[
                    ("none", "None"),
                    ("queued", "Queued"),
                    ("processing", "Processing"),
                    ("refunded", "Refunded"),
                    ("failed", "Failed"),
                ], default="none", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("shop", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="appointments", to="barbers.barbershop")),
                ("staff", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="appointments", to="barbers.staff")),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="appointments", to=settings.AUTH_USER_MODEL)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name="Hold",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("start_datetime", models.DateTimeField(db_index=True)),
                ("end_datetime", models.DateTimeField()),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("shop", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="holds", to="barbers.barbershop")),
                ("staff", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="holds", to="barbers.staff")),
            ],
            options={},
        ),
        migrations.CreateModel(
            name="IdempotencyKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=120, unique=True)),
                ("actor", models.CharField(blank=True, max_length=120)),
                ("request_hash", models.CharField(max_length=128)),
                ("response_json", models.JSONField(blank=True, null=True)),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name="ShopSystemSwitchHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("from_type", models.CharField(max_length=10)),
                ("to_type", models.CharField(max_length=10)),
                ("reason", models.CharField(blank=True, max_length=200)),
                ("actor", models.CharField(blank=True, max_length=120)),
                ("idempotency_key", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("shop", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="system_switches", to="barbers.barbershop")),
            ],
            options={},
        ),
        migrations.CreateModel(
            name="NotificationEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("topic", models.CharField(db_index=True, max_length=120)),
                ("payload", models.JSONField()),
                ("status", models.CharField(choices=[
                    ("pending", "Pending"),
                    ("sent", "Sent"),
                    ("failed", "Failed"),
                ], db_index=True, default="pending", max_length=10)),
                ("retries", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={},
        ),
        # Indexes for Appointment
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(fields=["staff", "start_datetime"], name="appointment_staff_start_idx"),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(fields=["shop", "start_datetime"], name="appointment_shop_start_idx"),
        ),
        # Indexes for Hold
        migrations.AddIndex(
            model_name="hold",
            index=models.Index(fields=["staff", "start_datetime"], name="hold_staff_start_idx"),
        ),
        migrations.AddIndex(
            model_name="hold",
            index=models.Index(fields=["shop", "start_datetime"], name="hold_shop_start_idx"),
        ),
        migrations.AddIndex(
            model_name="hold",
            index=models.Index(fields=["expires_at"], name="hold_expires_idx"),
        ),
        # Partial unique constraint for active statuses on Appointment
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.UniqueConstraint(
                fields=["staff", "start_datetime", "end_datetime"],
                condition=models.Q(("status__in", ["pending", "confirmed", "suggested"])),
                name="uniq_staff_time_active_status",
            ),
        ),
    ]


