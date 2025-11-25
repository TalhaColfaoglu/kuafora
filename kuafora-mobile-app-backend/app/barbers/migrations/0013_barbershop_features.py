from __future__ import annotations
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("barbers", "0012_backfill_social_fields"),
    ]
    operations = [
        migrations.RunSQL(
            sql=("ALTER TABLE barbers_barbershop ADD COLUMN IF NOT EXISTS features jsonb DEFAULT '[]'::jsonb;"),
            reverse_sql=("ALTER TABLE barbers_barbershop DROP COLUMN IF EXISTS features;"),
        ),
    ]
