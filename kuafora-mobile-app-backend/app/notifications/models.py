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
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_read"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.title}"

