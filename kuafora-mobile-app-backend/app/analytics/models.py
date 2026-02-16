from django.db import models
from django.db.models import Q
from django.utils import timezone
from app.users.models import User


class AppEvent(models.Model):
    """Uygulama açılma/kapanma ve genel event tracking"""
    
    EVENT_TYPES = [
        ('app_open', 'Uygulama Açıldı'),
        ('app_close', 'Uygulama Kapandı'),
        ('app_background', 'Uygulama Arka Plan'),
        ('app_foreground', 'Uygulama Ön Plan'),
    ]
    
    APP_TYPES = [
        ('main', 'Ana Uygulama'),
        ('partner', 'Partner Uygulaması'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='app_events',
        null=True,
        blank=True,
        help_text="Kullanıcı giriş yapmamışsa null olabilir"
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    app_type = models.CharField(max_length=10, choices=APP_TYPES)
    session_id = models.CharField(max_length=100, db_index=True, help_text="Oturum ID'si")
    device_id = models.CharField(max_length=200, db_index=True, help_text="Cihaz benzersiz ID")
    platform = models.CharField(max_length=20, help_text="iOS, Android, Web")
    app_version = models.CharField(max_length=50, blank=True, help_text="Uygulama versiyonu")
    os_version = models.CharField(max_length=50, blank=True, help_text="İşletim sistemi versiyonu")
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'analytics_app_events'
        indexes = [
            models.Index(fields=['timestamp', 'event_type']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['app_type', 'timestamp']),
            models.Index(fields=['session_id']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.event_type} - {self.app_type} - {self.timestamp}"


class ScreenView(models.Model):
    """Ekran görüntüleme tracking"""
    
    APP_TYPES = [
        ('main', 'Ana Uygulama'),
        ('partner', 'Partner Uygulaması'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='screen_views',
        null=True,
        blank=True
    )
    screen_name = models.CharField(max_length=200, db_index=True, help_text="Ekran adı (örn: HomeScreen, BarberDetailScreen)")
    app_type = models.CharField(max_length=10, choices=APP_TYPES)
    session_id = models.CharField(max_length=100, db_index=True)
    device_id = models.CharField(max_length=200, db_index=True)
    view_duration = models.FloatField(null=True, blank=True, help_text="Görüntüleme süresi (saniye)")
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    metadata = models.JSONField(default=dict, blank=True, help_text="Ek bilgiler (barbershop_id, campaign_id vb.)")
    
    class Meta:
        db_table = 'analytics_screen_views'
        indexes = [
            models.Index(fields=['timestamp', 'screen_name']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['app_type', 'screen_name']),
            models.Index(fields=['session_id']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.screen_name} - {self.app_type} - {self.timestamp}"


class FeatureUsage(models.Model):
    """Özellik kullanım tracking"""
    
    FEATURE_TYPES = [
        ('favorite_toggle', 'Favori Ekleme/Çıkarma'),
        ('review_create', 'Yorum Oluşturma'),
        ('search', 'Arama'),
        ('filter', 'Filtreleme'),
        ('map_view', 'Harita Görünümü'),
        ('appointment_create', 'Randevu Oluşturma'),
        ('campaign_view', 'Kampanya Görüntüleme'),
        ('chat_send', 'Mesaj Gönderme'),
        ('profile_edit', 'Profil Düzenleme'),
        ('settings_change', 'Ayarlar Değiştirme'),
    ]
    
    APP_TYPES = [
        ('main', 'Ana Uygulama'),
        ('partner', 'Partner Uygulaması'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='feature_usages',
        null=True,
        blank=True
    )
    feature_type = models.CharField(max_length=50, choices=FEATURE_TYPES, db_index=True)
    app_type = models.CharField(max_length=10, choices=APP_TYPES)
    session_id = models.CharField(max_length=100, db_index=True)
    device_id = models.CharField(max_length=200, db_index=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    metadata = models.JSONField(default=dict, blank=True, help_text="Ek bilgiler (barbershop_id, search_query vb.)")
    success = models.BooleanField(default=True, help_text="İşlem başarılı mı?")
    
    class Meta:
        db_table = 'analytics_feature_usages'
        indexes = [
            models.Index(fields=['timestamp', 'feature_type']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['app_type', 'feature_type']),
            models.Index(fields=['session_id']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.feature_type} - {self.app_type} - {self.timestamp}"


class UserSession(models.Model):
    """Kullanıcı oturum tracking"""
    
    APP_TYPES = [
        ('main', 'Ana Uygulama'),
        ('partner', 'Partner Uygulaması'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions',
        null=True,
        blank=True
    )
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    device_id = models.CharField(max_length=200, db_index=True)
    app_type = models.CharField(max_length=10, choices=APP_TYPES)
    platform = models.CharField(max_length=20)
    app_version = models.CharField(max_length=50, blank=True)
    os_version = models.CharField(max_length=50, blank=True)
    start_time = models.DateTimeField(default=timezone.now, db_index=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True, help_text="Oturum süresi (saniye)")
    screen_count = models.IntegerField(default=0, help_text="Görüntülenen ekran sayısı")
    event_count = models.IntegerField(default=0, help_text="Toplam event sayısı")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'analytics_user_sessions'
        indexes = [
            models.Index(fields=['start_time', 'end_time']),
            models.Index(fields=['user', 'start_time']),
            models.Index(fields=['app_type', 'start_time']),
            models.Index(fields=['session_id']),
            models.Index(fields=['device_id', 'start_time']),
        ]
        ordering = ['-start_time']
    
    def __str__(self):
        return f"Session {self.session_id} - {self.app_type} - {self.start_time}"
    
    def calculate_duration(self):
        """Oturum süresini hesapla"""
        if self.end_time:
            delta = self.end_time - self.start_time
            self.duration = delta.total_seconds()
            self.save(update_fields=['duration'])
        return self.duration


class DailyMetrics(models.Model):
    """Günlük metrics snapshot - Dashboard için tarihsel veri saklama"""
    
    date = models.DateField(unique=True, db_index=True, help_text="Metrik günü")
    
    # Kullanıcı metrikleri
    total_users = models.IntegerField(default=0, help_text="Toplam kullanıcı sayısı")
    app_users_total = models.IntegerField(default=0, help_text="Uygulama kullanıcıları (staff hariç)")
    daily_active_users = models.IntegerField(default=0, help_text="O gün aktif olan kullanıcılar")
    daily_registrations = models.IntegerField(default=0, help_text="O gün kayıt olan kullanıcılar")
    
    # 7 günlük metrikleri
    weekly_active_users = models.IntegerField(default=0, help_text="Son 7 gün aktif kullanıcılar")
    weekly_registrations = models.IntegerField(default=0, help_text="Son 7 gün kayıtlar")
    
    # 30 günlük metrikleri
    monthly_active_users = models.IntegerField(default=0, help_text="Son 30 gün aktif kullanıcılar")
    monthly_registrations = models.IntegerField(default=0, help_text="Son 30 gün kayıtlar")
    
    # Yıllık metrikleri
    yearly_active_users = models.IntegerField(default=0, help_text="Son 365 gün aktif kullanıcılar")
    yearly_registrations = models.IntegerField(default=0, help_text="Son 365 gün kayıtlar")
    
    # Barbershop metrikleri
    total_barbershops = models.IntegerField(default=0)
    approved_barbershops = models.IntegerField(default=0)
    
    # Randevu metrikleri
    total_appointments = models.IntegerField(default=0)
    daily_appointments = models.IntegerField(default=0)
    
    # Retention/Churn
    retention_rate = models.FloatField(default=0.0, help_text="Tutma oranı (%)")
    churn_rate = models.FloatField(default=0.0, help_text="Ayrılma oranı (%)")
    conversion_rate = models.FloatField(default=0.0, help_text="Dönüşüm oranı (%)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_daily_metrics'
        ordering = ['-date']
        verbose_name = "Günlük Metrik"
        verbose_name_plural = "Günlük Metrikler"
    
    def __str__(self):
        return f"Metrics for {self.date}"


class UserActivityLog(models.Model):
    """Kullanıcı aktivite logu - Her giriş için bir kayıt (aktif kullanıcı takibi için)"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activity_logs',
        null=True,
        blank=True
    )
    device_id = models.CharField(max_length=200, db_index=True, help_text="Cihaz ID")
    app_type = models.CharField(
        max_length=10,
        choices=[('main', 'Ana Uygulama'), ('partner', 'Partner Uygulaması')],
        default='main'
    )
    activity_date = models.DateField(db_index=True, help_text="Aktivite günü")
    login_count = models.IntegerField(default=1, help_text="O gün giriş sayısı")
    last_activity = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'analytics_user_activity_log'
        unique_together = [['user', 'device_id', 'activity_date', 'app_type']]
        constraints = [
            # Guest (user=NULL) kayıtlarında Postgres'te NULL unique_together'ı bozabilir.
            # Bu partial unique constraint ile aynı gün/cihaz için duplicate guest kayıtlarını engelleriz.
            models.UniqueConstraint(
                fields=['device_id', 'activity_date', 'app_type'],
                condition=Q(user__isnull=True),
                name='uniq_guest_device_day_app',
            ),
        ]
        indexes = [
            models.Index(fields=['activity_date', 'app_type']),
            models.Index(fields=['device_id', 'activity_date']),
            models.Index(fields=['user', 'activity_date']),
        ]
        ordering = ['-activity_date']
    
    def __str__(self):
        user_str = self.user.email if self.user else f"Device {self.device_id[:8]}"
        return f"{user_str} - {self.activity_date}"

