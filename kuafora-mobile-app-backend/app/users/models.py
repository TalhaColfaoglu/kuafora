from __future__ import annotations

import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
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


class UserManager(BaseUserManager):
    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    image = models.ImageField(upload_to="users/images/", null=True, blank=True)
    full_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=6, choices=Gender.choices, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old_instance = User.objects.get(pk=self.pk)
                if self.image != old_instance.image:
                    resize_image(self.image)
            except User.DoesNotExist:
                resize_image(self.image)
        else:
            resize_image(self.image)
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.email


class UserAddress(models.Model):
    user = models.ForeignKey("User", on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=50, blank=True, default="")
    address_line = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.user.email} - {self.label}"
