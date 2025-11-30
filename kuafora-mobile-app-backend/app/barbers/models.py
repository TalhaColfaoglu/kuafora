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

def resize_image(image_field, max_size=(1080, 1080)):
    if not image_field:
        return

    try:
        img = Image.open(image_field)
        
        # Handle EXIF orientation
        img = ImageOps.exif_transpose(img)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            
        # Check if resize is needed
        if img.width > max_size[0] or img.height > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            
            filename = os.path.basename(image_field.name)
            # Ensure extension is .jpg
            base_name, _ = os.path.splitext(filename)
            filename = f"{base_name}.jpg"
            
            image_field.save(filename, ContentFile(buffer.getvalue()), save=False)
    except Exception as e:
        print(f"Error resizing image: {e}")

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
    categories = models.ManyToManyField("ShopCategory", blank=True, related_name="barbershops")
    system_type = models.CharField(
        max_length=10,
        choices=[("info", "Information"), ("booking", "Booking")],
        default="info",
        help_text="Isletme sistem modu: info veya booking"
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
                    resize_image(self.main_image)
            except Barbershop.DoesNotExist:
                resize_image(self.main_image)
        else:
            resize_image(self.main_image)
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


class BarbershopImage(models.Model):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="barbershops/extra/")

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old_instance = BarbershopImage.objects.get(pk=self.pk)
                if self.image != old_instance.image:
                    resize_image(self.image)
            except BarbershopImage.DoesNotExist:
                resize_image(self.image)
        else:
            resize_image(self.image)
        super().save(*args, **kwargs)


class Staff(models.Model):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="staff")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profiles")
    photo = models.ImageField(upload_to="staff/photos/", null=True, blank=True)
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
                    resize_image(self.photo)
            except Staff.DoesNotExist:
                resize_image(self.photo)
        else:
            resize_image(self.photo)
        super().save(*args, **kwargs)


class StaffCatalogImage(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="catalog")
    image = models.ImageField(upload_to="staff/catalog/")

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old_instance = StaffCatalogImage.objects.get(pk=self.pk)
                if self.image != old_instance.image:
                    resize_image(self.image)
            except StaffCatalogImage.DoesNotExist:
                resize_image(self.image)
        else:
            resize_image(self.image)
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

# This was missing in the original file but referenced in Barbershop.categories
class ShopCategory(models.Model):
    name = models.CharField(max_length=100)
    icon = models.ImageField(upload_to="categories/", null=True, blank=True)
    
    def __str__(self) -> str:
        return self.name
