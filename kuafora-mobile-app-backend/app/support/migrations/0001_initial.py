from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SupportRequest",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("phone", models.CharField(blank=True, default="", max_length=32)),
                (
                    "type",
                    models.CharField(
                        choices=[("support", "Destek"), ("suggestion", "Öneri"), ("complaint", "Şikayet")],
                        default="support",
                        max_length=20,
                    ),
                ),
                ("message", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[("new", "Yeni"), ("in_progress", "İşleme Alındı"), ("resolved", "Çözüldü")],
                        default="new",
                        max_length=20,
                    ),
                ),
                ("admin_note", models.TextField(blank=True, default="")),
                ("app_version", models.CharField(blank=True, default="", max_length=64)),
                ("platform", models.CharField(blank=True, default="", max_length=32)),
                ("device_info", models.CharField(blank=True, default="", max_length=255)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="support_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Destek Talebi",
                "verbose_name_plural": "Destek Talepleri",
                "ordering": ("-created_at",),
            },
        ),
    ]


