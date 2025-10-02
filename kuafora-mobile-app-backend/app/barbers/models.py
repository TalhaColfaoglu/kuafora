from __future__ import annotations

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Barbershop(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        UNISEX = "unisex", "Unisex"

    name = models.CharField(max_length=200)
    gender = models.CharField(max_length=7, choices=Gender.choices)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    main_image = models.ImageField(upload_to="barbershops/main/", null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    rating_avg = models.FloatField(default=0, editable=False)
    total_reviews = models.PositiveIntegerField(default=0, editable=False)
    # denormalized star buckets
    star_1_count = models.PositiveIntegerField(default=0, editable=False)
    star_2_count = models.PositiveIntegerField(default=0, editable=False)
    star_3_count = models.PositiveIntegerField(default=0, editable=False)
    star_4_count = models.PositiveIntegerField(default=0, editable=False)
    star_5_count = models.PositiveIntegerField(default=0, editable=False)
    views_weekly = models.PositiveIntegerField(default=0, editable=False)
    favorites_count = models.PositiveIntegerField(default=0, editable=False)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class BarbershopImage(models.Model):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="barbershops/extra/")


class Staff(models.Model):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="staff")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profiles")
    photo = models.ImageField(upload_to="staff/photos/", null=True, blank=True)
    email = models.EmailField()
    certificate = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    total_reviews = models.PositiveIntegerField(default=0, editable=False)


class StaffCatalogImage(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="catalog")
    image = models.ImageField(upload_to="staff/catalog/")


class WorkSchedule(models.Model):
    class Weekday(models.TextChoices):
        MON = "Mon", "Monday"
        TUE = "Tue", "Tuesday"
        WED = "Wed", "Wednesday"
        THU = "Thu", "Thursday"
        FRI = "Fri", "Friday"
        SAT = "Sat", "Saturday"
        SUN = "Sun", "Sunday"

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="work_schedules")
    day_of_week = models.CharField(max_length=3, choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_time = models.PositiveIntegerField(default=0, help_text="Break time in minutes")


class ShopWorkingHours(models.Model):
    """Genel dükkan çalışma saatleri - admin tarafından belirlenir"""
    class Weekday(models.TextChoices):
        MON = "MON", "Monday"
        TUE = "TUE", "Tuesday"
        WED = "WED", "Wednesday"
        THU = "THU", "Thursday"
        FRI = "FRI", "Friday"
        SAT = "SAT", "Saturday"
        SUN = "SUN", "Sunday"

    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="shop_working_hours")
    day_of_week = models.CharField(max_length=3, choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_closed = models.BooleanField(default=False, help_text="Bu gün tamamen kapalı mı")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("barbershop", "day_of_week")

    def __str__(self) -> str:
        return f"{self.barbershop.name} - {self.get_day_of_week_display()}"


class StaffWorkingHours(models.Model):
    """Personel varsayılan çalışma saatleri - dükkan saatlerini override edebilir"""
    class Weekday(models.TextChoices):
        MON = "MON", "Monday"
        TUE = "TUE", "Tuesday"
        WED = "WED", "Wednesday"
        THU = "THU", "Thursday"
        FRI = "FRI", "Friday"
        SAT = "SAT", "Saturday"
        SUN = "SUN", "Sunday"

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="staff_working_hours")
    day_of_week = models.CharField(max_length=3, choices=Weekday.choices)
    start_time = models.TimeField(null=True, blank=True, help_text="Boşsa dükkan saatlerini devralır")
    end_time = models.TimeField(null=True, blank=True, help_text="Boşsa dükkan saatlerini devralır")
    is_closed = models.BooleanField(default=False, help_text="Bu gün personel çalışmıyor")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("staff", "day_of_week")

    def __str__(self) -> str:
        return f"{self.staff.user.email} - {self.get_day_of_week_display()}"


class Override(models.Model):
    """Özel durumlar - global dükkan veya personel bazlı override'lar"""
    class OverrideType(models.TextChoices):
        SHOP_GLOBAL = "shop_global", "Dükkan Global Override"
        STAFF_INDIVIDUAL = "staff_individual", "Personel Override"

    class OverrideScope(models.TextChoices):
        FULL_DAY_CLOSED = "full_day_closed", "Tüm Gün Kapalı"
        EARLY_CLOSING = "early_closing", "Erken Kapanış"
        LATE_OPENING = "late_opening", "Geç Açılış"
        TIME_RANGE_CLOSED = "time_range_closed", "Belirli Saat Aralığı Kapalı"

    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="overrides")
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="overrides", null=True, blank=True)
    override_type = models.CharField(max_length=20, choices=OverrideType.choices)
    override_scope = models.CharField(max_length=20, choices=OverrideScope.choices)
    
    # Tarih bilgileri
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Boşsa tek gün, doluysa tarih aralığı")
    start_time = models.TimeField(null=True, blank=True, help_text="Saat aralığı override'ları için")
    end_time = models.TimeField(null=True, blank=True, help_text="Saat aralığı override'ları için")
    
    # Tekrarlama (opsiyonel)
    is_recurring = models.BooleanField(default=False)
    recurring_rule = models.CharField(max_length=100, blank=True, help_text="Örn: her ayın ilk pazartesi")
    
    # Meta bilgiler
    reason = models.CharField(max_length=200, blank=True, help_text="Override sebebi")
    is_active = models.BooleanField(default=True, help_text="Override aktif mi?")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_overrides")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        staff_name = f" - {self.staff.user.email}" if self.staff else ""
        return f"{self.barbershop.name}{staff_name} - {self.get_override_scope_display()}"
    
    def save(self, *args, **kwargs):
        """Auto-deactivate if end_date is in the past"""
        from django.utils import timezone
        if self.end_date and self.end_date < timezone.now().date():
            self.is_active = False
        super().save(*args, **kwargs)


