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
        if thumb_field:
            thumb_copy = img.copy()
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
    image_thumb = models.ImageField(upload_to="users/images/thumbs/", null=True, blank=True)
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
                    # Delete old images if they exist
                    if old_instance.image:
                        try:
                            old_instance.image.delete(save=False)
                        except Exception as e:
                            print(f"Error deleting old user image: {e}")
                    if old_instance.image_thumb:
                        try:
                            old_instance.image_thumb.delete(save=False)
                        except Exception as e:
                            print(f"Error deleting old user thumbnail: {e}")
                    # Process new image
                    process_image(self.image, self.image_thumb)
            except User.DoesNotExist:
                process_image(self.image, self.image_thumb)
        else:
            process_image(self.image, self.image_thumb)
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
