from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from .models import User, UserAddress
from django.db.models import F


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("full_name", "first_name", "last_name", "email", "password", "gender", "phone")

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        first = validated_data.pop("first_name", "").strip()
        last = validated_data.pop("last_name", "").strip()
        def _normalize(n: str) -> str:
            # İlk harf büyük, kalan küçük olacak şekilde normalize et
            # Çoklu boşlukları da tek boşluğa indir.
            return " ".join([p[:1].upper() + p[1:].lower() if p else "" for p in n.split()]).strip()

        if not validated_data.get("full_name"):
            validated_data["full_name"] = _normalize((first + " " + last).strip())
        else:
            validated_data["full_name"] = _normalize(validated_data.get("full_name", ""))
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, attrs):
        email = (attrs.get("email") or "").strip().lower()
        password = (attrs.get("password") or "")

        if not email or not password:
            raise serializers.ValidationError({"detail": "E-posta ve şifre zorunludur.", "reason": "missing_fields"})

        # We intentionally distinguish common cases so the app can show the right message.
        # Note: This reveals whether the email exists. This is acceptable here because the
        # mobile flow already calls /auth/check-email/ before login.
        user_obj = User.objects.filter(email__iexact=email).only("id", "email", "is_active", "password", "email_verified").first()
        if not user_obj:
            raise serializers.ValidationError({"detail": "Bu e-posta ile kayıt bulunamadı.", "reason": "user_not_found"})

        if not user_obj.is_active:
            raise serializers.ValidationError({"detail": "Hesabınız banlanmış veya pasif durumda.", "reason": "banned"})

        # Check password explicitly for a clearer error than generic authenticate(None).
        if not user_obj.check_password(password):
            raise serializers.ValidationError({"detail": "Şifre yanlış.", "reason": "wrong_password"})

        if not getattr(user_obj, "email_verified", False):
            raise serializers.ValidationError({"detail": "E-posta doğrulanmadı.", "reason": "email_not_verified"})

        # Re-run authenticate to keep backend compatibility / future-proofing.
        user = authenticate(request=self.context.get("request"), email=email, password=password)
        if not user:
            # Fallback: should be rare if the above checks passed.
            raise serializers.ValidationError({"detail": "E-posta veya şifre hatalı.", "reason": "invalid_credentials"})

        attrs["user"] = user
        attrs["email"] = email
        return attrs


from drf_spectacular.utils import extend_schema_field

class UserSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(read_only=True)
    image_thumb = serializers.ImageField(read_only=True)
    image_url = serializers.SerializerMethodField()
    image_thumb_url = serializers.SerializerMethodField()
    ban_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "email_verified",
            "email_verified_at",
            "full_name",
            "phone",
            "gender",
            "image",
            "image_thumb",
            "image_url",
            "image_thumb_url",
            "ban_status",
        )
        read_only_fields = ("id", "email_verified", "email_verified_at", "image", "image_thumb", "image_url", "image_thumb_url")
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_image_url(self, obj):
        return obj.image.url if obj.image else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_image_thumb_url(self, obj):
        return obj.image_thumb.url if obj.image_thumb else None

    @extend_schema_field(serializers.DictField)
    def get_ban_status(self, obj):
        from app.appointments.models import CustomerBan
        from django.utils import timezone
        active_ban = CustomerBan.objects.filter(user=obj, end_date__gte=timezone.now().date()).first()
        if active_ban:
            return {
                "is_banned": True,
                "end_date": active_ban.end_date,
                "reason": active_ban.reason
            }
        return None


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("full_name", "gender")

    def validate_full_name(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            return value
        return " ".join([p[:1].upper() + p[1:].lower() if p else "" for p in value.split()]).strip()

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyEmailCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=4, max_length=12)


class PhoneSerializer(serializers.Serializer):
    phone = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = ("id", "city", "district", "is_default", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, allow_blank=True)


class BarbershopStatsSerializer(serializers.Serializer):
    favorites_count = serializers.IntegerField()
    views_count = serializers.IntegerField()
