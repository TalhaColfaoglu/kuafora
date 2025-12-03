# Data migration: Initial plans and coupons

from django.db import migrations
from django.utils import timezone


def create_initial_data(apps, schema_editor):
    SubscriptionPlan = apps.get_model('subscriptions', 'SubscriptionPlan')
    Coupon = apps.get_model('subscriptions', 'Coupon')
    
    # ===== PLANLAR =====
    
    # Kuafora Bilgi Sistemi - 190₺/ay
    bilgi_plan = SubscriptionPlan.objects.create(
        name='Kuafora Bilgi Sistemi',
        slug='bilgi',
        description='Temel görünürlük paketi. Bilgi sistemi veya harici randevu kullanan salonlar için.',
        price_monthly=190.00,
        price_yearly=1900.00,  # 2 ay bedava
        features=[
            'Ana uygulamada görünürlük',
            'Salon profil sayfası',
            'Hizmet & fiyat listesi',
            'Fotoğraf galerisi',
            'Konum & iletişim bilgileri',
            'Çalışma saatleri',
        ],
        booking_system_types=['info_system', 'external'],
        is_active=True,
        sort_order=1,
    )
    
    # Kuafora Randevu Sistemi - 890₺/ay
    randevu_plan = SubscriptionPlan.objects.create(
        name='Kuafora Randevu Sistemi',
        slug='randevu',
        description='Full özellikli paket. Kuafora randevu sistemini kullanan salonlar için.',
        price_monthly=890.00,
        price_yearly=8900.00,  # 2 ay bedava
        features=[
            'Tüm Bilgi Sistemi özellikleri',
            'Online randevu alma',
            'Randevu yönetimi',
            'Müşteri bildirimleri',
            'Personel takvimi',
            'Anlık müsaitlik durumu',
            'Analitik & raporlar',
            'Müşteri yorumları',
        ],
        booking_system_types=['kuafora_booking'],
        is_active=True,
        sort_order=2,
    )
    
    # ===== KUPONLAR =====
    
    # İlk 200 kuaför için ömür boyu bedava
    Coupon.objects.create(
        code='ILK200',
        description='İlk 200 kuaföre ömür boyu ücretsiz abonelik. MVP lansmanı için.',
        discount_type='lifetime',
        discount_value=0,
        max_uses=200,
        current_uses=0,
        valid_from=timezone.now(),
        valid_until=None,  # Süresiz
        is_active=True,
    )
    
    # 3 ay bedava trial uzatma kuponu
    Coupon.objects.create(
        code='HOSGELDIN',
        description='Yeni kuaförlere hoş geldin kuponu. 3 ay ekstra trial.',
        discount_type='free_months',
        discount_value=3,
        max_uses=1000,
        current_uses=0,
        valid_from=timezone.now(),
        valid_until=None,
        is_active=True,
    )
    
    # %50 indirim kuponu (ödeme altyapısı gelince)
    Coupon.objects.create(
        code='YILBASI2025',
        description='2025 Yılbaşı kampanyası. %50 indirim.',
        discount_type='percent',
        discount_value=50,
        max_uses=500,
        current_uses=0,
        valid_from=timezone.now(),
        valid_until=timezone.now() + timezone.timedelta(days=90),  # 3 ay geçerli
        is_active=True,
    )


def reverse_initial_data(apps, schema_editor):
    SubscriptionPlan = apps.get_model('subscriptions', 'SubscriptionPlan')
    Coupon = apps.get_model('subscriptions', 'Coupon')
    
    SubscriptionPlan.objects.filter(slug__in=['bilgi', 'randevu']).delete()
    Coupon.objects.filter(code__in=['ILK200', 'HOSGELDIN', 'YILBASI2025']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_data, reverse_initial_data),
    ]
