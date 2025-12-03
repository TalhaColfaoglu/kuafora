from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action
from .models import SubscriptionPlan, Subscription, Coupon, CouponUsage


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(ModelAdmin):
    list_display = ('name', 'slug', 'price_display', 'booking_systems_display', 'is_active_badge', 'sort_order')
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

    def is_active_badge(self, obj):
        return format_html('<span class="text-green-600">✓</span>') if obj.is_active else format_html('<span class="text-red-600">✗</span>')
    is_active_badge.short_description = "Aktif"


class CouponUsageInline(TabularInline):
    model = CouponUsage
    extra = 0
    readonly_fields = ('coupon', 'subscription', 'applied_at')
    can_delete = False
    tab = True
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
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
    inlines = [CouponUsageInline]
    actions = ['make_lifetime', 'extend_trial_30_days']
    
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
            'trial': 'bg-blue-100 text-blue-800',
            'active': 'bg-green-100 text-green-800',
            'lifetime': 'bg-purple-100 text-purple-800',
            'grace_period': 'bg-orange-100 text-orange-800',
            'suspended': 'bg-red-100 text-red-800',
            'cancelled': 'bg-gray-100 text-gray-800',
        }
        color_class = colors.get(obj.status, 'bg-gray-100 text-gray-800')
        return format_html(
            f'<span class="px-2 py-1 rounded text-xs font-medium {color_class}">{obj.get_status_display()}</span>'
        )
    status_badge.short_description = "Durum"
    
    def trial_info(self, obj):
        if obj.status == 'trial':
            days = obj.days_until_trial_ends
            if days is not None:
                color = 'text-green-600' if days > 7 else 'text-orange-600' if days > 0 else 'text-red-600'
                return format_html(
                    f'<span class="{color} font-bold">{days} gün</span>'
                )
        return "-"
    trial_info.short_description = "Trial"
    
    def coupon_info(self, obj):
        if obj.coupon:
            return format_html(
                f'<span class="bg-yellow-100 text-yellow-800 px-2 py-1 rounded text-xs">{obj.coupon.code}</span>'
            )
        return "-"
    coupon_info.short_description = "Kupon"
    
    @action(description="Seçilenleri ömür boyu yap")
    def make_lifetime(self, request, queryset):
        updated = queryset.update(status='lifetime')
        self.message_user(request, f'{updated} abonelik ömür boyu yapıldı.')
    
    @action(description="Trial süresini 30 gün uzat")
    def extend_trial_30_days(self, request, queryset):
        for sub in queryset:
            sub.trial_ends_at = sub.trial_ends_at + timezone.timedelta(days=30)
            sub.save()
        self.message_user(request, f'{queryset.count()} aboneliğin trial süresi 30 gün uzatıldı.')


@admin.register(Coupon)
class CouponAdmin(ModelAdmin):
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
    actions = ['deactivate_coupons', 'activate_coupons']
    
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
            'lifetime': 'bg-purple-100 text-purple-800',
            'free_months': 'bg-green-100 text-green-800',
            'percent': 'bg-blue-100 text-blue-800',
            'fixed': 'bg-orange-100 text-orange-800',
        }
        color_class = colors.get(obj.discount_type, 'bg-gray-100 text-gray-800')
        return format_html(
            f'<span class="px-2 py-1 rounded text-xs font-medium {color_class}">{obj.discount_display}</span>'
        )
    discount_badge.short_description = "İndirim"
    
    def usage_info(self, obj):
        if obj.max_uses:
            percent = (obj.current_uses / obj.max_uses) * 100
            color = 'text-green-600' if percent < 80 else 'text-orange-600' if percent < 100 else 'text-red-600'
            return format_html(
                f'<span class="{color}">{obj.current_uses}/{obj.max_uses}</span>'
            )
        return f"{obj.current_uses}/∞"
    usage_info.short_description = "Kullanım"
    
    def validity_info(self, obj):
        now = timezone.now()
        if obj.valid_until:
            if obj.valid_until < now:
                return format_html('<span class="text-red-600">Süresi doldu</span>')
            days_left = (obj.valid_until - now).days
            return f"{days_left} gün kaldı"
        return "Süresiz"
    validity_info.short_description = "Geçerlilik"
    
    def is_valid_badge(self, obj):
        if obj.is_valid:
            return format_html('<span class="text-green-600 font-bold">✓ Geçerli</span>')
        return format_html('<span class="text-red-600 font-bold">✗ Geçersiz</span>')
    is_valid_badge.short_description = "Durum"
    
    @action(description="Seçilen kuponları pasif yap")
    def deactivate_coupons(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} kupon pasif yapıldı.')
    
    @action(description="Seçilen kuponları aktif yap")
    def activate_coupons(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} kupon aktif yapıldı.')
    
    def save_model(self, request, obj, form, change):
        if not change:  # Yeni kupon oluşturulurken
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CouponUsage)
class CouponUsageAdmin(ModelAdmin):
    list_display = ('coupon', 'subscription', 'barbershop_name', 'applied_at')
    list_filter = ('coupon', 'applied_at')
    search_fields = ('coupon__code', 'subscription__barbershop__name')
    readonly_fields = ('coupon', 'subscription', 'applied_at')
    
    def barbershop_name(self, obj):
        return obj.subscription.barbershop.name
    barbershop_name.short_description = "Kuaför Salonu"
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
