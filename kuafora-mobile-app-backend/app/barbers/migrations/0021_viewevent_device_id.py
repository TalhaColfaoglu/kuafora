# Generated migration for adding device_id to ViewEvent

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0020_external_booking'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # AlterField işlemini "Database" ve "State" olarak ayırıyoruz.
        # Database işlemi manuel SQL ile yapılıyor (Hata vermemesi için).
        # State işlemi Django'nun model yapısını güncellemesi için yapılıyor.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # user_id kolonunu NULL yapılabilir hale getir
                migrations.RunSQL(
                    sql="ALTER TABLE barbers_viewevent ALTER COLUMN user_id DROP NOT NULL;",
                    reverse_sql="ALTER TABLE barbers_viewevent ALTER COLUMN user_id SET NOT NULL;"
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='viewevent',
                    name='user',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.CASCADE,
                        related_name='barbershop_view_events',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ]
        ),
        
        # Add device_id field (Bu işlem normal devam edebilir)
        migrations.AddField(
            model_name='viewevent',
            name='device_id',
            field=models.CharField(
                blank=True,
                help_text="Cihaz benzersiz ID'si - misafir kullanıcılar için",
                max_length=100,
                null=True,
            ),
        ),
        
        # Add index for device_id
        migrations.AddIndex(
            model_name='viewevent',
            index=models.Index(fields=['barbershop', 'device_id'], name='barbers_vie_barbers_abc123_idx'),
        ),
    ]
