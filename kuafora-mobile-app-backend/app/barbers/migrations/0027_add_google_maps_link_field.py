# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0026_add_is_approved_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='barbershop',
            name='google_maps_link',
            field=models.CharField(blank=True, help_text='Google Maps konum linki (örn: https://maps.app.goo.gl/...)', max_length=500, null=True),
        ),
    ]

