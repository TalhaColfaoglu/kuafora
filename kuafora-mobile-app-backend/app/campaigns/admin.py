from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import action
from .models import Campaign


@admin.register(Campaign)
class CampaignAdmin(ModelAdmin):
    list_display = ("name", "barbershop", "discount_display", "date_range", "is_active_badge")
    list_filter = ("is_active", "system_type", "discount_type", "barbershop", "start_date", "end_date")
    search_fields = ("name", "description", "barbershop__name")
    actions = ["activate_campaigns", "deactivate_campaigns"]
    date_hierarchy = "start_date"
    autocomplete_fields = ("barbershop",)

    fieldsets = (
        ("Temel", {"fields": ("barbershop", "name", "description", "type", "system_type")}),
        ("İndirim", {"fields": ("discount_type", "discount_value")}),
        ("Tarih", {"fields": ("start_date", "end_date", "is_active")}),
        ("Kurallar", {"fields": ("rules",), "classes": ("collapse",)}),
    )
    
    def discount_display(self, obj):
        if obj.discount_type == 'percent':
            return f"%{obj.discount_value}"
        return f"{obj.discount_value} ₺"
    discount_display.short_description = "İndirim"
    
    def date_range(self, obj):
        return f"{obj.start_date.strftime('%d.%m')} - {obj.end_date.strftime('%d.%m.%Y')}"
    date_range.short_description = "Tarih Aralığı"
    
    def is_active_badge(self, obj):
        return format_html('<span class="text-green-600">✓</span>') if obj.is_active else format_html('<span class="text-red-600">✗</span>')
    is_active_badge.short_description = "Aktif"
    
    @action(description="Seçilen kampanyaları aktifleştir")
    def activate_campaigns(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} kampanya aktifleştirildi.")
        
    @action(description="Seçilen kampanyaları pasifleştir")
    def deactivate_campaigns(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} kampanya pasifleştirildi.")
