from __future__ import annotations

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0006_add_service_created_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyOverride",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("status", models.CharField(max_length=10)),
                ("note", models.CharField(blank=True, max_length=200)),
                ("expires_at", models.DateTimeField(help_text="Genellikle gün sonu 23:59:59")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("barbershop", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="daily_overrides", to="barbers.barbershop")),
                ("created_by", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="created_daily_overrides", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("barbershop", "date")},
            },
        ),
        migrations.AddIndex(
            model_name="dailyoverride",
            index=models.Index(fields=["barbershop", "-date"], name="barbers_dai_barbers_33f9a9_idx"),
        ),
    ]


