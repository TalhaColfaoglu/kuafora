# Generated manually to add image_thumb fields

from django.db import migrations, models


def add_image_thumb_fields_if_not_exist(apps, schema_editor):
    """Add image_thumb columns if they don't exist"""
    from django.db import connection
    with connection.cursor() as cursor:
        # Check and add main_image_thumb to barbers_barbershop
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='barbers_barbershop' AND column_name='main_image_thumb';
        """)
        if not cursor.fetchone():
            cursor.execute("""
                ALTER TABLE barbers_barbershop 
                ADD COLUMN main_image_thumb VARCHAR(100);
            """)
        
        # Check and add image_thumb to barbers_barbershopimage
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='barbers_barbershopimage' AND column_name='image_thumb';
        """)
        if not cursor.fetchone():
            cursor.execute("""
                ALTER TABLE barbers_barbershopimage 
                ADD COLUMN image_thumb VARCHAR(100);
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0016_staffworkinghours_versioning'),
    ]

    operations = [
        migrations.RunPython(add_image_thumb_fields_if_not_exist, migrations.RunPython.noop),
    ]
