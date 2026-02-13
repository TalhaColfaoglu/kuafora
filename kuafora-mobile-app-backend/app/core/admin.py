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
        'force_update_display',
        'min_version_display',
        'is_active_display',
        'release_date',
    ]
    list_filter = ['platform', 'app_type', 'force_update', 'is_active', 'release_date']
    search_fields = ['version_name', 'version_code', 'update_message']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_active']
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
    
    actions = ['activate_versions', 'deactivate_versions', 'set_force_update', 'unset_force_update']
    
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
    
    def force_update_display(self, obj):
        if obj.force_update:
            return format_html(
                '<span style="background: #f44336; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">⚠️ ZORUNLU</span>'
            )
        return format_html('<span style="color: #999;">İsteğe bağlı</span>')
    force_update_display.short_description = 'Güncelleme Türü'
    
    def min_version_display(self, obj):
        if obj.min_version_code:
            return format_html(
                '<span style="background: #ff9800; color: white; padding: 3px 8px; border-radius: 3px;">Build &lt; {}</span>',
                obj.min_version_code
            )
        return '-'
    min_version_display.short_description = 'Min. Versiyon'
    
    def is_active_display(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: #4caf50; font-weight: bold;">✅ Aktif</span>'
            )
        return format_html('<span style="color: #999;">❌ Pasif</span>')
    is_active_display.short_description = 'Durum'
    
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
