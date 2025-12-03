from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import action
from .models import Appointment, Hold, NotificationEvent, CustomerBan


@admin.register(Appointment)
class AppointmentAdmin(ModelAdmin):
    list_display = ("id_short", "shop_link", "customer_link", "staff_link", "status_badge", "time_range", "price_display")
    list_filter = ("status", "start_datetime", "shop", "source")
    search_fields = ("shop__name", "customer__full_name", "staff__user__full_name", "id")
    readonly_fields = ("created_at", "updated_at")
    actions = ["cancel_appointments", "complete_appointments"]

    def id_short(self, obj):
        return str(obj.id)[:8]
    id_short.short_description = "ID"

    def shop_link(self, obj):
        return obj.shop.name
    shop_link.short_description = "Salon"

    def customer_link(self, obj):
        return obj.customer.full_name if obj.customer else "-"
    customer_link.short_description = "Müşteri"

    def staff_link(self, obj):
        return obj.staff.user.full_name if obj.staff.user else obj.staff.email
    staff_link.short_description = "Personel"

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

    def time_range(self, obj):
        return f"{obj.start_datetime.strftime('%d.%m %H:%M')} - {obj.end_datetime.strftime('%H:%M')}"
    time_range.short_description = "Zaman"

    def price_display(self, obj):
        return f"{obj.price_total} ₺"
    price_display.short_description = "Tutar"

    @action(description="Seçilen randevuları iptal et")
    def cancel_appointments(self, request, queryset):
        updated = queryset.update(status="cancelled", cancelled_by="system")
        self.message_user(request, f"{updated} randevu iptal edildi.")

    @action(description="Seçilen randevuları tamamlandı yap")
    def complete_appointments(self, request, queryset):
        updated = queryset.update(status="completed")
        self.message_user(request, f"{updated} randevu tamamlandı olarak işaretlendi.")


@admin.register(Hold)
class HoldAdmin(ModelAdmin):
    list_display = ("shop", "staff", "expires_at", "price_total")
    list_filter = ("shop", "created_at")
    readonly_fields = ("created_at",)


@admin.register(CustomerBan)
class CustomerBanAdmin(ModelAdmin):
    list_display = ("user", "start_date", "end_date", "is_active_badge")
    list_filter = ("start_date", "end_date")
    search_fields = ("user__email", "user__full_name")

    def is_active_badge(self, obj):
        return format_html('<span class="text-red-600 font-bold">Banlı</span>') if obj.is_active() else format_html('<span class="text-gray-400">Süresi Dolmuş</span>')
    is_active_badge.short_description = "Durum"
