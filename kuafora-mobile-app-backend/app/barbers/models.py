from __future__ import annotations

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from datetime import date
from PIL import Image, ImageOps
from io import BytesIO
from django.core.files.base import ContentFile
import os

def process_image(image_field, thumb_field=None, max_size=(1080, 1080), thumb_size=(300, 300)):
    if not image_field:
        return

    try:
        # Open image
        img = Image.open(image_field)
        
        # Handle EXIF orientation
        img = ImageOps.exif_transpose(img)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            
        # 1. Optimize Main Image
        # Only resize if larger than max_size
        if img.width > max_size[0] or img.height > max_size[1]:
            img_copy = img.copy()
            img_copy.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            buffer = BytesIO()
            img_copy.save(buffer, format='JPEG', quality=85)
            
            filename = os.path.basename(image_field.name)
            base_name, _ = os.path.splitext(filename)
            filename = f"{base_name}.jpg"
            
            # Save optimized main image
            image_field.save(filename, ContentFile(buffer.getvalue()), save=False)
        
        # 2. Generate Thumbnail if field provided
        # Thumbnail'i ortadan kare crop yaparak oluştur (baskılamadan)
        if thumb_field:
            thumb_copy = img.copy()
            
            # Görselin ortasından kare bir kısmı kes (baskılamadan)
            # Yatay görsel: yüksekliğe göre kare, Dikey görsel: genişliğe göre kare
            width, height = thumb_copy.size
            if width > height:
                # Yatay görsel: yüksekliğe göre kare kes
                left = (width - height) // 2
                right = left + height
                thumb_copy = thumb_copy.crop((left, 0, right, height))
            elif height > width:
                # Dikey görsel: genişliğe göre kare kes
                top = (height - width) // 2
                bottom = top + width
                thumb_copy = thumb_copy.crop((0, top, width, bottom))
            # Zaten kare ise değişiklik yok
            
            # Şimdi kare görseli istenen boyuta küçült (aspect ratio korunur çünkü zaten kare)
            thumb_copy.thumbnail(thumb_size, Image.Resampling.LANCZOS)
            
            thumb_buffer = BytesIO()
            thumb_copy.save(thumb_buffer, format='JPEG', quality=80)
            
            filename = os.path.basename(image_field.name)
            base_name, _ = os.path.splitext(filename)
            thumb_filename = f"{base_name}_thumb.jpg"
            
            # Save thumbnail
            thumb_field.save(thumb_filename, ContentFile(thumb_buffer.getvalue()), save=False)

    except Exception as e:
        print(f"Error processing image: {e}")

class ShopCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, default="")
    icon = models.ImageField(upload_to="categories/icons/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Shop Categories"

    def __str__(self):
        return self.name

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
    main_image_thumb = models.ImageField(upload_to="barbershops/main/thumbs/", null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False, help_text="Admin onayı - onaylanmadan ana uygulamada görünmez")
    rejection_reason = models.TextField(blank=True, null=True, help_text="Reddetme nedeni (admin tarafından doldurulur)")
    rejected_at = models.DateTimeField(blank=True, null=True, help_text="Reddetme tarihi")
    google_maps_link = models.CharField(max_length=500, blank=True, null=True, help_text="Google Maps konum linki (örn: https://maps.app.goo.gl/...)")
    description = models.TextField(blank=True)
    categories = models.ManyToManyField(ShopCategory, blank=True, related_name="barbershops")
    system_type = models.CharField(
        max_length=15,
        choices=[
            ("info", "Information"),
            ("booking", "Kuafora Booking"),
            ("external", "External Booking")
        ],
        default="info",
        help_text="Isletme sistem modu: info, booking veya external"
    )
    external_booking = models.JSONField(
        default=dict,
        blank=True,
        help_text="Harici randevu yontemleri: whatsapp, website, instagram, other_app, custom"
    )
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

    # Social Media
    instagram = models.CharField(max_length=100, blank=True)
    facebook = models.CharField(max_length=100, blank=True)
    twitter = models.CharField(max_length=100, blank=True)
    whatsapp = models.CharField(max_length=100, blank=True)
    features = models.JSONField(default=list, blank=True)

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old_instance = Barbershop.objects.get(pk=self.pk)
                if self.main_image != old_instance.main_image:
                    # Image changed
                    process_image(self.main_image, self.main_image_thumb)
            except Barbershop.DoesNotExist:
                process_image(self.main_image, self.main_image_thumb)
        else:
            process_image(self.main_image, self.main_image_thumb)
        super().save(*args, **kwargs)

    class Meta:
        # Performance: Database indexes for frequently queried fields
        # Note: Django indexes don't support related fields (subscription__status)
        # Use select_related('subscription') in queries for related field filtering
        indexes = [
            # Filtering indexes - most common queries
            models.Index(fields=['is_approved', 'is_verified', 'city']),
            # Location-based queries
            models.Index(fields=['city', 'district']),
            models.Index(fields=['latitude', 'longitude']),
            # Sorting and filtering
            models.Index(fields=['-created_at']),  # Newest shops
            models.Index(fields=['-rating_avg']),  # Top rated shops
            # Combined filtering for approved/verified shops
            models.Index(fields=['is_verified', 'is_approved', 'city']),
        ]
        ordering = ['-created_at']

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class BarbershopImage(models.Model):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="barbershops/extra/")
    image_thumb = models.ImageField(upload_to="barbershops/extra/thumbs/", null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old_instance = BarbershopImage.objects.get(pk=self.pk)
                if self.image != old_instance.image:
                    process_image(self.image, self.image_thumb)
            except BarbershopImage.DoesNotExist:
                process_image(self.image, self.image_thumb)
        else:
            process_image(self.image, self.image_thumb)
        super().save(*args, **kwargs)


class Staff(models.Model):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="staff")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profiles")
    photo = models.ImageField(upload_to="staff/photos/", null=True, blank=True)
    photo_thumb = models.ImageField(upload_to="staff/photos/thumbs/", null=True, blank=True)
    email = models.EmailField()
    certificate = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    total_reviews = models.PositiveIntegerField(default=0, editable=False)
    
    # Personel profil bilgileri
    bio = models.TextField(blank=True, help_text="Personel hakkında açıklama")
    gender_preference = models.CharField(
        max_length=10,
        choices=[
            ('all', 'Herkese Hizmet'),
            ('male', 'Sadece Erkek'),
            ('female', 'Sadece Kadın'),
        ],
        default='all'
    )
    experience_years = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Kuaförlük deneyimi (yıl)"
    )
    career_start_year = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Kuaförlüğe başladığı yıl (YYYY)"
    )
    tags = models.JSONField(
        default=list, blank=True,
        help_text="Uzmanlık etiketleri: ['boyama_ustasi', '20_yillik_usta', ...]"
    )
    rating_avg = models.FloatField(default=0, editable=False)
    
    # Social Media
    instagram = models.CharField(max_length=100, blank=True)
    facebook = models.CharField(max_length=100, blank=True)
    twitter = models.CharField(max_length=100, blank=True)
    whatsapp = models.CharField(max_length=100, blank=True)
    
    # Randevu sistemi için (şimdilik boş kalabilir)
    auto_approval = models.BooleanField(
        default=False,
        help_text="Randevular otomatik onayla mı?"
    )
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Personelin yaptığı hizmetten alacağı pay (yüzde)"
    )
    appointment_interval = models.PositiveIntegerField(
        default=15,
        choices=[(5, '5 dk'), (10, '10 dk'), (15, '15 dk'), (20, '20 dk'), (30, '30 dk')],
        help_text="Randevu aralığı (dakika)"
    )

    # Not: Duplicate kayıtlar endpoint seviyesinde güvenli şekilde ele alınıyor (filter().first(), distinct()).
    # DB seviyesinde unique kısıt eklemek mevcut verilerdeki çoğullardan dolayı deploy sırasında migrate'i kilitliyor.

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old_instance = Staff.objects.get(pk=self.pk)
                if self.photo != old_instance.photo:
                    process_image(self.photo, self.photo_thumb)
            except Staff.DoesNotExist:
                process_image(self.photo, self.photo_thumb)
        else:
            process_image(self.photo, self.photo_thumb)
        super().save(*args, **kwargs)


class StaffCatalogImage(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="catalog")
    image = models.ImageField(upload_to="staff/catalog/")

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old_instance = StaffCatalogImage.objects.get(pk=self.pk)
                if self.image != old_instance.image:
                    # Just resize, no thumb for catalog for now as per request mainly for main/profile lists
                    process_image(self.image) 
            except StaffCatalogImage.DoesNotExist:
                process_image(self.image)
        else:
            process_image(self.image)
        super().save(*args, **kwargs)


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
    break_start_time = models.TimeField(null=True, blank=True)
    break_end_time = models.TimeField(null=True, blank=True)
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
    break_start_time = models.TimeField(null=True, blank=True)
    break_end_time = models.TimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False, help_text="Bu gün personel çalışmıyor")
    
    # Versioning
    valid_from = models.DateField(default=date(2020, 1, 1))
    valid_until = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("staff", "day_of_week", "valid_from")

    def __str__(self) -> str:
        return f"{self.staff.user.email} - {self.get_day_of_week_display()} ({self.valid_from})"


