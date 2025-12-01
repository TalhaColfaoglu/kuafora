# Generated manually to add ShopCategory and Staff.photo_thumb

from django.db import migrations, models


def add_missing_table_and_column(apps, schema_editor):
    """Add ShopCategory table and Staff.photo_thumb column if they don't exist"""
    from django.db import connection
    with connection.cursor() as cursor:
        # Create ShopCategory table if it doesn't exist
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'barbers_shopcategory'
            );
        """)
        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE barbers_shopcategory (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    slug VARCHAR(50) UNIQUE NOT NULL DEFAULT '',
                    icon VARCHAR(100),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE
                );
            """)
        
        # Add photo_thumb column to Staff if it doesn't exist
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name='barbers_staff' AND column_name='photo_thumb'
            );
        """)
        if not cursor.fetchone()[0]:
            cursor.execute("""
                ALTER TABLE barbers_staff 
                ADD COLUMN photo_thumb VARCHAR(100);
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0017_barbershop_main_image_thumb_barbershopimage_image_thumb'),
    ]

    operations = [
        migrations.RunPython(add_missing_table_and_column, migrations.RunPython.noop),
    ]
