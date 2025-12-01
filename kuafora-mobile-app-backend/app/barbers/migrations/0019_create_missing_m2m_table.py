# Generated manually to ensure M2M table exists

from django.db import migrations, models


def ensure_m2m_table_exists(apps, schema_editor):
    """Ensure barbers_barbershop_categories table exists"""
    from django.db import connection
    with connection.cursor() as cursor:
        # Create barbers_barbershop_categories (M2M table) if it doesn't exist
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'barbers_barbershop_categories'
            );
        """)
        if not cursor.fetchone()[0]:
            cursor.execute("""
                CREATE TABLE barbers_barbershop_categories (
                    id SERIAL PRIMARY KEY,
                    barbershop_id INTEGER NOT NULL REFERENCES barbers_barbershop(id) DEFERRABLE INITIALLY DEFERRED,
                    shopcategory_id INTEGER NOT NULL REFERENCES barbers_shopcategory(id) DEFERRABLE INITIALLY DEFERRED,
                    CONSTRAINT barbers_barbershop_categories_barbershop_id_shopcategory_id_uniq UNIQUE (barbershop_id, shopcategory_id)
                );
                CREATE INDEX barbers_barbershop_categories_barbershop_id_idx ON barbers_barbershop_categories(barbershop_id);
                CREATE INDEX barbers_barbershop_categories_shopcategory_id_idx ON barbers_barbershop_categories(shopcategory_id);
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0018_shopcategory_staff_photo_thumb'),
    ]

    operations = [
        migrations.RunPython(ensure_m2m_table_exists, migrations.RunPython.noop),
    ]
