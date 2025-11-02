from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0007_add_dailyoverride"),
    ]

    operations = [
        migrations.AddField(
            model_name="barbershop",
            name="latitude",
            field=models.FloatField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="barbershop",
            name="longitude",
            field=models.FloatField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="barbershop",
            name="system_type",
            field=models.CharField(
                max_length=10,
                choices=[("info", "Information"), ("booking", "Booking")],
                default="info",
                help_text="Isletme sistem modu: info veya booking",
            ),
            preserve_default=True,
        ),
    ]