class SpecialMessage(models.Model):
    """Özel mesajlar - duyurular bölümünde listelenir"""
    class MessageSource(models.TextChoices):
        AUTOMATIC = "automatic", "Otomatik (Sistem)"
        MANUAL = "manual", "Manuel (Admin)"

    class DisplayType(models.TextChoices):
        BANNER = "banner", "Banner (Sayfada Kart)"
        POPUP = "popup", "Popup (Girişte Diyalog)"

    class TargetType(models.TextChoices):
        ALL_SHOP = "all_shop", "Tüm Dükkan"
        SPECIFIC_STAFF = "specific_staff", "Belirli Personel(ler)"

    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="special_messages")
    source = models.CharField(max_length=10, choices=MessageSource.choices)
    display_type = models.CharField(max_length=10, choices=DisplayType.choices, default="banner")
    target_type = models.CharField(max_length=15, choices=TargetType.choices)
    
    # Mesaj içeriği
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Hedefleme
    target_staff = models.ManyToManyField(Staff, blank=True, related_name="targeted_messages")
    
    # Yayın bilgileri
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    priority = models.IntegerField(default=0, help_text="Yüksek sayı = yüksek öncelik")
    
    # Meta bilgiler
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_messages", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        # Önceliği dikkate almıyoruz; her zaman en yeni üstte
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.barbershop.name} - {self.title}"


class MessageViewLog(models.Model):
    """Mesaj görüntülenme logları - popup'lar için özellikle önemli"""
    message = models.ForeignKey(SpecialMessage, on_delete=models.CASCADE, related_name="view_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="message_views", null=True, blank=True)
    device_id = models.CharField(max_length=100, help_text="Cihaz benzersiz ID'si")
    viewed_at = models.DateTimeField(auto_now_add=True)
    dismissed = models.BooleanField(default=False, help_text="Kullanıcı popup'ı kapattı mı")

    class Meta:
        unique_together = ("message", "device_id")

    def __str__(self) -> str:
        return f"{self.message.title} - {self.device_id}"


class CalendarAuditLog(models.Model):
    """Takvim değişikliklerinin audit log'u"""
    class ActionType(models.TextChoices):
        CREATE = "create", "Oluştur"
        UPDATE = "update", "Güncelle"
        DELETE = "delete", "Sil"
        OVERRIDE = "override", "Override Uygula"

    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="calendar_audit_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calendar_actions")
    action_type = models.CharField(max_length=10, choices=ActionType.choices)
    target_model = models.CharField(max_length=50, help_text="Hangi model değiştirildi")
    target_id = models.IntegerField(help_text="Değiştirilen kaydın ID'si")
    changes = models.JSONField(help_text="Yapılan değişiklikler")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.barbershop.name} - {self.get_action_type_display()} - {self.target_model}"


class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="reviews")
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "barbershop")


class ReviewReply(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="replies")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_replies")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("review", "user")  # Bir review'a bir kullanıcı sadece bir kez cevap verebilir

    def __str__(self) -> str:
        return f"Reply to review {self.review.id} by {self.user.email}"


class ServiceCategory(models.Model):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="service_categories")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("barbershop", "name")

    def __str__(self) -> str:
        return f"{self.barbershop.name} - {self.name}"


class Service(models.Model):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="services")
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name="services", null=True, blank=True)
    name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.PositiveIntegerField(help_text="Duration in minutes")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.barbershop.name} - {self.name}"


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "barbershop")
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.user.email} -> {self.barbershop.name}"





# --- Holidays & Special Days ---
class OfficialHoliday(models.Model):
    """Materialized list of official holidays (TR). Read-only for partners."""
    class HolidayType(models.TextChoices):
        NATIONAL = "national", "National"
        RELIGIOUS = "religious", "Religious"
        OBSERVANCE = "observance", "Observance"

    date = models.DateField(db_index=True)
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=12, choices=HolidayType.choices)
    country_code = models.CharField(max_length=2, default="TR", db_index=True)
    year = models.IntegerField(db_index=True)

    class Meta:
        unique_together = ("country_code", "date")
        ordering = ["date"]

    def __str__(self) -> str:
        return f"{self.date} - {self.name}"


class ShopHolidayOverride(models.Model):
    """Per shop decision for a given date (closed/open/custom hours or custom special day)."""
    class Status(models.TextChoices):
        CLOSED = "closed", "Closed all day"
        OPEN = "open", "Open all day"
        CUSTOM = "custom_hours", "Custom hours"

    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="holiday_overrides")
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    title = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="holiday_overrides")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("barbershop", "date")
        ordering = ["date"]

    def __str__(self) -> str:
        return f"{self.barbershop.name} - {self.date} - {self.status}"

class LastViewed(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="last_viewed")
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="viewed_by")
    viewed_at = models.DateTimeField(auto_now_add=True)  # renamed to match migrations

    class Meta:
        unique_together = ("user", "barbershop")
        indexes = [models.Index(fields=["user", "-viewed_at"])]


class ViewEvent(models.Model):
    """Her BarberDetailScreen ziyaretini ayrı kayıt eden etkinlik tablosu.
    Toplam görüntülenme ve unique kişi sayısı bu tablodan hesaplanır.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="barbershop_view_events")
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="view_events")
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["barbershop", "-viewed_at"]),
            models.Index(fields=["barbershop", "user"]),
        ]

