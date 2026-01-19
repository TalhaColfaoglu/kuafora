# Generated manually

from django.db import migrations, models


def check_and_add_google_maps_link(apps, schema_editor):
    """Check if column exists, if not add it"""
    db_alias = schema_editor.connection.alias
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='barbers_barbershop' AND column_name='google_maps_link'
        """)
        if not cursor.fetchone():
            # Column doesn't exist, add it
            cursor.execute("""
                ALTER TABLE barbers_barbershop 
                ADD COLUMN google_maps_link VARCHAR(500) NULL
            """)


def reverse_migration(apps, schema_editor):
    """Remove column if it exists"""
    db_alias = schema_editor.connection.alias
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='barbers_barbershop' AND column_name='google_maps_link'
        """)
        if cursor.fetchone():
            cursor.execute("""
                ALTER TABLE barbers_barbershop 
                DROP COLUMN google_maps_link
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0026_add_is_approved_field'),
    ]

    operations = [
        migrations.RunPython(check_and_add_google_maps_link, reverse_migration),
    ]

