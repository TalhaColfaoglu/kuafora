# Generated manually to add image_thumb fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0016_staffworkinghours_versioning'),
    ]

    operations = [
        migrations.AddField(
            model_name='barbershop',
            name='main_image_thumb',
            field=models.ImageField(blank=True, null=True, upload_to='barbershops/main/thumbs/'),
        ),
        migrations.AddField(
            model_name='barbershopimage',
            name='image_thumb',
            field=models.ImageField(blank=True, null=True, upload_to='barbershops/extra/thumbs/'),
        ),
    ]
