from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from unfold.admin import ModelAdmin
from unfold.decorators import action

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    ordering = ("email",)
    list_display = ("email", "full_name_display", "gender", "is_active_badge", "is_staff_badge", "is_superuser_badge")
    search_fields = ("email", "full_name")
    
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Kişisel Bilgiler", {"fields": ("full_name", "gender", "phone", "image")} ),
        (
            "Yetkiler",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Önemli Tarihler", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "gender", "password1", "password2")} ),
    )
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("groups", "user_permissions")
    list_filter = ("is_staff", "is_superuser", "is_active", "gender")
    actions = ["ban_users", "unban_users"]
    
    def full_name_display(self, obj):
        return obj.full_name
    full_name_display.short_description = "Ad Soyad"

    def is_active_badge(self, obj):
        return format_html(
            '<span style="color: {}; font-weight: 600;">{}</span>',
            '#10B981' if obj.is_active else '#EF4444',
            'Aktif' if obj.is_active else 'Pasif'
        )
    is_active_badge.short_description = "Durum"

    def is_staff_badge(self, obj):
        if obj.is_staff:
            return format_html('<span style="background-color: #3B82F6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px;">Personel</span>')
        return ""
    is_staff_badge.short_description = "Personel"

    def is_superuser_badge(self, obj):
        if obj.is_superuser:
            return format_html(
                '<span style="background-color: #8B5CF6; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px;">Süper Admin</span>'
            )
        return ""
    is_superuser_badge.short_description = "Süper Admin"

    @action(description="Seçilen kullanıcıları banla (girişe kapat)")
    def ban_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} kullanıcı banlandı (is_active=False).")

    @action(description="Seçilen kullanıcıların banını kaldır (yeniden aktif et)")
    def unban_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} kullanıcının banı kaldırıldı.")
