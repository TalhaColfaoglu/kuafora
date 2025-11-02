from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0007_add_dailyoverride"),
    ]

    operations = [
        # Idempotent field adds to avoid DuplicateColumn errors on existing DBs
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_barbershop ADD COLUMN IF NOT EXISTS latitude double precision;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_barbershop DROP COLUMN IF EXISTS latitude;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_barbershop ADD COLUMN IF NOT EXISTS longitude double precision;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_barbershop DROP COLUMN IF EXISTS longitude;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_barbershop ADD COLUMN IF NOT EXISTS system_type varchar(10) DEFAULT 'info' NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_barbershop DROP COLUMN IF EXISTS system_type;"
            ),
        ),
    ]


