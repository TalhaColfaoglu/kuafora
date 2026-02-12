# Generated migration for UserActivityLog and DailyMetrics models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('analytics', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DailyMetrics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True, help_text='Metrik günü', unique=True)),
                ('total_users', models.IntegerField(default=0, help_text='Toplam kullanıcı sayısı')),
                ('app_users_total', models.IntegerField(default=0, help_text='Uygulama kullanıcıları (staff hariç)')),
                ('daily_active_users', models.IntegerField(default=0, help_text='O gün aktif olan kullanıcılar')),
                ('daily_registrations', models.IntegerField(default=0, help_text='O gün kayıt olan kullanıcılar')),
                ('weekly_active_users', models.IntegerField(default=0, help_text='Son 7 gün aktif kullanıcılar')),
                ('weekly_registrations', models.IntegerField(default=0, help_text='Son 7 gün kayıtlar')),
                ('monthly_active_users', models.IntegerField(default=0, help_text='Son 30 gün aktif kullanıcılar')),
                ('monthly_registrations', models.IntegerField(default=0, help_text='Son 30 gün kayıtlar')),
                ('yearly_active_users', models.IntegerField(default=0, help_text='Son 365 gün aktif kullanıcılar')),
                ('yearly_registrations', models.IntegerField(default=0, help_text='Son 365 gün kayıtlar')),
                ('total_barbershops', models.IntegerField(default=0)),
                ('approved_barbershops', models.IntegerField(default=0)),
                ('total_appointments', models.IntegerField(default=0)),
                ('daily_appointments', models.IntegerField(default=0)),
                ('retention_rate', models.FloatField(default=0.0, help_text='Tutma oranı (%)')),
                ('churn_rate', models.FloatField(default=0.0, help_text='Ayrılma oranı (%)')),
                ('conversion_rate', models.FloatField(default=0.0, help_text='Dönüşüm oranı (%)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Günlük Metrik',
                'verbose_name_plural': 'Günlük Metrikler',
                'db_table': 'analytics_daily_metrics',
                'ordering': ['-date'],
            },
        ),
        migrations.CreateModel(
            name='UserActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_id', models.CharField(db_index=True, help_text='Cihaz ID', max_length=200)),
                ('app_type', models.CharField(choices=[('main', 'Ana Uygulama'), ('partner', 'Partner Uygulaması')], default='main', max_length=10)),
                ('activity_date', models.DateField(db_index=True, help_text='Aktivite günü')),
                ('login_count', models.IntegerField(default=1, help_text='O gün giriş sayısı')),
                ('last_activity', models.DateTimeField(default=django.utils.timezone.now)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='activity_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'analytics_user_activity_log',
                'ordering': ['-activity_date'],
            },
        ),
        migrations.AddIndex(
            model_name='dailymetrics',
            index=models.Index(fields=['date'], name='analytics_d_date_idx'),
        ),
        migrations.AddIndex(
            model_name='useractivitylog',
            index=models.Index(fields=['activity_date', 'app_type'], name='analytics_u_activit_idx'),
        ),
        migrations.AddIndex(
            model_name='useractivitylog',
            index=models.Index(fields=['device_id', 'activity_date'], name='analytics_u_device__idx'),
        ),
        migrations.AddIndex(
            model_name='useractivitylog',
            index=models.Index(fields=['user', 'activity_date'], name='analytics_u_user_id_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='useractivitylog',
            unique_together={('user', 'device_id', 'activity_date', 'app_type')},
        ),
        migrations.AddIndex(
            model_name='usersession',
            index=models.Index(fields=['device_id', 'start_time'], name='analytics_u_device__start_idx'),
        ),
    ]
