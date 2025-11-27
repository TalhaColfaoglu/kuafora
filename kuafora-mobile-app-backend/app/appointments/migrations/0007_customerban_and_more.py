from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0006_add_appointment_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerBan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bans', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name='customerban',
            index=models.Index(fields=['user', 'end_date'], name='appointment_user_id_b24a68_idx'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['staff', 'start_datetime'], name='appointment_staff_i_7637c6_idx'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['shop', 'start_datetime'], name='appointment_shop_id_c4656f_idx'),
        ),
    ]

