from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    """
    Ensure new social fields exist on Barbershop and Staff models.

    Production veritabanında bazı migration'lar fake olarak işaretlendiği için
    eksik kolonları güvenli şekilde (IF NOT EXISTS) ekler.
    """

    dependencies = [
        ("barbers", "0011_barbershop_facebook_barbershop_instagram_and_more"),
    ]

    operations = [
        # --- Barbershop social fields ---
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_barbershop "
                "ADD COLUMN IF NOT EXISTS instagram varchar(100) DEFAULT '' NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_barbershop "
                "DROP COLUMN IF EXISTS instagram;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_barbershop "
                "ADD COLUMN IF NOT EXISTS facebook varchar(100) DEFAULT '' NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_barbershop "
                "DROP COLUMN IF EXISTS facebook;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_barbershop "
                "ADD COLUMN IF NOT EXISTS twitter varchar(100) DEFAULT '' NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_barbershop "
                "DROP COLUMN IF EXISTS twitter;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_barbershop "
                "ADD COLUMN IF NOT EXISTS whatsapp varchar(100) DEFAULT '' NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_barbershop "
                "DROP COLUMN IF EXISTS whatsapp;"
            ),
        ),
        # --- Staff social fields ---
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff "
                "ADD COLUMN IF NOT EXISTS instagram varchar(100) DEFAULT '' NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff "
                "DROP COLUMN IF EXISTS instagram;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff "
                "ADD COLUMN IF NOT EXISTS facebook varchar(100) DEFAULT '' NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff "
                "DROP COLUMN IF EXISTS facebook;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff "
                "ADD COLUMN IF NOT EXISTS twitter varchar(100) DEFAULT '' NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff "
                "DROP COLUMN IF EXISTS twitter;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE barbers_staff "
                "ADD COLUMN IF NOT EXISTS whatsapp varchar(100) DEFAULT '' NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE barbers_staff "
                "DROP COLUMN IF EXISTS whatsapp;"
            ),
        ),
    ]



