from __future__ import annotations

from django.conf import settings
from django.db import models


class SupportRequest(models.Model):
    class Type(models.TextChoices):
        SUPPORT = "support", "Destek"
        SUGGESTION = "suggestion", "Öneri"
        COMPLAINT = "complaint", "Şikayet"

    class Status(models.TextChoices):
        NEW = "new", "Yeni"
        IN_PROGRESS = "in_progress", "İşleme Alındı"
        RESOLVED = "resolved", "Çözüldü"

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_requests",
    )

    # For guests / contact-back
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")

    type = models.CharField(max_length=20, choices=Type.choices, default=Type.SUPPORT)
    message = models.TextField()

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    admin_note = models.TextField(blank=True, default="")

    # Optional diagnostics from client / proxy
    app_version = models.CharField(max_length=64, blank=True, default="")
    platform = models.CharField(max_length=32, blank=True, default="")
    device_info = models.CharField(max_length=255, blank=True, default="")
    user_agent = models.TextField(blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Destek Talebi"
        verbose_name_plural = "Destek Talepleri"

    def __str__(self) -> str:  # pragma: no cover
        who = self.user.email if self.user_id else (self.email or self.phone or "guest")
        return f"{self.get_type_display()} • {who} • {self.created_at:%Y-%m-%d %H:%M}"


