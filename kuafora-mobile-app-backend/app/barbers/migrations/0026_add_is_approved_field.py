# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0025_add_rejection_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='barbershop',
            name='is_approved',
            field=models.BooleanField(default=False, help_text='Admin onayı - onaylanmadan ana uygulamada görünmez'),
        ),
    ]

