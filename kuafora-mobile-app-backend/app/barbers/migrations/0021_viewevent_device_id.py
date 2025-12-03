# Generated migration for adding device_id to ViewEvent

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0020_external_booking'),
    ]

    operations = [
        # Make user field nullable (for guest users)
        migrations.AlterField(
            model_name='viewevent',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name='barbershop_view_events',
                to='users.customuser',
            ),
        ),
        # Add device_id field
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
