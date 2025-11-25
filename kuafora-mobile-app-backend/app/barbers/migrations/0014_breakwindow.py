from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0013_add_barbershop_features"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BreakWindow",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(choices=[("shop", "Dükkan"), ("staff", "Personel")], max_length=10)),
                ("date", models.DateField(help_text="Molayı kapsayan gün")),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("label", models.CharField(blank=True, help_text="Örn: Yemek molası", max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "barbershop",
                    models.ForeignKey(
                        help_text="Molanın bağlı olduğu dükkan",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="break_windows",
                        to="barbers.barbershop",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_break_windows",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        blank=True,
                        help_text="Personel molaları için zorunlu",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="break_windows",
                        to="barbers.staff",
                    ),
                ),
            ],
            options={
                "ordering": ["date", "start_time"],
            },
        ),
        migrations.AddConstraint(
            model_name="breakwindow",
            constraint=models.CheckConstraint(
                check=models.Q(("start_time__lt", models.F("end_time"))),
                name="breakwindow_start_before_end",
            ),
        ),
        migrations.AddIndex(
            model_name="breakwindow",
            index=models.Index(fields=["barbershop", "date"], name="barbershop_date_break_idx"),
        ),
        migrations.AddIndex(
            model_name="breakwindow",
            index=models.Index(fields=["staff", "date"], name="staff_date_break_idx"),
        ),
    ]


