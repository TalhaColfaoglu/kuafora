# Generated manually - Fix indexes (remove subscription__status indexes)

from django.db import migrations, models


def check_and_add_index(apps, schema_editor):
    """Check if index exists, if not add it"""
    db_alias = schema_editor.connection.alias
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename='barbers_barbershop' AND indexname='barbers_bar_is_veri_idx'
        """)
        if not cursor.fetchone():
            # Index doesn't exist, add it
            cursor.execute("""
                CREATE INDEX barbers_bar_is_veri_idx 
                ON barbers_barbershop (is_verified, is_approved, city)
            """)


def reverse_migration(apps, schema_editor):
    """Remove index if it exists"""
    db_alias = schema_editor.connection.alias
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename='barbers_barbershop' AND indexname='barbers_bar_is_veri_idx'
        """)
        if cursor.fetchone():
            cursor.execute("""
                DROP INDEX IF EXISTS barbers_bar_is_veri_idx
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0027_add_google_maps_link_field'),
    ]

    operations = [
        migrations.RunPython(check_and_add_index, reverse_migration),
    ]

