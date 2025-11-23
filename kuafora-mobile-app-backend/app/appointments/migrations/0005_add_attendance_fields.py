from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    """
    Safely add attendance tracking fields to Appointment model.

    production veritabanında bazı migration'lar fake olarak işaretlendiği için,
    eksik kolonları IF NOT EXISTS ile ekler.
    """

    dependencies = [
        ("appointments", "0004_remove_appointment_exclude_overlap_per_staff_active_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE appointments_appointment "
                "ADD COLUMN IF NOT EXISTS is_attended boolean;"
            ),
            reverse_sql=(
                "ALTER TABLE appointments_appointment "
                "DROP COLUMN IF EXISTS is_attended;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE appointments_appointment "
                "ADD COLUMN IF NOT EXISTS attended_at timestamp with time zone;"
            ),
            reverse_sql=(
                "ALTER TABLE appointments_appointment "
                "DROP COLUMN IF EXISTS attended_at;"
            ),
        ),
    ]



