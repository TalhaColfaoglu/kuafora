# Generated manually - google_maps_link already exists, removed from migration
# NOT: google_maps_link zaten 0027 migration'ında eklenmiş, bu migration'da tekrar eklenmemeli

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0033_alter_barbershop_options_barbershop_google_maps_link_and_more'),
    ]

    operations = [
        # Meta options değişikliği (eğer varsa)
        migrations.AlterModelOptions(
            name='barbershop',
            options={},
        ),
        # google_maps_link ZATEN VAR (0027'de eklendi) - ekleme işlemini çıkarıyoruz
        # Sadece field değişikliklerini yapıyoruz (storage, upload_to vb.)
        migrations.AlterField(
            model_name='barbershop',
            name='main_image',
            field=models.ImageField(blank=True, null=True, storage=None, upload_to='barbershops/main/'),
        ),
        migrations.AlterField(
            model_name='barbershop',
            name='main_image_thumb',
            field=models.ImageField(blank=True, null=True, storage=None, upload_to='barbershops/main/thumbs/'),
        ),
        migrations.AlterField(
            model_name='barbershopcatalog',
            name='image',
            field=models.ImageField(storage=None, upload_to='barbershops/catalog/'),
        ),
        migrations.AlterField(
            model_name='barbershopcatalog',
            name='image_thumb',
            field=models.ImageField(blank=True, null=True, storage=None, upload_to='barbershops/catalog/thumbs/'),
        ),
        migrations.AlterField(
            model_name='barbershopimage',
            name='image',
            field=models.ImageField(storage=None, upload_to='barbershops/images/'),
        ),
        migrations.AlterField(
            model_name='barbershopimage',
            name='image_thumb',
            field=models.ImageField(blank=True, null=True, storage=None, upload_to='barbershops/images/thumbs/'),
        ),
    ]
