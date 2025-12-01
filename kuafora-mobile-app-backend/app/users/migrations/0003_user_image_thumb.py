# Generated manually to add image_thumb field

from django.db import migrations, models


def add_image_thumb_if_not_exists(apps, schema_editor):
    """Add image_thumb column if it doesn't exist"""
    from django.db import connection
    with connection.cursor() as cursor:
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users_user' AND column_name='image_thumb';
        """)
        if not cursor.fetchone():
            # Column doesn't exist, add it
            cursor.execute("""
                ALTER TABLE users_user 
                ADD COLUMN image_thumb VARCHAR(100);
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_useraddress_favorite_lastviewed'),
    ]

    operations = [
        migrations.RunPython(add_image_thumb_if_not_exists, migrations.RunPython.noop),
    ]
