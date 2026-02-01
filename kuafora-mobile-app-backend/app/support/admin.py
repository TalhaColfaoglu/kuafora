from django.contrib import admin

from unfold.admin import ModelAdmin
from unfold.decorators import action

from .models import SupportRequest


@admin.register(SupportRequest)
class SupportRequestAdmin(ModelAdmin):
    list_display = ("id", "type", "status", "message_preview", "user", "email", "phone", "created_at")
    list_filter = ("type", "status", "created_at")
    search_fields = ("message", "email", "phone", "user__email")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "ip_address", "user_agent", "platform", "app_version", "device_info")
    list_display_links = ("id", "message_preview")

    fieldsets = (
        (None, {"fields": ("type", "status")}),
        ("İçerik (mesaj tam metin)", {"fields": ("message",)}),
        ("İletişim", {"fields": ("user", "email", "phone")}),
        ("Admin Notu", {"fields": ("admin_note",)}),
        ("Teknik", {"fields": ("platform", "app_version", "device_info", "ip_address", "user_agent")}),
        ("Tarihler", {"fields": ("created_at", "updated_at")}),
    )

    actions = ["mark_in_progress", "mark_resolved"]

    @admin.display(description="Mesaj")
    def message_preview(self, obj: SupportRequest) -> str:
        if not obj.message:
            return "—"
        text = (obj.message or "").strip().replace("\n", " ")
        return text[:80] + ("…" if len(text) > 80 else "")

    @action(description="Seçilenleri İşleme Alındı yap")
    def mark_in_progress(self, request, queryset):
        updated = queryset.update(status=SupportRequest.Status.IN_PROGRESS)
        self.message_user(request, f"{updated} kayıt güncellendi.")

    @action(description="Seçilenleri Çözüldü yap")
    def mark_resolved(self, request, queryset):
        updated = queryset.update(status=SupportRequest.Status.RESOLVED)
        self.message_user(request, f"{updated} kayıt güncellendi.")


