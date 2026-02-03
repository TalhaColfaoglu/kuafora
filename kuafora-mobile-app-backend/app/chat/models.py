from django.db import models
from django.conf import settings
from app.barbers.models import Barbershop

class ChatRoom(models.Model):
    class RoomType(models.TextChoices):
        PRIVATE = "private", "Private (1-on-1)"
        PUBLIC = "public", "Public (Community)"

    # Customer is nullable for public rooms
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="chat_rooms",
        null=True, 
        blank=True
    )
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="chat_rooms")
    
    room_type = models.CharField(
        max_length=10, 
        choices=RoomType.choices, 
        default=RoomType.PRIVATE
    )
    
    # Explicitly track if it's public (redundant with room_type but requested)
    is_public = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    last_message_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at"]
        indexes = [
            models.Index(fields=["barbershop", "room_type"]),
            models.Index(fields=["customer", "barbershop"]),
        ]

    def save(self, *args, **kwargs):
        if self.room_type == self.RoomType.PUBLIC:
            self.is_public = True
        super().save(*args, **kwargs)

    def __str__(self):
        if self.room_type == self.RoomType.PUBLIC:
            return f"Public Chat - {self.barbershop}"
        return f"{self.customer} - {self.barbershop}"

class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    is_staff_reply = models.BooleanField(default=False, help_text="If true, sender is a staff member representing the shop")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    # Şikayet: 3 şikayet gelince otomatik gizlenir; admin panelde görünür
    is_hidden = models.BooleanField(default=False, help_text="3+ şikayet sonrası otomatik veya manuel gizlendi")
    hidden_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message in {self.room} by {self.sender}"

    @property
    def report_count(self):
        return self.reports.count()


class ChatMessageReport(models.Model):
    """Bir mesaja kullanıcı şikayeti. 3 farklı kullanıcı şikayet edince mesaj otomatik gizlenir."""
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name="reports")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_message_reports")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("message", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report on msg {self.message_id} by {self.user_id}"

# Alias for compatibility if needed
Message = ChatMessage

class ChatBan(models.Model):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="chat_bans")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_bans")
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Süreli ban desteği: null ise süresiz, dolu ise expires_at sonrasında otomatik olarak geçersiz sayılır
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("barbershop", "user")

    def __str__(self):
        return f"{self.user} banned from {self.barbershop}"
