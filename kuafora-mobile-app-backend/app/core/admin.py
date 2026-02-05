from django.contrib import admin
from .models import AppVersion


@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    list_display = [
        'platform',
        'version_name',
        'version_code',
        'force_update',
        'is_active',
        'release_date',
    ]
    list_filter = ['platform', 'force_update', 'is_active', 'release_date']
    search_fields = ['version_name', 'version_code']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('platform', 'version_name', 'version_code', 'is_active')
        }),
        ('Güncelleme Ayarları', {
            'fields': ('force_update', 'min_version_code', 'update_message')
        }),
        ('Store Bilgileri', {
            'fields': ('play_store_url',)
        }),
        ('Tarih Bilgileri', {
            'fields': ('release_date', 'created_at', 'updated_at')
        }),
    )
