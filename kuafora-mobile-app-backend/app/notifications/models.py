from django.db import models
from django.conf import settings


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        BOOKING = "booking", "Randevu"
        CHAT = "chat", "Mesaj"
        REPLY = "reply", "Yorum Yanıtı"
        SYSTEM = "system", "Sistem"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    type = models.CharField(max_length=20, choices=NotificationType.choices)
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

