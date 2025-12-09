from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta

from unfold.admin import ModelAdmin
from unfold.decorators import action

from .models import Notification, BroadcastNotification


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ("user", "title", "body_preview", "type_badge", "is_read", "created_at")
    list_filter = ("type", "is_read", "created_at")
    search_fields = ("title", "body", "user__full_name", "user__email")
    readonly_fields = ("created_at",)

    def has_add_permission(self, request):
        # Tek tek Notification eklemek yerine admin'de Toplu Bildirim
        # ekranını kullanmanızı istiyoruz.
        return False
    
    def body_preview(self, obj):
        return (obj.body[:80] + "...") if len(obj.body) > 80 else obj.body

    body_preview.short_description = "Mesaj"
    
    def type_badge(self, obj):
        colors = {
            "system": "bg-gray-100 text-gray-800",
            "booking": "bg-blue-100 text-blue-800",
            "chat": "bg-emerald-100 text-emerald-800",
            "reply": "bg-yellow-100 text-yellow-800",
        }
        color_class = colors.get(obj.type, "bg-gray-100 text-gray-800")
        return format_html(
            f'<span class="px-2 py-1 rounded text-xs font-medium {color_class}">{obj.get_type_display()}</span>'
        )

    type_badge.short_description = "Tip"


@admin.register(BroadcastNotification)
class BroadcastNotificationAdmin(ModelAdmin):
    """
    Kullanıcı dostu: Buradan sadece 3 adımda toplu bildirim gönderebilirsiniz:
    1) Başlık ve mesajı yazın
    2) Hedef kitleyi (segment) seçin
    3) Kaydet’e basın – sistem ilgili herkese in‑app bildirim üretir.
    """

    list_display = ("title", "segment", "created_at", "sent_at")
    list_filter = ("segment", "created_at", "sent_at")
    search_fields = ("title", "body")
    readonly_fields = ("created_at", "sent_at")

    fieldsets = (
        (
            "Mesaj İçeriği",
            {
                "fields": ("title", "body"),
                "description": "Kullanıcılara gidecek bildirim başlığı ve içeriği.",
            },
        ),
        (
            "Hedef Kitle",
            {
                "fields": ("segment",),
                "description": "Örneğin 'Tüm kullanıcılar'ı seçerseniz platformdaki tüm aktif kullanıcılara gider.",
            },
        ),
        (
            "Durum",
            {
                "fields": ("created_at", "sent_at"),
                "description": "Bu alanlar sadece bilgi içindir, sistem tarafından doldurulur.",
            },
        ),
    )

    @action(description="Seçilen duyuruyu şimdi gönder (hedef kitleye Notification üret)")
    def send_now(self, request, queryset):
        sent_total = 0
        for obj in queryset:
            if obj.sent_at:
                continue
            sent_total += self._fan_out(obj)
        self.message_user(request, f"Toplam {sent_total} kullanıcıya bildirim gönderildi.")

    actions = ["send_now"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Yeni kayıtta otomatik gönder – admin için mümkün olan en az adım
        if not change and not obj.sent_at:
            total = self._fan_out(obj)
            self.message_user(
                request,
                f"Toplu bildirim kaydedildi ve {total} kullanıcıya gönderildi.",
            )

    def _fan_out(self, obj: BroadcastNotification) -> int:
        """
        BroadcastNotification kaydını alır, hedef kitleyi çözer ve
        her kullanıcı için tek tek Notification üretir.
        """
        from app.users.models import User

        now = timezone.now()
        users_qs = User.objects.filter(is_active=True)

        if obj.segment == BroadcastNotification.Segment.ACTIVE_30_DAYS:
            users_qs = users_qs.filter(last_login__gte=now - timedelta(days=30))

        count = 0
        for user in users_qs.iterator():
            Notification.objects.create(
                user=user,
                title=obj.title,
                body=obj.body,
                type=Notification.NotificationType.SYSTEM,
            )
            count += 1

        if not obj.sent_at:
            obj.sent_at = timezone.now()
            obj.save(update_fields=["sent_at"])

        return count
