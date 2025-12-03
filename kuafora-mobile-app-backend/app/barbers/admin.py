from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action
from .models import (
    Barbershop,
    BarbershopImage,
    Staff,
    StaffCatalogImage,
    WorkSchedule,
    Review,
    Service,
)


class BarbershopImageInline(TabularInline):
    model = BarbershopImage
    extra = 1
    tab = True


@admin.register(Barbershop)
class BarbershopAdmin(ModelAdmin):
    list_display = ("name", "gender_badge", "location_display", "verification_badge", "rating_display", "subscription_status")
    list_filter = ("gender", "city", "district", "is_verified")
    search_fields = ("name", "city", "district")
    inlines = [BarbershopImageInline]
    actions = ["verify_barbershops", "unverify_barbershops"]

    def gender_badge(self, obj):
        colors = {
            "male": "bg-blue-100 text-blue-800",
            "female": "bg-pink-100 text-pink-800",
            "unisex": "bg-purple-100 text-purple-800",
        }
        color_class = colors.get(obj.gender, "bg-gray-100 text-gray-800")
        return format_html(
            f'<span class="px-2 py-1 rounded text-xs font-medium {color_class}">{obj.get_gender_display()}</span>'
        )
    gender_badge.short_description = "Tür"

    def location_display(self, obj):
        return f"{obj.district}, {obj.city}"
    location_display.short_description = "Konum"

    def verification_badge(self, obj):
        if obj.is_verified:
            return format_html('<span class="text-green-600 font-bold">✓ Onaylı</span>')
        return format_html('<span class="text-yellow-600 font-bold">⏳ Beklemede</span>')
    verification_badge.short_description = "Onay Durumu"

    def rating_display(self, obj):
        if obj.rating_avg:
            return f"⭐ {obj.rating_avg:.1f} ({obj.total_reviews})"
        return "-"
    rating_display.short_description = "Puan"

    def subscription_status(self, obj):
        if hasattr(obj, 'subscription'):
            status = obj.subscription.get_status_display()
            color = "text-green-600" if obj.subscription.is_active_subscription else "text-red-600"
            return format_html(f'<span class="{color} font-medium">{status}</span>')
        return format_html('<span class="text-gray-400">Yok</span>')
    subscription_status.short_description = "Abonelik"

    @action(description="Seçilen kuaförleri onayla")
    def verify_barbershops(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"{updated} kuaför onaylandı.")

    @action(description="Seçilen kuaförlerin onayını kaldır")
    def unverify_barbershops(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f"{updated} kuaförün onayı kaldırıldı.")


@admin.register(Staff)
class StaffAdmin(ModelAdmin):
    list_display = ("user_email", "barbershop_link", "role_badge", "rating_display")
    list_filter = ("barbershop", "is_admin", "certificate")
    search_fields = ("user__email", "user__full_name", "barbershop__name")

    def user_email(self, obj):
        return obj.user.email if obj.user else obj.email
    user_email.short_description = "E-posta"

    def barbershop_link(self, obj):
        return obj.barbershop.name
    barbershop_link.short_description = "Salon"

    def role_badge(self, obj):
        if obj.is_admin:
            return format_html('<span class="bg-indigo-100 text-indigo-800 px-2 py-1 rounded text-xs">Yönetici</span>')
        return format_html('<span class="bg-gray-100 text-gray-800 px-2 py-1 rounded text-xs">Personel</span>')
    role_badge.short_description = "Rol"

    def rating_display(self, obj):
        return f"⭐ {obj.rating_avg:.1f}" if obj.rating_avg else "-"
    rating_display.short_description = "Puan"


@admin.register(StaffCatalogImage)
class StaffCatalogImageAdmin(ModelAdmin):
    list_display = ("staff", "image_preview", "created_at")
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(f'<img src="{obj.image.url}" style="height: 50px; border-radius: 4px;" />')
        return "-"
    image_preview.short_description = "Görsel"


@admin.register(WorkSchedule)
class WorkScheduleAdmin(ModelAdmin):
    list_display = ("staff", "day_display", "hours_display", "is_off")
    list_filter = ("day_of_week",)
    
    def day_display(self, obj):
        days = {
            0: "Pazartesi", 1: "Salı", 2: "Çarşamba", 3: "Perşembe", 
            4: "Cuma", 5: "Cumartesi", 6: "Pazar"
        }
        return days.get(obj.day_of_week, "-")
    day_display.short_description = "Gün"

    def hours_display(self, obj):
        if obj.is_off:
            return "İzinli"
        return f"{obj.start_time} - {obj.end_time}"
    hours_display.short_description = "Saatler"


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ("user", "barbershop", "rating_stars", "comment_snippet", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("comment", "user__full_name", "barbershop__name")
    actions = ["delete_reviews"]

    def rating_stars(self, obj):
        return "⭐" * obj.rating
    rating_stars.short_description = "Puan"

    def comment_snippet(self, obj):
        return (obj.comment[:50] + '...') if len(obj.comment) > 50 else obj.comment
    comment_snippet.short_description = "Yorum"

    @action(description="Seçilen yorumları sil")
    def delete_reviews(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"{count} yorum silindi.")


@admin.register(Service)
class ServiceAdmin(ModelAdmin):
    list_display = ("name", "barbershop", "category", "price_display", "duration_display", "is_active_badge")
    list_filter = ("barbershop", "category", "is_active")
    search_fields = ("name", "barbershop__name")

    def price_display(self, obj):
        return f"{obj.price} ₺"
    price_display.short_description = "Fiyat"

    def duration_display(self, obj):
        return f"{obj.duration} dk"
    duration_display.short_description = "Süre"

    def is_active_badge(self, obj):
        return format_html('<span class="text-green-600">✓</span>') if obj.is_active else format_html('<span class="text-red-600">✗</span>')
    is_active_badge.short_description = "Aktif"
