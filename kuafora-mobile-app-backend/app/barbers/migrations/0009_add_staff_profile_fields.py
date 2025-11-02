from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("barbers", "0008_add_barbershop_fields"),
    ]

    operations = [
        # Idempotent field adds to avoid DuplicateColumn errors on existing DBs
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff ADD COLUMN IF NOT EXISTS bio text DEFAULT '' NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff DROP COLUMN IF EXISTS bio;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff ADD COLUMN IF NOT EXISTS gender_preference varchar(10) DEFAULT 'all' NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff DROP COLUMN IF EXISTS gender_preference;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff ADD COLUMN IF NOT EXISTS experience_years integer;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff DROP COLUMN IF EXISTS experience_years;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff ADD COLUMN IF NOT EXISTS career_start_year integer;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff DROP COLUMN IF EXISTS career_start_year;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff ADD COLUMN IF NOT EXISTS tags jsonb DEFAULT '[]'::jsonb NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff DROP COLUMN IF EXISTS tags;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff ADD COLUMN IF NOT EXISTS rating_avg double precision DEFAULT 0 NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff DROP COLUMN IF EXISTS rating_avg;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff ADD COLUMN IF NOT EXISTS auto_approval boolean DEFAULT false NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff DROP COLUMN IF EXISTS auto_approval;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff ADD COLUMN IF NOT EXISTS commission_rate numeric(5, 2);"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff DROP COLUMN IF EXISTS commission_rate;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff ADD COLUMN IF NOT EXISTS appointment_interval integer DEFAULT 15 NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff DROP COLUMN IF EXISTS appointment_interval;"
            ),
        ),
    ]

