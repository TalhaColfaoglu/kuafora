from django.db import models
from django.utils import timezone


class AppVersion(models.Model):
    """
    Mobil uygulama versiyon bilgilerini yönetmek için model.
    """
    PLATFORM_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
    ]

    platform = models.CharField(
        max_length=10,
        choices=PLATFORM_CHOICES,
        default='android',
        help_text='Uygulama platformu'
    )
    version_name = models.CharField(
        max_length=50,
        help_text='Versiyon adı (örn: 1.0.0-internal.2)'
    )
    version_code = models.IntegerField(
        help_text='Build numarası (versionCode) - Her yeni build için artırılmalı'
    )
    force_update = models.BooleanField(
        default=False,
        help_text='Zorunlu güncelleme mi? (True ise kullanıcı uygulamayı kullanamaz)'
    )
    min_version_code = models.IntegerField(
        null=True,
        blank=True,
        help_text='Bu versiyondan eski olanlar için zorunlu güncelleme (opsiyonel)'
    )
    release_date = models.DateTimeField(
        default=timezone.now,
        help_text='Yayın tarihi'
    )
    update_message = models.TextField(
        blank=True,
        help_text='Güncelleme mesajı (kullanıcıya gösterilecek)'
    )
    play_store_url = models.URLField(
        blank=True,
        help_text='Play Store / App Store URL (boş bırakılırsa default URL kullanılır)'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Bu versiyon aktif mi?'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-version_code']
        unique_together = [['platform', 'version_code']]
        indexes = [
            models.Index(fields=['platform', 'is_active', '-version_code']),
        ]

    def __str__(self):
        return f"{self.platform} - {self.version_name} (Build {self.version_code})"
