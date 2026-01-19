# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0024_shopcategory_alter_breakwindow_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='barbershop',
            name='rejection_reason',
            field=models.TextField(blank=True, help_text='Reddetme nedeni (admin tarafından doldurulur)', null=True),
        ),
        migrations.AddField(
            model_name='barbershop',
            name='rejected_at',
            field=models.DateTimeField(blank=True, help_text='Reddetme tarihi', null=True),
        ),
    ]

