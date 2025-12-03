from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class SubscriptionPlan(models.Model):
    """Abonelik planları - Kuafora Bilgi (190₺) ve Kuafora Randevu (890₺)"""
    
    name = models.CharField(max_length=100, verbose_name="Plan Adı")
    slug = models.SlugField(unique=True, verbose_name="Slug")  # 'bilgi', 'randevu'
    description = models.TextField(blank=True, verbose_name="Açıklama")
    price_monthly = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Aylık Fiyat (₺)"
    )
    price_yearly = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="Yıllık Fiyat (₺)"
    )
    features = models.JSONField(default=list, verbose_name="Özellikler")
    
    # Hangi randevu sistemleri bu plana dahil
    # ['info_system', 'external'] veya ['kuafora_booking']
    booking_system_types = models.JSONField(
        default=list, 
        verbose_name="Randevu Sistem Tipleri",
        help_text="info_system, external, kuafora_booking"
    )
    
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    sort_order = models.IntegerField(default=0, verbose_name="Sıralama")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Abonelik Planı"
        verbose_name_plural = "Abonelik Planları"
        ordering = ["sort_order", "price_monthly"]
    
    def __str__(self):
        return f"{self.name} - {self.price_monthly}₺/ay"


class Subscription(models.Model):
    """Kuaför abonelikleri"""
    
    STATUS_CHOICES = [
        ('trial', 'Deneme'),
        ('active', 'Aktif'),
        ('grace_period', 'Ek Süre'),
        ('suspended', 'Askıda'),
        ('cancelled', 'İptal'),
        ('lifetime', 'Ömür Boyu'),
    ]
    
    barbershop = models.OneToOneField(
        'barbers.Barbershop', 
        on_delete=models.CASCADE, 
        related_name='subscription',
        verbose_name="Kuaför Salonu"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, 
        on_delete=models.PROTECT, 
        related_name='subscriptions',
        verbose_name="Plan"
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='trial',
        verbose_name="Durum",
        db_index=True
    )
    
    # Tarihler
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Başlangıç")
    trial_ends_at = models.DateTimeField(verbose_name="Deneme Bitiş")
    current_period_start = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="Dönem Başlangıç"
    )
    current_period_end = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="Dönem Bitiş"
    )
    
    # Kupon
    coupon = models.ForeignKey(
        'Coupon', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='applied_subscriptions',
        verbose_name="Uygulanan Kupon"
    )
    coupon_applied_at = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="Kupon Uygulanma Tarihi"
    )
    
    # Ödeme bilgileri (ileride kullanılacak)
    payment_provider = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="Ödeme Sağlayıcı"
    )  # "iyzico", "stripe"
    payment_customer_id = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Ödeme Müşteri ID"
    )
    
    # Bildirim takibi
    trial_warning_sent = models.BooleanField(
        default=False, 
        verbose_name="Trial Uyarısı Gönderildi"
    )
    grace_warning_sent = models.BooleanField(
        default=False, 
        verbose_name="Grace Uyarısı Gönderildi"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Abonelik"
        verbose_name_plural = "Abonelikler"
    
    def __str__(self):
        return f"{self.barbershop.name} - {self.plan.name} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        # Trial bitiş tarihini otomatik ayarla (90 gün)
        if not self.trial_ends_at:
            self.trial_ends_at = timezone.now() + timedelta(days=90)
        super().save(*args, **kwargs)
    
    @property
    def is_active_subscription(self):
        """Abonelik aktif mi? (Ana uygulamada görünürlük için)"""
        return self.status in ['trial', 'active', 'lifetime', 'grace_period']
    
    @property
    def days_until_trial_ends(self):
        """Trial bitimine kaç gün kaldı"""
        if self.status != 'trial':
            return None
        delta = self.trial_ends_at - timezone.now()
        return max(0, delta.days)
    
    @property
    def status_info(self):
        """Vitrin uygulaması için detaylı durum bilgisi"""
        if self.status == 'trial':
            days_left = self.days_until_trial_ends
            return {
                'status': 'trial',
                'status_display': 'Deneme Süresi',
                'message': f'{days_left} gün kaldı',
                'days_left': days_left,
                'trial_ends_at': self.trial_ends_at.isoformat(),
                'color': 'blue' if days_left > 7 else 'orange',
            }
        elif self.status == 'lifetime':
            return {
                'status': 'lifetime',
                'status_display': 'Ömür Boyu Ücretsiz',
                'message': 'İlk 200 kuaförden birisiniz! ✨',
                'coupon_code': self.coupon.code if self.coupon else None,
                'color': 'green',
            }
        elif self.status == 'active':
            return {
                'status': 'active',
                'status_display': 'Aktif',
                'message': 'Aboneliğiniz aktif',
                'period_end': self.current_period_end.isoformat() if self.current_period_end else None,
                'color': 'green',
            }
        elif self.status == 'grace_period':
            return {
                'status': 'grace_period',
                'status_display': 'Ek Süre',
                'message': 'Ödeme bekleniyor (7 gün)',
                'color': 'orange',
            }
        elif self.status == 'suspended':
            return {
                'status': 'suspended',
                'status_display': 'Askıda',
                'message': '⚠️ Aboneliğiniz askıda. Ödeme yapın.',
                'color': 'red',
            }
        elif self.status == 'cancelled':
            return {
                'status': 'cancelled',
                'status_display': 'İptal',
                'message': 'Aboneliğiniz iptal edildi',
                'color': 'gray',
            }
        return {
            'status': self.status,
            'status_display': self.get_status_display(),
            'message': '',
            'color': 'gray',
        }


class Coupon(models.Model):
    """Kupon sistemi - Admin panelinden yönetilecek"""
    
    DISCOUNT_TYPE_CHOICES = [
        ('lifetime', 'Ömür Boyu Ücretsiz'),
        ('free_months', 'Bedava Ay'),
        ('percent', 'Yüzde İndirim'),
        ('fixed', 'Sabit TL İndirim'),
    ]
    
    code = models.CharField(
        max_length=50, 
        unique=True, 
        db_index=True,
        verbose_name="Kupon Kodu"
    )
    description = models.TextField(
        blank=True, 
        verbose_name="Açıklama",
        help_text="Admin için açıklama"
    )
    
    discount_type = models.CharField(
        max_length=20, 
        choices=DISCOUNT_TYPE_CHOICES,
        verbose_name="İndirim Tipi"
    )
    discount_value = models.IntegerField(
        verbose_name="İndirim Değeri",
        help_text="0 (lifetime), 6 (ay), 50 (%), 100 (TL)"
    )
    
    # Kısıtlamalar
    max_uses = models.IntegerField(
        null=True, 
        blank=True, 
        verbose_name="Maksimum Kullanım",
        help_text="Boş = sınırsız"
    )
    current_uses = models.IntegerField(default=0, verbose_name="Kullanım Sayısı")
    valid_from = models.DateTimeField(default=timezone.now, verbose_name="Geçerlilik Başlangıç")
    valid_until = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="Geçerlilik Bitiş",
        help_text="Boş = süresiz"
    )
    
    # Plan kısıtlaması
    applicable_plans = models.ManyToManyField(
        SubscriptionPlan, 
        blank=True,
        related_name='applicable_coupons',
        verbose_name="Geçerli Planlar",
        help_text="Boş = tüm planlar"
    )
    
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_coupons',
        verbose_name="Oluşturan"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Kupon"
        verbose_name_plural = "Kuponlar"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.code} ({self.get_discount_type_display()})"
    
    @property
    def is_valid(self):
        """Kupon geçerli mi?"""
        if not self.is_active:
            return False
        now = timezone.now()
        if self.valid_from > now:
            return False
        if self.valid_until and self.valid_until < now:
            return False
        if self.max_uses and self.current_uses >= self.max_uses:
            return False
        return True
    
    @property
    def remaining_uses(self):
        """Kalan kullanım hakkı"""
        if self.max_uses is None:
            return None  # Sınırsız
        return max(0, self.max_uses - self.current_uses)
    
    @property
    def discount_display(self):
        """İndirim gösterimi"""
        if self.discount_type == 'lifetime':
            return 'Ömür boyu ücretsiz'
        elif self.discount_type == 'free_months':
            return f'{self.discount_value} ay ücretsiz'
        elif self.discount_type == 'percent':
            return f'%{self.discount_value} indirim'
        elif self.discount_type == 'fixed':
            return f'{self.discount_value}₺ indirim'
        return ''


class CouponUsage(models.Model):
    """Kupon kullanım geçmişi"""
    
    coupon = models.ForeignKey(
        Coupon, 
        on_delete=models.CASCADE, 
        related_name='usages',
        verbose_name="Kupon"
    )
    subscription = models.ForeignKey(
        Subscription, 
        on_delete=models.CASCADE, 
        related_name='coupon_usages',
        verbose_name="Abonelik"
    )
    applied_at = models.DateTimeField(auto_now_add=True, verbose_name="Uygulanma Tarihi")
    
    class Meta:
        verbose_name = "Kupon Kullanımı"
        verbose_name_plural = "Kupon Kullanımları"
        unique_together = ['coupon', 'subscription']
    
    def __str__(self):
        return f"{self.coupon.code} → {self.subscription.barbershop.name}"
