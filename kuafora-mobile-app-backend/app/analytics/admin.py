from django.contrib import admin
from app.analytics.models import (
    AppEvent, ScreenView, FeatureUsage, UserSession,
    DailyMetrics, UserActivityLog
)


@admin.register(AppEvent)
class AppEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'app_type', 'user', 'platform', 'timestamp']
    list_filter = ['event_type', 'app_type', 'platform', 'timestamp']
    search_fields = ['user__email', 'session_id', 'device_id']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def has_delete_permission(self, request, obj=None):
        """İstatistik verileri silinemez - sürekli saklanmalı"""
        return False
    
    def has_add_permission(self, request):
        """Sadece API üzerinden eklenebilir"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """İstatistik verileri değiştirilemez"""
        return False


@admin.register(ScreenView)
class ScreenViewAdmin(admin.ModelAdmin):
    list_display = ['screen_name', 'app_type', 'user', 'view_duration', 'timestamp']
    list_filter = ['screen_name', 'app_type', 'timestamp']
    search_fields = ['screen_name', 'user__email', 'session_id', 'device_id']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def has_delete_permission(self, request, obj=None):
        """İstatistik verileri silinemez - sürekli saklanmalı"""
        return False
    
    def has_add_permission(self, request):
        """Sadece API üzerinden eklenebilir"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """İstatistik verileri değiştirilemez"""
        return False


@admin.register(FeatureUsage)
class FeatureUsageAdmin(admin.ModelAdmin):
    list_display = ['feature_type', 'app_type', 'user', 'success', 'timestamp']
    list_filter = ['feature_type', 'app_type', 'success', 'timestamp']
    search_fields = ['feature_type', 'user__email', 'session_id', 'device_id']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def has_delete_permission(self, request, obj=None):
        """İstatistik verileri silinemez - sürekli saklanmalı"""
        return False
    
    def has_add_permission(self, request):
        """Sadece API üzerinden eklenebilir"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """İstatistik verileri değiştirilemez"""
        return False


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'app_type', 'platform', 'start_time', 'duration', 'screen_count', 'event_count']
    list_filter = ['app_type', 'platform', 'start_time']
    search_fields = ['session_id', 'user__email', 'device_id']
    readonly_fields = ['start_time', 'duration', 'screen_count', 'event_count']
    date_hierarchy = 'start_time'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def has_delete_permission(self, request, obj=None):
        """İstatistik verileri silinemez - sürekli saklanmalı"""
        return False
    
    def has_add_permission(self, request):
        """Sadece API üzerinden eklenebilir"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """İstatistik verileri değiştirilemez"""
        return False


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_id', 'app_type', 'activity_date', 'login_count', 'last_activity']
    list_filter = ['app_type', 'activity_date']
    search_fields = ['user__email', 'device_id']
    readonly_fields = ['user', 'device_id', 'app_type', 'activity_date', 'login_count', 'last_activity']
    date_hierarchy = 'activity_date'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def has_delete_permission(self, request, obj=None):
        """İstatistik verileri silinemez"""
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        """Sadece otomatik olarak oluşturulur"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """İstatistik verileri değiştirilemez"""
        return False


@admin.register(DailyMetrics)
class DailyMetricsAdmin(admin.ModelAdmin):
    list_display = [
        'date', 
        'daily_active_users', 
        'weekly_active_users',
        'monthly_active_users',
        'daily_registrations',
        'retention_rate',
        'churn_rate',
        'conversion_rate'
    ]
    list_filter = ['date']
    search_fields = ['date']
    readonly_fields = [
        'date',
        'total_users',
        'app_users_total',
        'daily_active_users',
        'daily_registrations',
        'weekly_active_users',
        'weekly_registrations',
        'monthly_active_users',
        'monthly_registrations',
        'yearly_active_users',
        'yearly_registrations',
        'total_barbershops',
        'approved_barbershops',
        'total_appointments',
        'daily_appointments',
        'retention_rate',
        'churn_rate',
        'conversion_rate',
        'created_at',
        'updated_at'
    ]
    date_hierarchy = 'date'
    
    def has_delete_permission(self, request, obj=None):
        """Sadece superuser silebilir"""
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        """Management command ile oluşturulur"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Management command ile güncellenir"""
        return False
