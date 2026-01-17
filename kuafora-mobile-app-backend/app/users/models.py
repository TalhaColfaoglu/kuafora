from __future__ import annotations

import uuid
from uuid import uuid4
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from PIL import Image, ImageOps
from io import BytesIO
from django.core.files.base import ContentFile
import os


def user_profile_image_upload_to(instance: "User", filename: str) -> str:
    # Keep per-user folder to avoid collisions across users
    return f"users/{instance.id}/images/{filename}"


def user_profile_thumb_upload_to(instance: "User", filename: str) -> str:
    return f"users/{instance.id}/images/thumbs/{filename}"

def process_image(image_field, thumb_field=None, max_size=(1080, 1080), thumb_size=(300, 300)):
    """Process and optimize image, create thumbnail"""
    if not image_field:
        print("⚠️ process_image: No image_field provided")
        return

    try:
        print(f"🔄 Processing image: {image_field.name}")
        
        # Open image
        img = Image.open(image_field)
        print(f"  → Original size: {img.size}, mode: {img.mode}")
        
        # Handle EXIF orientation
        img = ImageOps.exif_transpose(img)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            print(f"  → Converted to RGB")
            
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
            print(f"  → Main image optimized: {img_copy.size}")
        else:
            print(f"  → Main image size OK, no resize needed")
        
        # 2. Generate Thumbnail if field provided
        if thumb_field is not None:
            print(f"  → Creating thumbnail...")
            thumb_copy = img.copy()
            thumb_copy.thumbnail(thumb_size, Image.Resampling.LANCZOS)
            
            thumb_buffer = BytesIO()
            thumb_copy.save(thumb_buffer, format='JPEG', quality=80)
            
            filename = os.path.basename(image_field.name)
            base_name, _ = os.path.splitext(filename)
            thumb_filename = f"{base_name}_thumb.jpg"
            
            # Save thumbnail
            thumb_field.save(thumb_filename, ContentFile(thumb_buffer.getvalue()), save=False)
            print(f"  ✓ Thumbnail created: {thumb_copy.size} -> {thumb_filename}")
        else:
            print(f"  ⚠️ No thumb_field provided, skipping thumbnail")

    except Exception as e:
        print(f"❌ Error processing image: {e}")
        import traceback
        traceback.print_exc()


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
    image = models.ImageField(upload_to=user_profile_image_upload_to, null=True, blank=True)
    image_thumb = models.ImageField(upload_to=user_profile_thumb_upload_to, null=True, blank=True)
    full_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
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
        # Check if image has changed
        is_new_image = False
        if self.pk:
            try:
                old_instance = User.objects.get(pk=self.pk)
                is_new_image = self.image and self.image != old_instance.image
            except User.DoesNotExist:
                is_new_image = bool(self.image)
        else:
            is_new_image = bool(self.image)
        
        # Save first to ensure file is on disk
        super().save(*args, **kwargs)
        
        # Process image AFTER saving to ensure file exists on disk
        if is_new_image and self.image:
            print(f"🔄 Processing new image for user {self.id}")
            process_image(self.image, self.image_thumb)
            # Save again to update the thumbnail field
            super().save(update_fields=['image_thumb'])

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
