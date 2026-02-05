# Generated manually - google_maps_link already exists, removed from migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0032_add_barbershop_catalog'),
    ]

    operations = [
        # Meta options değişikliği
        migrations.AlterModelOptions(
            name='barbershop',
            options={},
        ),
        # google_maps_link zaten var, ekleme işlemini çıkarıyoruz
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
        # Indexes ekleme
        migrations.AddIndex(
            model_name='barbershop',
            index=models.Index(fields=['is_approved', 'is_verified', 'city'], name='barbers_bar_is_appr_02d51a_idx'),
        ),
        migrations.AddIndex(
            model_name='barbershop',
            index=models.Index(fields=['city', 'district'], name='barbers_bar_city_b2d5f9_idx'),
        ),
        migrations.AddIndex(
            model_name='barbershop',
            index=models.Index(fields=['latitude', 'longitude'], name='barbers_bar_latitud_9cc854_idx'),
        ),
        migrations.AddIndex(
            model_name='barbershop',
            index=models.Index(fields=['-created_at'], name='barbers_bar_created_6258a0_idx'),
        ),
        migrations.AddIndex(
            model_name='barbershop',
            index=models.Index(fields=['-rating_avg'], name='barbers_bar_rating__69387f_idx'),
        ),
        migrations.AddIndex(
            model_name='barbershop',
            index=models.Index(fields=['is_verified', 'is_approved', 'city'], name='barbers_bar_is_veri_ec8c97_idx'),
        ),
    ]
