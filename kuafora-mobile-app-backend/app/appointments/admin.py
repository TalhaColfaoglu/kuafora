from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import action
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(ModelAdmin):
    list_display = (
        "customer_link", 
        "barbershop_link", 
        "service_names", 
        "date_display", 
        "status_badge", 
        "price_display"
    )
    list_filter = ("status", "start_datetime", "shop")
    search_fields = (
        "customer__full_name", 
        "barbershop__name", 
        "staff__user__full_name"
    )
    actions = ["cancel_appointments", "confirm_appointments"]
    
    def customer_link(self, obj):
        return obj.customer.full_name if obj.customer else "Misafir"
    customer_link.short_description = "Müşteri"
    
    def barbershop_link(self, obj):
        return obj.barbershop.name
    barbershop_link.short_description = "Salon"
    
    def service_names(self, obj):
        services = obj.services.all()
        if not services:
            return "-"
        return ", ".join([s.name for s in services])
    service_names.short_description = "Hizmetler"
    
    def date_display(self, obj):
        return obj.start_time.strftime("%d.%m.%Y %H:%M")
    date_display.short_description = "Tarih"
    
    def status_badge(self, obj):
        colors = {
            "pending": "bg-yellow-100 text-yellow-800",
            "confirmed": "bg-green-100 text-green-800",
            "completed": "bg-blue-100 text-blue-800",
            "cancelled": "bg-red-100 text-red-800",
            "no_show": "bg-gray-100 text-gray-800",
        }
        color_class = colors.get(obj.status, "bg-gray-100 text-gray-800")
        return format_html(
            f'<span class="px-2 py-1 rounded text-xs font-medium {color_class}">{obj.get_status_display()}</span>'
        )
    status_badge.short_description = "Durum"
    
    def price_display(self, obj):
        return f"{obj.total_price} ₺"
    price_display.short_description = "Tutar"
    
    @action(description="Seçilen randevuları iptal et")
    def cancel_appointments(self, request, queryset):
        updated = queryset.update(status="cancelled")
        self.message_user(request, f"{updated} randevu iptal edildi.")
        
    @action(description="Seçilen randevuları onayla")
    def confirm_appointments(self, request, queryset):
        updated = queryset.update(status="confirmed")
        self.message_user(request, f"{updated} randevu onaylandı.")
