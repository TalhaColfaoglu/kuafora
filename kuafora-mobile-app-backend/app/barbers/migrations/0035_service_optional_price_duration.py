from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0034_alter_barbershop_options_barbershop_google_maps_link_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='service',
            name='price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Opsiyonel — bazı işletmeler fiyatı gizli tutar',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='service',
            name='duration',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Duration in minutes — randevu modunda zorunlu, bilgi modunda opsiyonel',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='staffservice',
            name='price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Opsiyonel — girilmezse dükkan hizmetinin fiyatı kullanılır',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='staffservice',
            name='duration_minutes',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Opsiyonel — girilmezse dükkan hizmetinin süresi kullanılır',
                null=True,
            ),
        ),
    ]
