from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0019_create_missing_m2m_table"),
    ]

    operations = [
        # Update system_type max_length and add new choice
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_barbershop "
                "ALTER COLUMN system_type TYPE varchar(15);"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_barbershop "
                "ALTER COLUMN system_type TYPE varchar(10);"
            ),
        ),
        # Add external_booking JSONField
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_barbershop "
                "ADD COLUMN IF NOT EXISTS external_booking jsonb DEFAULT '{}'::jsonb NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_barbershop "
                "DROP COLUMN IF EXISTS external_booking;"
            ),
        ),
    ]

