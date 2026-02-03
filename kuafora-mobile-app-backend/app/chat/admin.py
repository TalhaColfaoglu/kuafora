from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import ChatRoom, ChatMessage, ChatBan, ChatMessageReport


@admin.register(ChatRoom)
class ChatRoomAdmin(ModelAdmin):
    list_display = ("customer", "barbershop", "last_message_preview", "updated_at")
    search_fields = ("customer__full_name", "barbershop__name")
    list_filter = ("updated_at",)

    def get_queryset(self, request):
        # N+1 sorgularını azaltmak için ilişkileri önceden çek
        qs = super().get_queryset(request)
        return qs.select_related("customer", "barbershop")

    def last_message_preview(self, obj):
        last_msg = obj.messages.order_by("-created_at").first()
        if last_msg:
            content = last_msg.content
            return (content[:50] + "...") if len(content) > 50 else content
        return "-"

    last_message_preview.short_description = "Son Mesaj"


@admin.register(ChatMessage)
class ChatMessageAdmin(ModelAdmin):
    list_display = (
        "id",
        "room_link",
        "sender_display",
        "content_preview",
        "is_staff_reply",
        "is_hidden",
        "report_count_display",
        "created_at",
    )
    list_filter = ("is_staff_reply", "is_hidden", "created_at")
    search_fields = ("content", "room__customer__full_name", "room__barbershop__name")
    readonly_fields = ("hidden_at",)

    def get_queryset(self, request):
        # Oda ve gönderen bilgilerini tek seferde çek
        qs = super().get_queryset(request)
        return qs.select_related("room__customer", "room__barbershop", "sender")

    def room_link(self, obj):
        customer_name = obj.room.customer.full_name if obj.room.customer else "Anonim"
        return f"{customer_name} - {obj.room.barbershop.name}"

    room_link.short_description = "Oda"

    def sender_display(self, obj):
        return obj.sender.full_name if obj.sender else "Sistem"

    sender_display.short_description = "Gönderen"

    def content_preview(self, obj):
        return (obj.content[:80] + "...") if len(obj.content) > 80 else obj.content

    content_preview.short_description = "İçerik"

    def report_count_display(self, obj):
        return obj.reports.count()

    report_count_display.short_description = "Şikayet"


@admin.register(ChatMessageReport)
class ChatMessageReportAdmin(ModelAdmin):
    list_display = ("id", "message", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("message__content", "user__full_name")
    raw_id_fields = ("message", "user")


@admin.register(ChatBan)
class ChatBanAdmin(ModelAdmin):
    list_display = ("user", "barbershop", "reason", "created_at", "expires_at")
    search_fields = ("user__full_name", "barbershop__name", "reason")
    list_filter = ("created_at", "expires_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "barbershop")
