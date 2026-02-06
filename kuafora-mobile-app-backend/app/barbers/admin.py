from datetime import timedelta

from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.db.models import Count, Q, Case, When, BooleanField, Exists, OuterRef
from django.db import models
from django.contrib.admin import SimpleListFilter
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action
from .models import (
    Barbershop,
    BarbershopAppeal,
    BarbershopImage,
    BarbershopCatalog,
    Staff,
    StaffCatalogImage,
    WorkSchedule,
    Review,
    Favorite,
    ViewEvent,
    ServiceCategory,
    Service,
    StaffService,
    StaffServiceCategory,
)


class HasGoogleMapsFilter(SimpleListFilter):
    title = "Google Maps Linki"
    parameter_name = "has_google_maps"
    
    def lookups(self, request, model_admin):
        return (
            ("yes", "Link Var"),
            ("no", "Link Yok"),
        )
    
    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(google_maps_link__isnull=False).exclude(google_maps_link="")
        if self.value() == "no":
            return queryset.filter(Q(google_maps_link__isnull=True) | Q(google_maps_link=""))


class HasImagesFilter(SimpleListFilter):
    title = "Görsel Durumu"
    parameter_name = "has_images"
    
    def lookups(self, request, model_admin):
        return (
            ("yes", "Görsel Var"),
            ("no", "Görsel Yok"),
        )
    
    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(main_image__isnull=False)
        if self.value() == "no":
            return queryset.filter(main_image__isnull=True)


class HasSocialMediaFilter(SimpleListFilter):
    title = "Sosyal Medya"
    parameter_name = "has_social_media"
    
    def lookups(self, request, model_admin):
        return (
            ("yes", "Link Var"),
            ("no", "Link Yok"),
        )
    
    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                Q(instagram__isnull=False, instagram__gt="") |
                Q(facebook__isnull=False, facebook__gt="") |
                Q(twitter__isnull=False, twitter__gt="") |
                Q(whatsapp__isnull=False, whatsapp__gt="")
            )
        if self.value() == "no":
            return queryset.filter(
                Q(instagram__isnull=True) | Q(instagram=""),
                Q(facebook__isnull=True) | Q(facebook=""),
                Q(twitter__isnull=True) | Q(twitter=""),
                Q(whatsapp__isnull=True) | Q(whatsapp="")
            )


class RejectionStatusFilter(SimpleListFilter):
    title = "Reddetme Durumu"
    parameter_name = "rejection_status"
    
    def lookups(self, request, model_admin):
        return (
            ("rejected", "Reddedilmiş"),
            ("pending", "Beklemede"),
            ("approved", "Onaylanmış"),
            ("resubmitted", "Tekrar Başvurulmuş"),
        )
    
    def queryset(self, request, queryset):
        if self.value() == "rejected":
            return queryset.filter(rejection_reason__isnull=False).exclude(rejection_reason="")
        if self.value() == "pending":
            return queryset.filter(is_approved=False, rejection_reason__isnull=True)
        if self.value() == "approved":
            return queryset.filter(is_approved=True)
        if self.value() == "resubmitted":
            # Reddetme bilgisi temizlenmiş ama henüz onaylanmamış (tekrar başvurulmuş)
            return queryset.filter(
                is_approved=False,
                rejection_reason__isnull=True,
                rejected_at__isnull=True
            ).exclude(created_at__gte=timezone.now() - timedelta(days=1))  # Son 24 saat içinde oluşturulmamış
        return queryset


class BarbershopImageInline(TabularInline):
    model = BarbershopImage
    extra = 1
    tab = True


class BarbershopCatalogInline(TabularInline):
    model = BarbershopCatalog
    extra = 1
    tab = True
    fields = ('image', 'image_thumb', 'name', 'description', 'is_active', 'order')
    readonly_fields = ('image_thumb',)


class BarbershopAppealInline(TabularInline):
    model = BarbershopAppeal
    extra = 0
    readonly_fields = ("created_at", "message", "reviewed_at", "reviewed_by")
    can_delete = True
    show_change_link = True
    verbose_name = "İtiraz"
    verbose_name_plural = "Salon itirazları"
    ordering = ["-created_at"]
    fields = ("message", "status", "created_at", "reviewed_at", "reviewed_by")

    def has_add_permission(self, request, obj=None):
        return False  # İtirazlar sadece partner uygulamasından eklenir


