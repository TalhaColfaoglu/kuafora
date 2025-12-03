from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from .models import ChatRoom, ChatMessage, ChatBan


class ChatMessageInline(TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("sender", "content", "created_at", "is_staff_reply")
    can_delete = False
    ordering = ("-created_at",)
    tab = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChatRoom)
class ChatRoomAdmin(ModelAdmin):
    list_display = ("customer_email", "barbershop_name", "last_message_at", "is_active_badge", "message_count")
    list_filter = ("is_active", "created_at")
    search_fields = ("customer__email", "barbershop__name")
    readonly_fields = ("created_at", "updated_at", "last_message_at")
    inlines = [ChatMessageInline]

    def customer_email(self, obj):
        return obj.customer.email
    customer_email.short_description = "Müşteri"

    def barbershop_name(self, obj):
        return obj.barbershop.name
    barbershop_name.short_description = "Salon"

    def is_active_badge(self, obj):
        return format_html('<span class="text-green-600">Aktif</span>') if obj.is_active else format_html('<span class="text-gray-400">Pasif</span>')
    is_active_badge.short_description = "Durum"

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = "Mesaj Sayısı"


@admin.register(ChatBan)
class ChatBanAdmin(ModelAdmin):
    list_display = ("user", "barbershop", "reason", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__email", "barbershop__name", "reason")
