from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import SubscriptionPlan, Subscription, Coupon, CouponUsage


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'price_display', 'booking_systems_display', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    ordering = ('sort_order', 'price_monthly')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'description')
        }),
        ('Fiyatlandırma', {
            'fields': ('price_monthly', 'price_yearly')
        }),
        ('Özellikler', {
            'fields': ('features', 'booking_system_types')
        }),
        ('Ayarlar', {
            'fields': ('is_active', 'sort_order')
        }),
    )
    
    def price_display(self, obj):
        return f"{obj.price_monthly}₺/ay"
    price_display.short_description = "Fiyat"
    
    def booking_systems_display(self, obj):
        types = obj.booking_system_types or []
        return ", ".join(types) if types else "-"
    booking_systems_display.short_description = "Sistemler"


class CouponUsageInline(admin.TabularInline):
    model = CouponUsage
    extra = 0
    readonly_fields = ('coupon', 'subscription', 'applied_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'barbershop', 
        'plan', 
        'status_badge', 
        'trial_info',
        'coupon_info',
        'created_at'
    )
    list_filter = ('status', 'plan', 'created_at')
    search_fields = ('barbershop__name', 'coupon__code')
    readonly_fields = ('created_at', 'updated_at', 'started_at')
    raw_id_fields = ('barbershop', 'coupon')
    inlines = [CouponUsageInline]
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('barbershop', 'plan', 'status')
        }),
        ('Tarihler', {
            'fields': ('started_at', 'trial_ends_at', 'current_period_start', 'current_period_end')
        }),
        ('Kupon', {
            'fields': ('coupon', 'coupon_applied_at')
        }),
        ('Ödeme (İleride)', {
            'fields': ('payment_provider', 'payment_customer_id'),
            'classes': ('collapse',)
        }),
        ('Bildirimler', {
            'fields': ('trial_warning_sent', 'grace_warning_sent'),
            'classes': ('collapse',)
        }),
        ('Sistem Bilgileri', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'trial': '#3B82F6',  # blue
            'active': '#10B981',  # green
            'lifetime': '#8B5CF6',  # purple
            'grace_period': '#F59E0B',  # orange
            'suspended': '#EF4444',  # red
            'cancelled': '#6B7280',  # gray
        }
        color = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Durum"
    
    def trial_info(self, obj):
        if obj.status == 'trial':
            days = obj.days_until_trial_ends
            if days is not None:
                color = '#10B981' if days > 7 else '#F59E0B' if days > 0 else '#EF4444'
                return format_html(
                    '<span style="color: {}; font-weight: 600;">{} gün</span>',
                    color,
                    days
                )
        return "-"
    trial_info.short_description = "Trial"
    
    def coupon_info(self, obj):
        if obj.coupon:
            return format_html(
                '<span style="background-color: #FEF3C7; color: #92400E; padding: 2px 6px; '
                'border-radius: 3px; font-size: 11px;">{}</span>',
                obj.coupon.code
            )
        return "-"
    coupon_info.short_description = "Kupon"
    
    actions = ['make_lifetime', 'extend_trial_30_days']
    
    def make_lifetime(self, request, queryset):
        updated = queryset.update(status='lifetime')
        self.message_user(request, f'{updated} abonelik ömür boyu yapıldı.')
    make_lifetime.short_description = "Seçilenleri ömür boyu yap"
    
    def extend_trial_30_days(self, request, queryset):
        for sub in queryset:
            sub.trial_ends_at = sub.trial_ends_at + timezone.timedelta(days=30)
            sub.save()
        self.message_user(request, f'{queryset.count()} aboneliğin trial süresi 30 gün uzatıldı.')
    extend_trial_30_days.short_description = "Trial süresini 30 gün uzat"


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        'code', 
        'discount_badge',
        'usage_info',
        'validity_info',
        'is_valid_badge',
        'created_at'
    )
    list_filter = ('discount_type', 'is_active', 'created_at')
    search_fields = ('code', 'description')
    readonly_fields = ('current_uses', 'created_at', 'updated_at')
    filter_horizontal = ('applicable_plans',)
    inlines = [CouponUsageInline]
    
    fieldsets = (
        ('Kupon Bilgileri', {
            'fields': ('code', 'description')
        }),
        ('İndirim', {
            'fields': ('discount_type', 'discount_value')
        }),
        ('Kısıtlamalar', {
            'fields': ('max_uses', 'current_uses', 'valid_from', 'valid_until', 'applicable_plans')
        }),
        ('Durum', {
            'fields': ('is_active', 'created_by')
        }),
        ('Sistem Bilgileri', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def discount_badge(self, obj):
        colors = {
            'lifetime': '#8B5CF6',  # purple
            'free_months': '#10B981',  # green
            'percent': '#3B82F6',  # blue
            'fixed': '#F59E0B',  # orange
        }
        color = colors.get(obj.discount_type, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.discount_display
        )
    discount_badge.short_description = "İndirim"
    
    def usage_info(self, obj):
        if obj.max_uses:
            percent = (obj.current_uses / obj.max_uses) * 100
            color = '#10B981' if percent < 80 else '#F59E0B' if percent < 100 else '#EF4444'
            return format_html(
                '<span style="color: {};">{}/{}</span>',
                color,
                obj.current_uses,
                obj.max_uses
            )
        return f"{obj.current_uses}/∞"
    usage_info.short_description = "Kullanım"
    
    def validity_info(self, obj):
        now = timezone.now()
        if obj.valid_until:
            if obj.valid_until < now:
                return format_html('<span style="color: #EF4444;">Süresi doldu</span>')
            days_left = (obj.valid_until - now).days
            return f"{days_left} gün kaldı"
        return "Süresiz"
    validity_info.short_description = "Geçerlilik"
    
    def is_valid_badge(self, obj):
        if obj.is_valid:
            return format_html(
                '<span style="color: #10B981; font-weight: 600;">✓ Geçerli</span>'
            )
        return format_html(
            '<span style="color: #EF4444; font-weight: 600;">✗ Geçersiz</span>'
        )
    is_valid_badge.short_description = "Durum"
    
    actions = ['deactivate_coupons', 'activate_coupons']
    
    def deactivate_coupons(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} kupon pasif yapıldı.')
    deactivate_coupons.short_description = "Seçilen kuponları pasif yap"
    
    def activate_coupons(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} kupon aktif yapıldı.')
    activate_coupons.short_description = "Seçilen kuponları aktif yap"
    
    def save_model(self, request, obj, form, change):
        if not change:  # Yeni kupon oluşturulurken
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'subscription', 'barbershop_name', 'applied_at')
    list_filter = ('coupon', 'applied_at')
    search_fields = ('coupon__code', 'subscription__barbershop__name')
    readonly_fields = ('coupon', 'subscription', 'applied_at')
    
    def barbershop_name(self, obj):
        return obj.subscription.barbershop.name
    barbershop_name.short_description = "Kuaför Salonu"
    
    def has_add_permission(self, request):
        return False  # Manuel ekleme yok, sadece API'den
    
    def has_change_permission(self, request, obj=None):
        return False
