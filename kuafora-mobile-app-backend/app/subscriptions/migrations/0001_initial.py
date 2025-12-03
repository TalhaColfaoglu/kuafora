# Generated migration for subscriptions app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('barbers', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubscriptionPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Plan Adı')),
                ('slug', models.SlugField(unique=True, verbose_name='Slug')),
                ('description', models.TextField(blank=True, verbose_name='Açıklama')),
                ('price_monthly', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Aylık Fiyat (₺)')),
                ('price_yearly', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Yıllık Fiyat (₺)')),
                ('features', models.JSONField(default=list, verbose_name='Özellikler')),
                ('booking_system_types', models.JSONField(default=list, help_text='info_system, external, kuafora_booking', verbose_name='Randevu Sistem Tipleri')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktif')),
                ('sort_order', models.IntegerField(default=0, verbose_name='Sıralama')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Abonelik Planı',
                'verbose_name_plural': 'Abonelik Planları',
                'ordering': ['sort_order', 'price_monthly'],
            },
        ),
        migrations.CreateModel(
            name='Coupon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(db_index=True, max_length=50, unique=True, verbose_name='Kupon Kodu')),
                ('description', models.TextField(blank=True, help_text='Admin için açıklama', verbose_name='Açıklama')),
                ('discount_type', models.CharField(choices=[('lifetime', 'Ömür Boyu Ücretsiz'), ('free_months', 'Bedava Ay'), ('percent', 'Yüzde İndirim'), ('fixed', 'Sabit TL İndirim')], max_length=20, verbose_name='İndirim Tipi')),
                ('discount_value', models.IntegerField(help_text='0 (lifetime), 6 (ay), 50 (%), 100 (TL)', verbose_name='İndirim Değeri')),
                ('max_uses', models.IntegerField(blank=True, help_text='Boş = sınırsız', null=True, verbose_name='Maksimum Kullanım')),
                ('current_uses', models.IntegerField(default=0, verbose_name='Kullanım Sayısı')),
                ('valid_from', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Geçerlilik Başlangıç')),
                ('valid_until', models.DateTimeField(blank=True, help_text='Boş = süresiz', null=True, verbose_name='Geçerlilik Bitiş')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktif')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('applicable_plans', models.ManyToManyField(blank=True, help_text='Boş = tüm planlar', related_name='applicable_coupons', to='subscriptions.subscriptionplan', verbose_name='Geçerli Planlar')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_coupons', to=settings.AUTH_USER_MODEL, verbose_name='Oluşturan')),
            ],
            options={
                'verbose_name': 'Kupon',
                'verbose_name_plural': 'Kuponlar',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('trial', 'Deneme'), ('active', 'Aktif'), ('grace_period', 'Ek Süre'), ('suspended', 'Askıda'), ('cancelled', 'İptal'), ('lifetime', 'Ömür Boyu')], db_index=True, default='trial', max_length=20, verbose_name='Durum')),
                ('started_at', models.DateTimeField(auto_now_add=True, verbose_name='Başlangıç')),
                ('trial_ends_at', models.DateTimeField(verbose_name='Deneme Bitiş')),
                ('current_period_start', models.DateTimeField(blank=True, null=True, verbose_name='Dönem Başlangıç')),
                ('current_period_end', models.DateTimeField(blank=True, null=True, verbose_name='Dönem Bitiş')),
                ('coupon_applied_at', models.DateTimeField(blank=True, null=True, verbose_name='Kupon Uygulanma Tarihi')),
                ('payment_provider', models.CharField(blank=True, max_length=50, verbose_name='Ödeme Sağlayıcı')),
                ('payment_customer_id', models.CharField(blank=True, max_length=100, verbose_name='Ödeme Müşteri ID')),
                ('trial_warning_sent', models.BooleanField(default=False, verbose_name='Trial Uyarısı Gönderildi')),
                ('grace_warning_sent', models.BooleanField(default=False, verbose_name='Grace Uyarısı Gönderildi')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('barbershop', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='subscription', to='barbers.barbershop', verbose_name='Kuaför Salonu')),
                ('coupon', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='applied_subscriptions', to='subscriptions.coupon', verbose_name='Uygulanan Kupon')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='subscriptions', to='subscriptions.subscriptionplan', verbose_name='Plan')),
            ],
            options={
                'verbose_name': 'Abonelik',
                'verbose_name_plural': 'Abonelikler',
            },
        ),
        migrations.CreateModel(
            name='CouponUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('applied_at', models.DateTimeField(auto_now_add=True, verbose_name='Uygulanma Tarihi')),
                ('coupon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usages', to='subscriptions.coupon', verbose_name='Kupon')),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupon_usages', to='subscriptions.subscription', verbose_name='Abonelik')),
            ],
            options={
                'verbose_name': 'Kupon Kullanımı',
                'verbose_name_plural': 'Kupon Kullanımları',
                'unique_together': {('coupon', 'subscription')},
            },
        ),
    ]
