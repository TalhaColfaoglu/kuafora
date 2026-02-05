# Generated manually for BarbershopCatalog model

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0031_add_barbershop_appeal'),
    ]

    operations = [
        migrations.CreateModel(
            name='BarbershopCatalog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(storage=None, upload_to='barbershops/catalog/')),
                ('image_thumb', models.ImageField(blank=True, null=True, storage=None, upload_to='barbershops/catalog/thumbs/')),
                ('name', models.CharField(blank=True, help_text='Model adı (opsiyonel)', max_length=200, null=True)),
                ('description', models.TextField(blank=True, help_text='Model açıklaması (opsiyonel)', null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('order', models.IntegerField(default=0, help_text='Sıralama için')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('barbershop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='catalog', to='barbers.barbershop')),
            ],
            options={
                'verbose_name': 'Salon Katalog Görseli',
                'verbose_name_plural': 'Salon Katalog Görselleri',
                'ordering': ['order', 'created_at'],
            },
        ),
    ]
