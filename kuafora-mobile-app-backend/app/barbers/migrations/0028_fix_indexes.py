# Generated manually - Fix indexes (remove subscription__status indexes)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0027_add_google_maps_link_field'),
    ]

    operations = [
        # Add new combined index for filtering
        migrations.AddIndex(
            model_name='barbershop',
            index=models.Index(fields=['is_verified', 'is_approved', 'city'], name='barbers_bar_is_veri_idx'),
        ),
    ]