class ScheduleChangeRequest(models.Model):
    """
    Planlanmış çalışma saati değişiklikleri.
    Eğer effective_date gelecekteyse, bu modelde saklanır ve cron ile uygulanır.
    """
    class TargetType(models.TextChoices):
        SHOP = "shop", "Shop"
        STAFF = "staff", "Staff"

    target_type = models.CharField(max_length=10, choices=TargetType.choices)
    target_id = models.IntegerField(help_text="Staff ID veya Barbershop ID")
    new_schedule_json = models.JSONField(help_text="Uygulanacak yeni saat verisi (list of dicts)")
    effective_date = models.DateField()
    applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["effective_date", "applied"]),
        ]

    def __str__(self) -> str:
        return f"{self.target_type} {self.target_id} -> {self.effective_date}"



class BreakWindow(models.Model):
    """Gün bazlı mola aralıkları; dükkan veya personel kapsamı."""

    class Scope(models.TextChoices):
        SHOP = "shop", "Dükkan"
        STAFF = "staff", "Personel"

    barbershop = models.ForeignKey(
        Barbershop,
        on_delete=models.CASCADE,
        related_name="break_windows",
        help_text="Molanın bağlı olduğu dükkan",
    )
    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name="break_windows",
        null=True,
        blank=True,
        help_text="Personel molaları için zorunlu",
    )
    scope = models.CharField(max_length=10, choices=Scope.choices)
    date = models.DateField(help_text="Molayı kapsayan gün")
    start_time = models.TimeField()
    end_time = models.TimeField()
    label = models.CharField(max_length=120, blank=True, help_text="Örn: Yemek molası")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        help_text="Molayı ekleyen kullanıcı",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.scope} break on {self.date} ({self.start_time}-{self.end_time})"

# --- Re-added Missing Models ---

class ServiceCategory(models.Model):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="service_categories")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("barbershop", "name")
        ordering = ["id"]

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


class StaffService(models.Model):
    """
    Bir personelin sunduğu hizmet ve o hizmet için belirlediği fiyat/süre.
    Dükkan hizmetlerinden seçilir; personel kendi fiyat ve süresini belirler.
    """
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="staff_services")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="staff_offerings")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("staff", "service")
        ordering = ["service__name"]
    
    def __str__(self):
        return f"{self.staff.email} - {self.service.name} (₺{self.price})"


class StaffServiceCategory(models.Model):
    """
    Bir personelin sunduğu hizmet kategorileri.
    Personel dükkanın mevcut kategorilerinden seçim yapar.
    """
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="staff_categories")
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name="staff_offerings")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ("staff", "category")
        ordering = ["category__name"]
    
    def __str__(self):
        return f"{self.staff.email} - {self.category.name}"


class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="reviews")
    staff = models.ForeignKey(
        Staff, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reviews",
        help_text="Hangi personele yapılan yorum (opsiyonel)"
    )
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    # --- NEW FIELDS ---
    reply = models.TextField(blank=True, null=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    # ------------------
    is_anonymous = models.BooleanField(default=False)
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="liked_reviews")
    dislikes = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="disliked_reviews")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'barbershop', 'staff'],
                name='unique_user_barbershop_staff_review'
            )
        ]


class ReviewReply(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="replies")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_replies")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("review", "user")  # Bir review'a bir kullanıcı sadece bir kez cevap verebilir

    def __str__(self) -> str:
        return f"Reply to review {self.review.id} by {self.user.email}"


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "barbershop")
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.user.email} -> {self.barbershop.name}"


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


class DailyOverride(models.Model):
    """Bugüne özel manuel şalter. En yüksek öncelik. Gün sonunda süre aşımıyla geçersiz.

    Not: Sadece gün bazlı çalışır; saatlik değil. status=open/closed.
    """
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="daily_overrides")
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    note = models.CharField(max_length=200, blank=True)
    expires_at = models.DateTimeField(help_text="Genellikle gün sonu 23:59:59")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_daily_overrides")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("barbershop", "date")
        indexes = [models.Index(fields=["barbershop", "-date"]) ]

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
    user: Giriş yapmış kullanıcı (opsiyonel - misafirler için null)
    device_id: Cihaz benzersiz ID'si (misafir kullanıcıları takip etmek için)
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="barbershop_view_events", null=True, blank=True)
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="view_events")
    device_id = models.CharField(max_length=100, null=True, blank=True, help_text="Cihaz benzersiz ID'si - misafir kullanıcılar için")
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["barbershop", "-viewed_at"]),
            models.Index(fields=["barbershop", "user"]),
            models.Index(fields=["barbershop", "device_id"]),
        ]

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
