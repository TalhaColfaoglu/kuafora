# Generated manually

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AppVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(choices=[('android', 'Android'), ('ios', 'iOS')], default='android', help_text='Uygulama platformu', max_length=10)),
                ('version_name', models.CharField(help_text='Versiyon adı (örn: 1.0.0-internal.2)', max_length=50)),
                ('version_code', models.IntegerField(help_text='Build numarası (versionCode) - Her yeni build için artırılmalı')),
                ('force_update', models.BooleanField(default=False, help_text='Zorunlu güncelleme mi? (True ise kullanıcı uygulamayı kullanamaz)')),
                ('min_version_code', models.IntegerField(blank=True, help_text='Bu versiyondan eski olanlar için zorunlu güncelleme (opsiyonel)', null=True)),
                ('release_date', models.DateTimeField(default=django.utils.timezone.now, help_text='Yayın tarihi')),
                ('update_message', models.TextField(blank=True, help_text='Güncelleme mesajı (kullanıcıya gösterilecek)')),
                ('play_store_url', models.URLField(blank=True, help_text='Play Store / App Store URL (boş bırakılırsa default URL kullanılır)')),
                ('is_active', models.BooleanField(default=True, help_text='Bu versiyon aktif mi?')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-version_code'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='appversion',
            unique_together={('platform', 'version_code')},
        ),
        migrations.AddIndex(
            model_name='appversion',
            index=models.Index(fields=['platform', 'is_active', '-version_code'], name='core_appver_platform_idx'),
        ),
    ]
