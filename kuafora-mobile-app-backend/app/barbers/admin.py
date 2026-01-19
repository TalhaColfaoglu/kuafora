from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.db.models import Count
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action
from .models import (
    Barbershop,
    BarbershopImage,
    Staff,
    StaffCatalogImage,
    WorkSchedule,
    Review,
    ServiceCategory,
    Service,
    StaffService,
    StaffServiceCategory,
)


class BarbershopImageInline(TabularInline):
    model = BarbershopImage
    extra = 1
    tab = True


@admin.register(Barbershop)
class BarbershopAdmin(ModelAdmin):
    list_display = (
        "id",
        "name",
        "gender_badge",
        "location_display",
        "approval_badge",
        "verification_badge",
        "rating_display",
        "favorites_count",
        "views_count",
        "subscription_status",
        "created_at",
    )
    list_display_links = ("id", "name")
    list_filter = ("gender", "city", "district", "is_verified", "is_approved", "subscription__status")
    search_fields = ("name", "city", "district", "address")
    date_hierarchy = "created_at"
    list_select_related = ("subscription",)
    inlines = [BarbershopImageInline]
    actions = ["verify_barbershops", "unverify_barbershops", "approve_barbershops", "reject_barbershops"]
    readonly_fields = ("rating_avg", "total_reviews", "favorites_count", "created_at", "updated_at", "main_image_preview", "images_preview", "google_maps_link_display")

    fieldsets = (
        ("Temel", {"fields": ("name", "gender", "system_type", "is_verified", "is_approved")}),
        ("Onay Durumu", {"fields": ("rejection_reason", "rejected_at"), "classes": ("collapse",)}),
        ("Konum", {"fields": ("city", "district", "address", "latitude", "longitude", "google_maps_link", "google_maps_link_display")}),
        ("İletişim", {"fields": ("phone", "instagram", "facebook", "twitter", "whatsapp"), "classes": ("collapse",)}),
        ("Görseller", {"fields": ("main_image", "main_image_preview", "images_preview"), "classes": ("collapse",)}),
        ("Açıklama", {"fields": ("description",)}),
        ("İstatistik", {"fields": ("rating_avg", "total_reviews", "favorites_count"), "classes": ("collapse",)}),
        ("Sistem", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_views_count=Count("view_events"))

    def views_count(self, obj):
        return getattr(obj, "_views_count", 0)
    views_count.short_description = "Görüntülenme"

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

    def approval_badge(self, obj):
        if obj.is_approved:
            return format_html('<span class="text-green-600 font-bold">✓ Onaylandı</span>')
        return format_html('<span class="text-red-600 font-bold">✗ Onay Bekliyor</span>')
    approval_badge.short_description = "Admin Onayı"

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

    @action(description="Seçilen kuaförleri YAYINA AL (onayla)")
    def verify_barbershops(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"{updated} kuaför yayına alındı (onaylandı).")

    @action(description="Seçilen kuaförleri YAYINDAN KALDIR / BANLA")
    def unverify_barbershops(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f"{updated} kuaför yayından kaldırıldı (banlandı).")

    @action(description="Seçilen kuaförleri ONAYLA (Ana uygulamada görünür yap)")
    def approve_barbershops(self, request, queryset):
        updated = queryset.update(
            is_approved=True,
            rejection_reason='',  # Onaylandığında reddetme nedeni temizlenir
            rejected_at=None
        )
        self.message_user(request, f"{updated} kuaför onaylandı ve ana uygulamada görünür hale getirildi.")

    @action(description="Seçilen kuaförleri REDDET (Ana uygulamadan kaldır)")
    def reject_barbershops(self, request, queryset):
        from django.utils import timezone
        from django.contrib import messages
        from django.shortcuts import render, redirect
        
        # Admin'den reddetme nedeni al (POST'tan)
        reason = request.POST.get('rejection_reason', '').strip()
        
        # Eğer POST'ta reason yoksa, form göster
        if 'apply' not in request.POST or not reason:
            context = {
                'barbershops': queryset,
                'action_checkbox_name': '_selected_action',
                'opts': self.model._meta,
                'title': 'Kuaförleri Reddet',
            }
            return render(request, 'admin/barbers/barbershop/reject_form.html', context)
        
        # Reddetme işlemini yap
        updated = queryset.update(
            is_approved=False,
            rejection_reason=reason,
            rejected_at=timezone.now()
        )
        self.message_user(request, f"{updated} kuaför reddedildi ve ana uygulamadan kaldırıldı.", messages.SUCCESS)
        return None

    def main_image_preview(self, obj):
        if obj.main_image:
            return format_html(
                f'<img src="{obj.main_image.url}" style="max-width: 300px; max-height: 300px; border-radius: 8px; margin: 10px 0;" />'
            )
        return format_html('<span class="text-gray-400">Görsel yok</span>')
    main_image_preview.short_description = "Ana Görsel Önizleme"

    def images_preview(self, obj):
        images = obj.images.all()[:5]  # İlk 5 görseli göster
        if not images:
            return format_html('<span class="text-gray-400">Ek görsel yok</span>')
        html = '<div style="display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0;">'
        for img in images:
            html += f'<img src="{img.image.url}" style="max-width: 150px; max-height: 150px; border-radius: 8px;" />'
        html += '</div>'
        if obj.images.count() > 5:
            html += f'<p style="margin-top: 10px; color: #666;">Toplam {obj.images.count()} görsel</p>'
        return format_html(html)
    images_preview.short_description = "Ek Görseller"

    def google_maps_link_display(self, obj):
        if obj.google_maps_link:
            return format_html(
                f'<a href="{obj.google_maps_link}" target="_blank" style="color: #3b82f6; text-decoration: underline;">{obj.google_maps_link}</a>'
            )
        return format_html('<span class="text-gray-400">Google Maps linki girilmemiş</span>')
    google_maps_link_display.short_description = "Google Maps Linki"


@admin.register(Staff)
class StaffAdmin(ModelAdmin):
    list_display = ("id", "user_email", "barbershop_link", "role_badge", "experience_display", "rating_display")
    list_display_links = ("id", "user_email")
    list_filter = ("barbershop", "is_admin", "certificate", "gender_preference")
    search_fields = ("user__email", "user__full_name", "email", "barbershop__name")
    autocomplete_fields = ("barbershop", "user")

    fieldsets = (
        ("Temel", {"fields": ("barbershop", "user", "email", "is_admin", "certificate")}),
        ("Profil", {"fields": ("bio", "gender_preference", "career_start_year", "tags")}),
        ("Sosyal", {"fields": ("instagram", "facebook", "twitter", "whatsapp"), "classes": ("collapse",)}),
        ("Randevu Ayarları", {"fields": ("auto_approval", "commission_rate", "appointment_interval"), "classes": ("collapse",)}),
        ("Medya", {"fields": ("photo", "photo_thumb"), "classes": ("collapse",)}),
    )

    class WorkScheduleInline(TabularInline):
        model = WorkSchedule
        extra = 0
        tab = True

    class StaffCatalogInline(TabularInline):
        model = StaffCatalogImage
        extra = 0
        tab = True

    class StaffServiceInline(TabularInline):
        model = StaffService
        extra = 0
        tab = True
        autocomplete_fields = ("service",)

    class StaffCategoryInline(TabularInline):
        model = StaffServiceCategory
        extra = 0
        tab = True
        autocomplete_fields = ("category",)

    inlines = [WorkScheduleInline, StaffCategoryInline, StaffServiceInline, StaffCatalogInline]

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

    def experience_display(self, obj):
        if obj.career_start_year:
            return f"{obj.career_start_year} → {max(0, (timezone.now().year - obj.career_start_year))} yıl"
        return "-"
    experience_display.short_description = "Deneyim"


@admin.register(StaffCatalogImage)
class StaffCatalogImageAdmin(ModelAdmin):
    list_display = ("staff", "image_preview")
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(f'<img src="{obj.image.url}" style="height: 50px; border-radius: 4px;" />')
        return "-"
    image_preview.short_description = "Görsel"


@admin.register(WorkSchedule)
class WorkScheduleAdmin(ModelAdmin):
    list_display = ("staff", "day_display", "hours_display")
    list_filter = ("day_of_week",)
    search_fields = ("staff__user__full_name", "staff__user__email", "staff__barbershop__name")
    
    def day_display(self, obj):
        days = {
            "Mon": "Pazartesi",
            "Tue": "Salı",
            "Wed": "Çarşamba",
            "Thu": "Perşembe",
            "Fri": "Cuma",
            "Sat": "Cumartesi",
            "Sun": "Pazar",
        }
        return days.get(obj.day_of_week, obj.day_of_week or "-")
    day_display.short_description = "Gün"

    def hours_display(self, obj):
        return f"{obj.start_time} - {obj.end_time}"
    hours_display.short_description = "Saatler"


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ("user", "barbershop", "rating_stars", "comment_snippet", "created_at")
    list_filter = ("rating", "created_at", "is_anonymous", "barbershop")
    search_fields = ("comment", "user__full_name", "barbershop__name")
    actions = ["delete_reviews"]
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Temel", {"fields": ("user", "barbershop", "staff", "rating", "is_anonymous")}),
        ("Yorum", {"fields": ("comment",)}),
        ("Yanıt", {"fields": ("reply", "replied_at"), "classes": ("collapse",)}),
        ("Sistem", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

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


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(ModelAdmin):
    list_display = ("id", "name", "barbershop", "created_at")
    list_display_links = ("id", "name")
    list_filter = ("barbershop",)
    search_fields = ("name", "barbershop__name")
    autocomplete_fields = ("barbershop",)
    date_hierarchy = "created_at"
