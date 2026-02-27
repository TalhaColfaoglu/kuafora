from django.contrib import admin
from django.utils.html import format_html
from .models import AppVersion


@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    list_display = [
        'platform_display',
        'app_type_display',
        'version_name',
        'version_code',
        'force_update',      # hızlı toggle
        'min_version_code',  # eşik (opsiyonel)
        'is_active',         # aktif kayıt
        'release_date',
    ]
    list_filter = ['platform', 'app_type', 'force_update', 'is_active', 'release_date']
    search_fields = ['version_name', 'version_code', 'update_message']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['force_update', 'min_version_code', 'is_active']
    ordering = ['-platform', '-app_type', '-version_code']
    
    fieldsets = (
        ('📱 Temel Bilgiler', {
            'fields': ('platform', 'app_type', 'version_name', 'version_code', 'is_active'),
            'description': 'Uygulamanın platform ve versiyon bilgileri'
        }),
        ('🔄 Güncelleme Ayarları', {
            'fields': ('force_update', 'min_version_code', 'update_message'),
            'description': 'Zorunlu güncelleme: force_update ✅ ise bu versiyondan eski tüm kullanıcılar güncellemek zorunda. min_version_code belirtilirse o build numarasından eski olanlar günceller.'
        }),
        ('🏪 Store Bilgileri', {
            'fields': ('play_store_url',),
            'description': 'Boş bırakılırsa otomatik Play Store/App Store URL\'i kullanılır'
        }),
        ('📅 Tarih Bilgileri', {
            'fields': ('release_date', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'activate_versions',
        'deactivate_versions',
        'set_force_update',
        'unset_force_update',
        'activate_as_only_active',
        'force_update_to_selected_build',
        'set_min_version_to_selected_build',
        'clear_min_version',
    ]
    
    def platform_display(self, obj):
        icons = {'android': '🤖', 'ios': '🍎'}
        colors = {'android': '#3DDC84', 'ios': '#000000'}
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            colors.get(obj.platform, '#000'),
            icons.get(obj.platform, ''),
            obj.get_platform_display()
        )
    platform_display.short_description = 'Platform'
    
    def app_type_display(self, obj):
        colors = {'main': '#2196F3', 'partner': '#FF9800'}
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.app_type, '#999'),
            obj.get_app_type_display()
        )
    app_type_display.short_description = 'Uygulama'
    
    # Actions
    def activate_versions(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} versiyon aktif edildi.')
    activate_versions.short_description = '✅ Seçili versiyonları aktif et'
    
    def deactivate_versions(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} versiyon pasif edildi.')
    deactivate_versions.short_description = '❌ Seçili versiyonları pasif et'
    
    def set_force_update(self, request, queryset):
        count = queryset.update(force_update=True)
        self.message_user(request, f'{count} versiyon zorunlu güncelleme olarak işaretlendi.')
    set_force_update.short_description = '⚠️ Zorunlu güncelleme yap'
    
    def unset_force_update(self, request, queryset):
        count = queryset.update(force_update=False)
        self.message_user(request, f'{count} versiyonun zorunlu güncelleme işareti kaldırıldı.')
    unset_force_update.short_description = '✓ Zorunlu güncellemeyi kaldır'

    def activate_as_only_active(self, request, queryset):
        """
        Seçilen kayıt(lar)ı kendi (platform, app_type) grubunda tek aktif yapar.
        Aynı grupta birden fazla seçilirse en yüksek version_code aktif kalır.
        """
        from .models import AppVersion
        updated = 0
        groups = {}
        for v in queryset:
            groups.setdefault((v.platform, v.app_type), []).append(v)
        for (platform, app_type), items in groups.items():
            winner = sorted(items, key=lambda x: x.version_code, reverse=True)[0]
            AppVersion.objects.filter(platform=platform, app_type=app_type).exclude(pk=winner.pk).update(is_active=False)
            if not winner.is_active:
                AppVersion.objects.filter(pk=winner.pk).update(is_active=True)
            updated += 1
        self.message_user(request, f'{updated} grup için tek aktif versiyon ayarlandı.')
    activate_as_only_active.short_description = '⭐ Seçileni grupta tek aktif yap (diğerlerini kapat)'

    def force_update_to_selected_build(self, request, queryset):
        """
        Seçilen build'i zorunlu güncelleme yapar ve kendi grubunda tek aktif hale getirir.
        """
        from .models import AppVersion
        updated = 0
        groups = {}
        for v in queryset:
            groups.setdefault((v.platform, v.app_type), []).append(v)
        for (platform, app_type), items in groups.items():
            winner = sorted(items, key=lambda x: x.version_code, reverse=True)[0]
            AppVersion.objects.filter(platform=platform, app_type=app_type).exclude(pk=winner.pk).update(is_active=False)
            AppVersion.objects.filter(pk=winner.pk).update(is_active=True, force_update=True)
            updated += 1
        self.message_user(request, f'{updated} grup için zorunlu güncelleme ayarlandı (seçilen build).')
    force_update_to_selected_build.short_description = '🚫 Zorunlu güncelleme (seçilen build) + tek aktif'

    def set_min_version_to_selected_build(self, request, queryset):
        """
        min_version_code = seçilen kaydın version_code.
        Bu, "build < X ise zorunlu" eşiğini hızlı ayarlamak için kullanılır.
        Not: Force update kapalıyken (force_update=False) min_version_code dikkate alınır.
        """
        from .models import AppVersion
        updated = 0
        for v in queryset:
            AppVersion.objects.filter(pk=v.pk).update(min_version_code=v.version_code)
            updated += 1
        self.message_user(request, f'{updated} kayıt için min_version_code = version_code yapıldı.')
    set_min_version_to_selected_build.short_description = '⬆️ min_version_code = seçilen build'

    def clear_min_version(self, request, queryset):
        count = queryset.update(min_version_code=None)
        self.message_user(request, f'{count} kaydın min_version_code alanı temizlendi.')
    clear_min_version.short_description = '🧹 min_version_code temizle'

    def save_model(self, request, obj, form, change):
        """
        Aynı (platform, app_type) için birden fazla aktif kayıt kafa karıştırıyor.
        Bir kayıt aktif kaydedilirse, aynı grubun diğerlerini otomatik pasifler.
        """
        super().save_model(request, obj, form, change)
        if obj.is_active:
            AppVersion.objects.filter(platform=obj.platform, app_type=obj.app_type).exclude(pk=obj.pk).update(is_active=False)
