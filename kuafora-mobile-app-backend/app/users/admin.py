from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "full_name", "gender", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "full_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name", "gender", "phone", "image")} ),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "gender", "password1", "password2")} ),
    )
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("groups", "user_permissions")
    list_filter = ("is_staff", "is_superuser", "is_active", "gender")
    # Map username to email
    def get_fieldsets(self, request, obj=None):  # pragma: no cover - admin
        return super().get_fieldsets(request, obj)


