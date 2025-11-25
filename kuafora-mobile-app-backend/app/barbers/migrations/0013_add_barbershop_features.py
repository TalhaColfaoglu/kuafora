from __future__ import annotations
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0012_backfill_social_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name='barbershop',
            name='features',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
