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
    is_verified = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    rating_avg = models.FloatField(default=0, editable=False)
    total_reviews = models.PositiveIntegerField(default=0, editable=False)
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


class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="reviews")
    rating = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Service(models.Model):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="services")
    category = models.CharField(max_length=100)
    name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.PositiveIntegerField(help_text="Duration in minutes")
    is_active = models.BooleanField(default=True)


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "barbershop")


