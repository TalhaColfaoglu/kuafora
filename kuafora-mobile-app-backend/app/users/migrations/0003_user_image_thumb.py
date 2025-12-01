# Generated manually to add image_thumb field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_useraddress_favorite_lastviewed'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='image_thumb',
            field=models.ImageField(blank=True, null=True, upload_to='users/images/thumbs/'),
        ),
    ]
