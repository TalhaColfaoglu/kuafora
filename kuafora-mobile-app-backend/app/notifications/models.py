from django.db import models
from django.conf import settings


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        BOOKING = "booking", "Randevu"
        CHAT = "chat", "Mesaj"
        REPLY = "reply", "Yorum Yanıtı"
        SYSTEM = "system", "Sistem"
        # Partner uygulaması bildirim ağı
        REVIEW = "review", "Yeni Yorum"
        PAYMENT_REMINDER = "payment_reminder", "Ödeme Hatırlatması"
        STAFF_CHANGE = "staff_change", "Personel Değişikliği"
        SUBSCRIPTION_EXPIRY = "subscription_expiry", "Abonelik Bitişi"
        PROMO = "promo", "Kampanya / Fırsat"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    type = models.CharField(max_length=24, choices=NotificationType.choices)
    reference_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="ID of related object (ör. Appointment / Campaign / Review ID)",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Bildirim (otomatik)"
        verbose_name_plural = "Bildirimler (otomatik)"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_read"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.title}"


class DevicePushToken(models.Model):
    """
    Stores device tokens for sending real push notifications via FCM/APNs.
    Token lifecycle is managed by the mobile apps.
    """

    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_tokens",
    )
    token = models.CharField(max_length=255, db_index=True)
    platform = models.CharField(max_length=12, choices=Platform.choices)
    device_id = models.CharField(max_length=120, blank=True, default="", help_text="Client-generated stable device id (optional).")
    app_version = models.CharField(max_length=40, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Push Token"
        verbose_name_plural = "Push Tokens"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["token", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user", "token"], name="unique_user_token"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user_id} {self.platform} {self.token[:12]}..."


class BroadcastNotification(models.Model):
    """
    Admin panelinden gönderilen, çoklu kullanıcıya giden toplu bildirimler.
    Kaydı oluşturduğunuzda sistem arka planda ilgili kullanıcılar için
    tek tek Notification satırı üretir.
    """

    class Segment(models.TextChoices):
        ALL_USERS = "all_users", "Tüm kullanıcılar"
        ACTIVE_30_DAYS = "active_30_days", "Son 30 günde aktif olanlar"

    title = models.CharField(max_length=255)
    body = models.TextField()
    segment = models.CharField(
        max_length=20,
        choices=Segment.choices,
        default=Segment.ALL_USERS,
        help_text="Kime gideceğini seçin. Örn: 'Tüm kullanıcılar' ya da 'Son 30 günde aktif olanlar'.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Bildirimler üretildiğinde sistem tarafından otomatik doldurulur.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Toplu Bildirim (admin)"
        verbose_name_plural = "Toplu Bildirimler (admin)"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.title

