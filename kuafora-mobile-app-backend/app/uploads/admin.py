from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import UploadedImage


@admin.register(UploadedImage)
class UploadedImageAdmin(ModelAdmin):
    list_display = ("id", "image_preview", "created_at_display")
    list_filter = ("created_at",)
    search_fields = ("image",)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(f'<a href="{obj.image.url}" target="_blank"><img src="{obj.image.url}" style="height: 50px; border-radius: 4px;" /></a>')
        return "-"
    image_preview.short_description = "Görsel"

    def created_at_display(self, obj):
        return obj.created_at.strftime("%d.%m.%Y %H:%M")
    created_at_display.short_description = "Yüklenme Tarihi"
