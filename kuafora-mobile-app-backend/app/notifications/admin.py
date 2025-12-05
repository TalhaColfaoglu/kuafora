from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ("user", "title", "body_preview", "type_badge", "is_read", "created_at")
    list_filter = ("type", "is_read", "created_at")
    search_fields = ("title", "body", "user__full_name")
    
    def body_preview(self, obj):
        return (obj.body[:50] + '...') if len(obj.body) > 50 else obj.body
    body_preview.short_description = "Mesaj"
    
    def type_badge(self, obj):
        colors = {
            "system": "bg-gray-100 text-gray-800",
            "appointment": "bg-blue-100 text-blue-800",
            "campaign": "bg-purple-100 text-purple-800",
            "reminder": "bg-yellow-100 text-yellow-800",
        }
        color_class = colors.get(obj.type, "bg-gray-100 text-gray-800")
        return format_html(
            f'<span class="px-2 py-1 rounded text-xs font-medium {color_class}">{obj.get_type_display()}</span>'
        )
    type_badge.short_description = "Tip"
