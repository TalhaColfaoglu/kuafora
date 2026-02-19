from django import forms
from django.contrib import admin
from django.contrib import messages
from django.http import Http404, HttpRequest
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action
from .models import SubscriptionPlan, Subscription, Coupon, CouponUsage
from .services import apply_coupon_to_subscription


class QuickApplyCouponForm(forms.Form):
    """Admin için: Salon + Kupon seçimi ile hızlı kupon uygulama formu."""

    barbershop = forms.ModelChoiceField(
        queryset=None,
        label="Kuaför Salonu",
        empty_label="— Salon seçin —",
        widget=forms.Select(attrs={"class": "vTextField", "style": "min-width:320px"}),
    )
    coupon = forms.ModelChoiceField(
        queryset=None,
        label="Kupon",
        empty_label="— Kupon seçin —",
        widget=forms.Select(attrs={"class": "vTextField", "style": "min-width:320px"}),
    )

    def __init__(self, *args, **kwargs):
        from app.barbers.models import Barbershop
        super().__init__(*args, **kwargs)
        self.fields['barbershop'].queryset = (
            Barbershop.objects.filter(is_verified=True).order_by('name')
        )
        self.fields['coupon'].queryset = (
            Coupon.objects.filter(is_active=True)
            .exclude(discount_type='lifetime')
            .order_by('code')
        )

    def label_from_instance_barbershop(self, obj):
        sub = getattr(obj, '_cached_sub', None)
        return f"{obj.name} — {sub.get_status_display() if sub else 'Abonelik yok'}"


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
    change_form_template = "admin/subscriptions/subscription/change_form.html"
    list_display = (
        'barbershop',
        'plan',
        'status_badge',
        'remaining_days_display',
        'coupon_info',
        'quick_apply_link',
        'created_at',
    )
    list_filter = ('status', 'plan', 'created_at')
    search_fields = ('barbershop__name', 'coupon__code')
    readonly_fields = ('created_at', 'updated_at', 'started_at')
    inlines = [CouponUsageInline]
    actions = ['make_lifetime', 'extend_trial_30_days']

    class ApplyCouponCodeForm(forms.Form):
        coupon_code = forms.CharField(
            label="Kupon Kodu",
            max_length=50,
            help_text="Uygulanacak kupon kodu (örn. ILK200, HOSGELDINIZ).",
            widget=forms.TextInput(attrs={"class": "vTextField", "placeholder": "ILK200"}),
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "quick-apply/",
                self.admin_site.admin_view(self.quick_apply_coupon_view),
                name="subscriptions_subscription_quick_apply",
            ),
            path(
                "<path:object_id>/apply-coupon/",
                self.admin_site.admin_view(self.apply_coupon_view),
                name="subscriptions_subscription_apply_coupon",
            ),
        ]
        return custom + urls

    def quick_apply_coupon_view(self, request: HttpRequest):
        """Salon seç + Kupon seç → uygula. Tek adımda hızlı kupon ekleme."""
        from app.barbers.models import Barbershop
        from app.subscriptions.models import SubscriptionPlan

        form = QuickApplyCouponForm(request.POST or None)
        subscription_info = None

        if request.method == "POST" and form.is_valid():
            barbershop = form.cleaned_data["barbershop"]
            coupon = form.cleaned_data["coupon"]

            subscription = Subscription.objects.filter(barbershop=barbershop).first()
            if subscription is None:
                plan = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order').first()
                subscription = Subscription.objects.create(
                    barbershop=barbershop,
                    plan=plan,
                    status='trial',
                    trial_ends_at=timezone.now() + timezone.timedelta(days=30),
                )

            result = apply_coupon_to_subscription(subscription=subscription, coupon=coupon)
            if result.ok:
                messages.success(
                    request,
                    f"✓ '{coupon.code}' kuponu '{barbershop.name}' salonuna uygulandı.",
                )
                return redirect(
                    reverse("admin:subscriptions_subscription_change", args=[subscription.pk])
                )
            else:
                messages.error(request, result.error or "Kupon uygulanamadı.")
                subscription_info = subscription

        # GET veya hatalı POST'ta önceden seçilmiş salon varsa bilgi göster
        if request.method == "GET":
            barbershop_id = request.GET.get("barbershop_id")
            if barbershop_id:
                form.initial["barbershop"] = barbershop_id
                try:
                    subscription_info = Subscription.objects.get(
                        barbershop_id=barbershop_id
                    )
                except Subscription.DoesNotExist:
                    pass

        context = dict(
            self.admin_site.each_context(request),
            title="Hızlı Kupon Uygula",
            form=form,
            subscription_info=subscription_info,
            opts=self.model._meta,
            active_coupons=Coupon.objects.filter(is_active=True)
            .exclude(discount_type='lifetime')
            .order_by('code'),
        )
        return render(request, "admin/subscriptions/quick_apply_coupon.html", context)

    def apply_coupon_view(self, request: HttpRequest, object_id: str):
        """Belirli bir aboneliğe kupon uygula (subscription detail page'den açılır)."""
        subscription = self.get_object(request, object_id)
        if subscription is None:
            raise Http404("Abonelik bulunamadı")

        if request.method == "POST":
            form = self.ApplyCouponCodeForm(request.POST)
            if form.is_valid():
                code = form.cleaned_data["coupon_code"].strip().upper()
                try:
                    coupon = Coupon.objects.get(code=code)
                except Coupon.DoesNotExist:
                    messages.error(request, "Kupon bulunamadı.")
                else:
                    result = apply_coupon_to_subscription(subscription=subscription, coupon=coupon)
                    if result.ok:
                        messages.success(request, "Kupon başarıyla uygulandı.")
                        return redirect(
                            reverse("admin:subscriptions_subscription_change", args=[subscription.pk])
                        )
                    messages.error(request, result.error or "Kupon uygulanamadı.")
        else:
            form = self.ApplyCouponCodeForm()

        context = dict(
            self.admin_site.each_context(request),
            title="Kupon Uygula",
            subscription=subscription,
            form=form,
            opts=self.model._meta,
            original=subscription,
        )
        return render(request, "admin/subscriptions/apply_coupon.html", context)

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
            '<span class="px-2 py-1 rounded text-xs font-medium {}">{}</span>',
            color_class,
            obj.get_status_display(),
        )
    status_badge.short_description = "Durum"

    def remaining_days_display(self, obj):
        """Kalan gün sayısını duruma göre renkli göster."""
        now = timezone.now()
        if obj.status == 'lifetime':
            return format_html('<span class="text-purple-600 font-bold">♾ Ömür Boyu</span>')
        if obj.status == 'trial' and obj.trial_ends_at:
            days = (obj.trial_ends_at.date() - now.date()).days
            if days > 7:
                return format_html('<span class="text-green-600 font-bold">{} gün</span>', days)
            elif days > 0:
                return format_html('<span class="text-orange-500 font-bold">{} gün ⚠</span>', days)
            else:
                return format_html('<span class="text-red-600 font-bold">Süresi doldu</span>')
        if obj.status == 'active' and obj.current_period_end:
            days = (obj.current_period_end.date() - now.date()).days
            if days > 14:
                return format_html('<span class="text-green-600 font-bold">{} gün</span>', days)
            elif days > 0:
                return format_html('<span class="text-orange-500 font-bold">{} gün ⚠</span>', days)
            else:
                return format_html('<span class="text-red-600 font-bold">Süresi doldu</span>')
        if obj.status == 'grace_period':
            return format_html('<span class="text-orange-600 font-bold">Grace</span>')
        return format_html('<span class="text-gray-400">—</span>')
    remaining_days_display.short_description = "Kalan Süre"

    def coupon_info(self, obj):
        if obj.coupon:
            return format_html(
                '<span class="bg-yellow-100 text-yellow-800 px-2 py-1 rounded text-xs">{}</span>',
                obj.coupon.code,
            )
        return "—"
    coupon_info.short_description = "Kupon"

    def quick_apply_link(self, obj):
        url = reverse("admin:subscriptions_subscription_apply_coupon", args=[obj.pk])
        return format_html(
            '<a href="{}" class="text-xs text-blue-600 hover:underline">🎟 Kupon Ekle</a>',
            url,
        )
    quick_apply_link.short_description = "İşlem"
    
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
