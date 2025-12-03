from django.db import migrations, models


def drop_old_tables_if_exist(apps, schema_editor):
    """Eğer users_lastviewed ve users_favorite tabloları varsa sil"""
    with schema_editor.connection.cursor() as cursor:
        # Tabloların varlığını kontrol et
        cursor.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('users_lastviewed', 'users_favorite');
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        # Varsa sil
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")


def reverse_drop_tables(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_user_image_thumb'),
    ]

    operations = [
        # UserAddress değişiklikleri
        migrations.AlterModelOptions(
            name='useraddress',
            options={},
        ),
        migrations.RemoveField(
            model_name='useraddress',
            name='latitude',
        ),
        migrations.RemoveField(
            model_name='useraddress',
            name='longitude',
        ),
        migrations.AddField(
            model_name='useraddress',
            name='address_line',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='useraddress',
            name='label',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AlterField(
            model_name='useraddress',
            name='city',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='useraddress',
            name='district',
            field=models.CharField(blank=True, max_length=100),
        ),
        # User image_thumb ekleme
        migrations.AddField(
            model_name='user',
            name='image_thumb',
            field=models.ImageField(blank=True, null=True, upload_to='users/images/thumbs/'),
        ),
        # Eski tabloları güvenli şekilde sil
        migrations.RunPython(
            drop_old_tables_if_exist,
            reverse_drop_tables,
        ),
        # State'den modelleri kaldır
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(
                    name='LastViewed',
                ),
                migrations.DeleteModel(
                    name='Favorite',
                ),
            ],
        ),
    ]