def _absolute_media_url(request, url):
    """Relative media URL'yi mevcut site adresiyle mutlak URL'ye çevirir; proxy/alt yol sorunlarını giderir."""
    if not url:
        return url
    if not request:
        return url
    try:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return request.build_absolute_uri(url)
    except Exception:
        return url


@admin.register(Barbershop)
class BarbershopAdmin(ModelAdmin):
    list_display = (
        "id",
        "thumbnail_preview",
        "name",
        "gender_badge",
        "full_address_display",
        "phone_display",
        "approval_badge",
        "verification_badge",
        "google_maps_status",
        "images_count",
        "rating_display",
        "favorites_count",
        "views_count",
        "subscription_status",
        "preview_link",
        "created_at",
    )
    list_display_links = ("id", "name", "thumbnail_preview")
    list_filter = (
        "gender", 
        "city", 
        "district", 
        "is_verified", 
        "is_approved", 
        "subscription__status",
        "system_type",
        RejectionStatusFilter,
        HasGoogleMapsFilter,
        HasImagesFilter,
        HasSocialMediaFilter,
    )
    search_fields = ("name", "city", "district", "address", "phone_number", "description")
    date_hierarchy = "created_at"
    list_select_related = ("subscription",)
    list_per_page = 50
    inlines = [BarbershopAppealInline, BarbershopImageInline, BarbershopCatalogInline]
    actions = ["verify_barbershops", "unverify_barbershops", "approve_barbershops", "reject_barbershops", "resubmit_for_review"]
    change_form_template = "admin/barbers/barbershop/change_form.html"
    change_list_template = "admin/barbers/barbershop/change_list.html"
    readonly_fields = (
        "rating_avg",
        "total_reviews",
        "favorites_count",
        "views_weekly",
        "created_at",
        "updated_at",
        "main_image_preview",
        "images_preview",
        "google_maps_link_display",
        "address_full_display",
        "contact_info_display",
        "social_media_display",
        "stats_display",
        "categories_display",
        "rejection_reason",
        "rejected_at",
    )

    fieldsets = (
        ("📋 Temel Bilgiler", {
            "fields": ("name", "gender", "system_type", "is_verified", "is_approved"),
            "classes": ("wide",)
        }),
        ("📍 Konum Bilgileri", {
            "fields": ("address_full_display", "city", "district", "address", "latitude", "longitude", "google_maps_link", "google_maps_link_display"),
            "classes": ("wide",)
        }),
        ("📞 İletişim Bilgileri", {
            "fields": ("contact_info_display", "phone_number"),
            "classes": ("collapse",)
        }),
        ("📱 Sosyal Medya", {
            "fields": ("social_media_display", "instagram", "facebook", "twitter", "whatsapp"),
            "classes": ("collapse",)
        }),
        ("🖼️ Görseller", {
            "fields": ("main_image", "main_image_preview", "images_preview"),
            "classes": ("wide",)
        }),
        ("📝 Açıklama", {
            "fields": ("description",),
            "classes": ("wide",)
        }),
        ("🏷️ Kategoriler", {
            "fields": ("categories_display", "categories"),
            "classes": ("collapse",)
        }),
        ("📊 İstatistikler", {
            "fields": ("stats_display", "rating_avg", "total_reviews", "favorites_count", "views_weekly"),
            "classes": ("collapse",)
        }),
        ("❌ Reddetme Bilgileri (Sadece Görüntüleme)", {
            "fields": ("rejection_reason", "rejected_at"),
            "classes": ("collapse",),
            "description": "Bu kuaför reddedilmişse, reddetme nedeni ve tarihi burada görüntülenir. Profil güncellendiğinde otomatik olarak temizlenir ve tekrar inceleme sürecine alınır."
        }),
        ("⚙️ Sistem", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def changelist_view(self, request, *args, **kwargs):
        self._request = request
        return super().changelist_view(request, *args, **kwargs)

    def changeform_view(self, request, *args, **kwargs):
        self._request = request
        return super().changeform_view(request, *args, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            _views_count=Count("view_events"),
            _images_count=Count("images"),
            _has_google_maps=models.Case(
                models.When(google_maps_link__isnull=False, google_maps_link__gt='', then=True),
                default=False,
                output_field=models.BooleanField()
            ),
            _has_images=models.Case(
                models.When(main_image__isnull=False, then=True),
                default=False,
                output_field=models.BooleanField()
            ),
            _has_social_media=models.Case(
                models.When(
                    models.Q(instagram__isnull=False, instagram__gt='') |
                    models.Q(facebook__isnull=False, facebook__gt='') |
                    models.Q(twitter__isnull=False, twitter__gt='') |
                    models.Q(whatsapp__isnull=False, whatsapp__gt=''),
                    then=True
                ),
                default=False,
                output_field=models.BooleanField()
            ),
        ).select_related("subscription").prefetch_related("images", "categories", "staff")
        return qs

    def views_count(self, obj):
        return getattr(obj, "_views_count", 0)
    views_count.short_description = "Görüntülenme"
    
    def preview_link(self, obj):
        url = reverse("admin-barbershop-preview", kwargs={"pk": obj.pk})
        return format_html(
            '<a href="{}" target="_blank" style="font-weight: 600; color: #2563eb;">📱 Önizleme</a>',
            url,
        )
    preview_link.short_description = "Detay önizleme"

    def thumbnail_preview(self, obj):
        req = getattr(self, "_request", None)
        if obj.main_image:
            try:
                image_url = obj.main_image_thumb.url if obj.main_image_thumb else obj.main_image.url
                full_url = obj.main_image.url
            except (ValueError, OSError):
                return format_html('<span style="display: inline-block; width: 60px; height: 60px; background: #fef2f2; border-radius: 8px; text-align: center; line-height: 60px; color: #dc2626; font-size: 11px;" title="Görsel yüklenemedi">Hata</span>')
            image_url = _absolute_media_url(req, image_url)
            full_url = _absolute_media_url(req, full_url)
            return format_html(
                f'<a href="{full_url}" class="admin-barbershop-img-link" target="_blank" style="display: inline-block; cursor: pointer;" title="Tıklayarak görseli büyüt">'
                f'<img src="{image_url}" style="width: 60px; height: 60px; object-fit: cover; border-radius: 8px; border: 2px solid #e5e7eb; transition: transform 0.2s;" '
                f'onmouseover="this.style.transform=\'scale(1.1)\'; this.style.boxShadow=\'0 4px 8px rgba(0,0,0,0.2)\';" '
                f'onmouseout="this.style.transform=\'scale(1)\'; this.style.boxShadow=\'none\';" />'
                f'</a>'
            )
        return format_html('<span style="display: inline-block; width: 60px; height: 60px; background: #f3f4f6; border-radius: 8px; text-align: center; line-height: 60px; color: #9ca3af; font-size: 24px;">📷</span>')
    thumbnail_preview.short_description = "Görsel"
    
    def full_address_display(self, obj):
        parts = []
        if obj.district:
            parts.append(obj.district)
        if obj.city:
            parts.append(obj.city)
        address_text = ", ".join(parts) if parts else "-"
        if obj.address:
            address_text += f"<br><small style='color: #6b7280;'>{obj.address[:50]}{'...' if len(obj.address) > 50 else ''}</small>"
        return format_html(address_text)
    full_address_display.short_description = "Adres"
    
    def phone_display(self, obj):
        if obj.phone_number:
            return format_html(
                f'<a href="tel:{obj.phone_number}" style="color: #3b82f6; text-decoration: none;">{obj.phone_number}</a>'
            )
        return format_html('<span style="color: #9ca3af;">-</span>')
    phone_display.short_description = "Telefon"
    
    def google_maps_status(self, obj):
        has_link = getattr(obj, "_has_google_maps", False) or (obj.google_maps_link and obj.google_maps_link.strip())
        if has_link:
            return format_html(
                '<span style="color: #10b981;">✓</span> <small style="color: #6b7280;">Link var</small>'
            )
        return format_html('<span style="color: #ef4444;">✗</span> <small style="color: #6b7280;">Link yok</small>')
    google_maps_status.short_description = "Google Maps"
    
    def images_count(self, obj):
        count = getattr(obj, "_images_count", 0)
        if obj.main_image:
            count += 1
        if count > 0:
            return format_html(f'<span style="color: #3b82f6; font-weight: 600;">{count}</span>')
        return format_html('<span style="color: #9ca3af;">0</span>')
    images_count.short_description = "Görsel"

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
        elif obj.rejection_reason:
            # Reddedilmiş
            return format_html(
                '<span class="text-red-600 font-bold">✗ Reddedildi</span>'
                '<br><small style="color: #9ca3af; font-size: 11px;">Tekrar başvuru yapılabilir</small>'
            )
        else:
            return format_html('<span class="text-yellow-600 font-bold">⏳ Onay Bekliyor</span>')
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
            is_verified=False,  # Reddedildiğinde verified de False yapılmalı ki frontend'de gösterilebilsin
            rejection_reason=reason,
            rejected_at=timezone.now()
        )
        self.message_user(request, f"{updated} kuaför reddedildi ve ana uygulamadan kaldırıldı.", messages.SUCCESS)
        return None

    def main_image_preview(self, obj):
        req = getattr(self, "_request", None)
        if obj.main_image:
            try:
                thumbnail_url = obj.main_image_thumb.url if obj.main_image_thumb else obj.main_image.url
                full_url = obj.main_image.url
            except (ValueError, OSError):
                return format_html('<div style="padding: 20px; background: #fef2f2; border-radius: 8px; color: #dc2626; text-align: center;">📷 Görsel dosyası bulunamadı veya yüklenemedi</div>')
            thumbnail_url = _absolute_media_url(req, thumbnail_url)
            full_url = _absolute_media_url(req, full_url)
            return format_html(
                f'''
                <div style="margin: 10px 0;">
                    <a href="{full_url}" class="admin-barbershop-img-link" style="display: inline-block; cursor: pointer;" title="Tıklayarak görseli büyüt" target="_blank">
                        <img src="{thumbnail_url}" style="max-width: 400px; max-height: 400px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 10px; transition: transform 0.2s;" 
                             onmouseover="this.style.transform='scale(1.02)'; this.style.boxShadow='0 8px 12px rgba(0,0,0,0.15)';" 
                             onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 4px 6px rgba(0,0,0,0.1)';" />
                    </a>
                    <br>
                    <a href="{full_url}" class="admin-barbershop-img-link" style="color: #3b82f6; text-decoration: none; font-size: 12px; display: inline-block; margin-top: 8px;">🔗 Tam boyutu aç / büyüt</a>
                </div>
                '''
            )
        return format_html('<div style="padding: 20px; background: #f3f4f6; border-radius: 8px; color: #9ca3af; text-align: center;">📷 Ana görsel yok</div>')
    main_image_preview.short_description = "Ana Görsel Önizleme"

    def images_preview(self, obj):
        req = getattr(self, "_request", None)
        images = list(obj.images.all())
        total_count = len(images)
        if not images:
            return format_html('<div style="padding: 20px; background: #f3f4f6; border-radius: 8px; color: #9ca3af; text-align: center;">📷 Ek görsel yok</div>')
        
        html = f'<div style="margin: 10px 0;"><strong style="color: #374151; margin-bottom: 10px; display: block;">Toplam {total_count} ek görsel:</strong>'
        html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; margin-top: 10px;">'
        
        for img in images[:12]:  # İlk 12 görseli göster
            try:
                thumbnail_url = img.image_thumb.url if img.image_thumb else img.image.url
                full_url = img.image.url
            except (ValueError, OSError):
                thumbnail_url = full_url = "#"
            thumbnail_url = _absolute_media_url(req, thumbnail_url)
            full_url = _absolute_media_url(req, full_url)
            html += f'''
                <div style="position: relative;">
                    <a href="{full_url}" class="admin-barbershop-img-link" style="display: block; cursor: pointer;" title="Tıklayarak görseli büyüt" target="_blank">
                        <img src="{thumbnail_url}" style="width: 100%; height: 150px; object-fit: cover; border-radius: 8px; border: 2px solid #e5e7eb; transition: transform 0.2s;" 
                             onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='0 4px 8px rgba(0,0,0,0.2)';" 
                             onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='none';" />
                    </a>
                </div>
            '''
        html += '</div>'
        
        if total_count > 12:
            html += f'<p style="margin-top: 12px; color: #6b7280; font-size: 13px;">+ {total_count - 12} görsel daha var</p>'
        
        html += '</div>'
        return format_html(html)
    images_preview.short_description = "Ek Görseller"

    def google_maps_link_display(self, obj):
        if obj.google_maps_link and obj.google_maps_link.strip():
            link = obj.google_maps_link.strip()
            return format_html(
                f'''
                <div style="margin: 10px 0; padding: 12px; background: #eff6ff; border-radius: 8px; border-left: 4px solid #3b82f6;">
                    <div style="margin-bottom: 8px;">
                        <strong style="color: #1e40af;">📍 Google Maps Konumu:</strong>
                    </div>
                    <a href="{link}" target="_blank" style="color: #3b82f6; text-decoration: none; word-break: break-all; display: inline-block; margin-top: 4px;">
                        {link}
                        <span style="margin-left: 6px;">🔗</span>
                    </a>
                    {f'''
                    <div style="margin-top: 10px; padding: 8px; background: white; border-radius: 6px;">
                        <small style="color: #6b7280;">Koordinatlar: {obj.latitude or "N/A"}, {obj.longitude or "N/A"}</small>
                    </div>
                    ''' if obj.latitude and obj.longitude else ''}
                </div>
                '''
            )
        return format_html(
            '<div style="padding: 12px; background: #fef2f2; border-radius: 8px; border-left: 4px solid #ef4444; color: #991b1b;">'
            '⚠️ Google Maps linki girilmemiş'
            '</div>'
        )
    google_maps_link_display.short_description = "Google Maps Linki"
    
    def address_full_display(self, obj):
        parts = []
        if obj.address:
            parts.append(f'<strong>Adres:</strong> {obj.address}')
        if obj.district:
            parts.append(f'<strong>İlçe:</strong> {obj.district}')
        if obj.city:
            parts.append(f'<strong>İl:</strong> {obj.city}')
        if obj.latitude and obj.longitude:
            parts.append(f'<strong>Koordinatlar:</strong> {obj.latitude}, {obj.longitude}')
        
        if parts:
            return format_html(
                f'<div style="padding: 12px; background: #f9fafb; border-radius: 8px; line-height: 1.8;">'
                f'{"<br>".join(parts)}'
                f'</div>'
            )
        return format_html('<span style="color: #9ca3af;">Adres bilgisi girilmemiş</span>')
    address_full_display.short_description = "Tam Adres Bilgisi"
    
    def contact_info_display(self, obj):
        html = '<div style="padding: 12px; background: #f0fdf4; border-radius: 8px; border-left: 4px solid #10b981;">'
        if obj.phone_number:
            html += f'<div style="margin-bottom: 8px;"><strong>📞 Telefon:</strong> <a href="tel:{obj.phone_number}" style="color: #059669; text-decoration: none;">{obj.phone_number}</a></div>'
        else:
            html += '<div style="margin-bottom: 8px; color: #9ca3af;">📞 Telefon: Girilmemiş</div>'
        html += '</div>'
        return format_html(html)
    contact_info_display.short_description = "İletişim Bilgileri"
    
    def social_media_display(self, obj):
        links = []
        if obj.instagram:
            links.append(f'<a href="https://instagram.com/{obj.instagram.lstrip("@")}" target="_blank" style="color: #e4405f; text-decoration: none; margin-right: 12px;">📷 Instagram: @{obj.instagram.lstrip("@")}</a>')
        if obj.facebook:
            links.append(f'<a href="https://facebook.com/{obj.facebook}" target="_blank" style="color: #1877f2; text-decoration: none; margin-right: 12px;">👤 Facebook: {obj.facebook}</a>')
        if obj.twitter:
            links.append(f'<a href="https://twitter.com/{obj.twitter.lstrip("@")}" target="_blank" style="color: #1da1f2; text-decoration: none; margin-right: 12px;">🐦 Twitter: @{obj.twitter.lstrip("@")}</a>')
        if obj.whatsapp:
            links.append(f'<a href="https://wa.me/{obj.whatsapp.replace("+", "").replace(" ", "").replace("-", "")}" target="_blank" style="color: #25d366; text-decoration: none; margin-right: 12px;">💬 WhatsApp: {obj.whatsapp}</a>')
        
        if links:
            return format_html(
                f'<div style="padding: 12px; background: #fef3c7; border-radius: 8px; border-left: 4px solid #f59e0b;">'
                f'{"<br>".join(links)}'
                f'</div>'
            )
        return format_html('<div style="padding: 12px; background: #f3f4f6; border-radius: 8px; color: #9ca3af;">Sosyal medya linki girilmemiş</div>')
    social_media_display.short_description = "Sosyal Medya Linkleri"
    
    def stats_display(self, obj):
        staff_count = obj.staff.count() if hasattr(obj, 'staff') else 0
        services_count = obj.services.count() if hasattr(obj, 'services') else 0
        
        return format_html(
            f'''
            <div style="padding: 16px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; color: white; margin: 10px 0;">
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;">
                    <div>
                        <div style="font-size: 24px; font-weight: bold;">⭐ {obj.rating_avg:.1f if obj.rating_avg else "0.0"}</div>
                        <div style="font-size: 12px; opacity: 0.9;">{obj.total_reviews} yorum</div>
                    </div>
                    <div>
                        <div style="font-size: 24px; font-weight: bold;">❤️ {obj.favorites_count}</div>
                        <div style="font-size: 12px; opacity: 0.9;">Favori</div>
                    </div>
                    <div>
                        <div style="font-size: 24px; font-weight: bold;">👁️ {getattr(obj, "_views_count", 0)}</div>
                        <div style="font-size: 12px; opacity: 0.9;">Görüntülenme</div>
                    </div>
                    <div>
                        <div style="font-size: 24px; font-weight: bold;">👥 {staff_count}</div>
                        <div style="font-size: 12px; opacity: 0.9;">Personel</div>
                    </div>
                    <div>
                        <div style="font-size: 24px; font-weight: bold;">✂️ {services_count}</div>
                        <div style="font-size: 12px; opacity: 0.9;">Hizmet</div>
                    </div>
                    <div>
                        <div style="font-size: 24px; font-weight: bold;">📷 {getattr(obj, "_images_count", 0) + (1 if obj.main_image else 0)}</div>
                        <div style="font-size: 12px; opacity: 0.9;">Görsel</div>
                    </div>
                </div>
            </div>
            '''
        )
    stats_display.short_description = "İstatistikler"
    
    def categories_display(self, obj):
        categories = obj.categories.all() if hasattr(obj, 'categories') else []
        if categories:
            category_names = ", ".join([cat.name for cat in categories])
            return format_html(
                f'<div style="padding: 8px; background: #ede9fe; border-radius: 6px; color: #6d28d9; font-weight: 500;">{category_names}</div>'
            )
        return format_html('<span style="color: #9ca3af;">Kategori seçilmemiş</span>')
    categories_display.short_description = "Seçili Kategoriler"


@admin.register(BarbershopAppeal)
class BarbershopAppealAdmin(ModelAdmin):
    list_display = ("id", "barbershop_link", "message_snippet", "status_badge", "created_at", "reviewed_at", "reviewed_by")
    list_display_links = ("id", "barbershop_link", "message_snippet")
    list_filter = ("status", "created_at")
    search_fields = ("message", "barbershop__name")
    readonly_fields = ("barbershop", "message", "created_at", "reviewed_at", "reviewed_by")
    date_hierarchy = "created_at"
    list_per_page = 25
    ordering = ["-created_at"]

    fieldsets = (
        ("İtiraz", {"fields": ("barbershop", "message", "status", "created_at")}),
        ("İnceleme", {"fields": ("reviewed_at", "reviewed_by"), "classes": ("collapse",)}),
    )

    def barbershop_link(self, obj):
        if not obj.barbershop_id:
            return "-"
        url = reverse("admin:barbers_barbershop_change", args=[obj.barbershop_id])
        return format_html('<a href="{}">{}</a>', url, obj.barbershop.name)
    barbershop_link.short_description = "Salon"

    def message_snippet(self, obj):
        if not obj.message:
            return "-"
        return (obj.message[:80] + "…") if len(obj.message) > 80 else obj.message
    message_snippet.short_description = "İtiraz metni"

    def status_badge(self, obj):
        if obj.status == "pending":
            return format_html('<span style="color: #d97706; font-weight: 600;">Beklemede</span>')
        return format_html('<span style="color: #059669;">İncelendi</span>')
    status_badge.short_description = "Durum"

    def save_model(self, request, obj, form, change):
        if change and form.cleaned_data.get("status") == BarbershopAppeal.Status.REVIEWED:
            if not obj.reviewed_at:
                obj.reviewed_at = timezone.now()
            if not obj.reviewed_by_id:
                obj.reviewed_by = request.user
        super().save_model(request, obj, form, change)


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

    def changelist_view(self, request, *args, **kwargs):
        self._request = request
        return super().changelist_view(request, *args, **kwargs)

    def changeform_view(self, request, *args, **kwargs):
        self._request = request
        return super().changeform_view(request, *args, **kwargs)

    def image_preview(self, obj):
        if obj.image:
            try:
                url = obj.image.url
            except (ValueError, OSError):
                return format_html('<span style="color: #dc2626;">Yüklenemedi</span>')
            req = getattr(self, "_request", None)
            url = _absolute_media_url(req, url)
            return format_html(f'<img src="{url}" style="height: 50px; border-radius: 4px;" alt="" />')
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
    
    def has_delete_permission(self, request, obj=None):
        """Yorum verileri silinemez - istatistikler için sürekli saklanmalı"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Yorum verileri değiştirilemez - sadece görüntülenebilir"""
        return False


@admin.register(Favorite)
class FavoriteAdmin(ModelAdmin):
    list_display = ("user", "barbershop", "created_at")
    list_filter = ("created_at", "barbershop")
    search_fields = ("user__email", "barbershop__name")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    autocomplete_fields = ("user", "barbershop")
    
    def has_delete_permission(self, request, obj=None):
        """Favori verileri silinemez - istatistikler için sürekli saklanmalı"""
        return False
    
    def has_add_permission(self, request):
        """Sadece API üzerinden eklenebilir"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Favori verileri değiştirilemez - sadece görüntülenebilir"""
        return False


@admin.register(ViewEvent)
class ViewEventAdmin(ModelAdmin):
    list_display = ("barbershop", "user", "device_id", "viewed_at")
    list_filter = ("viewed_at", "barbershop")
    search_fields = ("barbershop__name", "user__email", "device_id")
    readonly_fields = ("viewed_at",)
    date_hierarchy = "viewed_at"
    autocomplete_fields = ("barbershop", "user")
    
    def has_delete_permission(self, request, obj=None):
        """Görüntülenme verileri silinemez - istatistikler için sürekli saklanmalı"""
        return False
    
    def has_add_permission(self, request):
        """Sadece API üzerinden eklenebilir"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Görüntülenme verileri değiştirilemez - sadece görüntülenebilir"""
        return False


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


@admin.register(BarbershopCatalog)
class BarbershopCatalogAdmin(ModelAdmin):
    list_display = ("id", "barbershop", "name", "image_preview", "is_active", "order", "created_at")
    list_display_links = ("id", "barbershop", "name")
    list_filter = ("barbershop", "is_active", "created_at")
    search_fields = ("name", "description", "barbershop__name")
    autocomplete_fields = ("barbershop",)
    readonly_fields = ("image_thumb", "created_at", "updated_at")
    date_hierarchy = "created_at"
    
    def changelist_view(self, request, *args, **kwargs):
        self._request = request
        return super().changelist_view(request, *args, **kwargs)
    
    def image_preview(self, obj):
        if obj.image:
            from django.utils.html import format_html
            return format_html('<img src="{}" style="max-width: 100px; max-height: 100px;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Görsel"
