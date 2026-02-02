# Salon itirazları: reddedilen kuaför itiraz edebilir; admin panelde görüntülenir ve tekrar değerlendirilir.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0030_add_service_target_gender"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BarbershopAppeal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.TextField(help_text="Kuaförün itiraz metni")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Beklemede"), ("reviewed", "İncelendi")],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "barbershop",
                    models.ForeignKey(
                        help_text="Itirazı yapan salon",
                        on_delete=models.CASCADE,
                        related_name="appeals",
                        to="barbers.barbershop",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="reviewed_appeals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Salon itirazı",
                "verbose_name_plural": "Salon itirazları",
                "ordering": ["-created_at"],
            },
        ),
    ]
