from __future__ import annotations

from django.contrib.auth import authenticate, password_validation
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from .models import User, UserAddress


class UserSerializer(serializers.ModelSerializer):
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = (
            "id",
            "image",
            "full_name",
            "first_name",
            "last_name",
            "email",
            "phone",
            "gender",
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("is_active", "is_staff", "is_superuser", "created_at", "updated_at")

    def get_first_name(self, obj):
        parts = (obj.full_name or "").split()
        return parts[0] if parts else ""

    def get_last_name(self, obj):
        parts = (obj.full_name or "").split()
        return " ".join(parts[1:]) if len(parts) > 1 else ""


def _normalize_phone(value: str) -> str:
    if value is None:
        return ""
    # Keep leading '+' and digits only
    value = value.strip().replace(" ", "")
    if value.startswith("+"):
        prefix = "+"
        rest = "".join(ch for ch in value[1:] if ch.isdigit())
        return prefix + rest
    return "+" + "".join(ch for ch in value if ch.isdigit())


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("full_name", "first_name", "last_name", "email", "password", "gender", "phone")

    def validate_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        first = validated_data.pop("first_name", "").strip()
        last = validated_data.pop("last_name", "").strip()
        if not validated_data.get("full_name"):
            validated_data["full_name"] = (first + " " + last).strip()
        # Normalize and validate phone
        phone = validated_data.get("phone", "")
        phone = _normalize_phone(phone)
        validated_data["phone"] = phone
        if phone:
            # Enforce uniqueness at serializer level (DB may contain blanks)
            if User.objects.filter(phone=phone).exists():
                raise serializers.ValidationError({"phone": _("Phone number already in use")})
            # Basic format: +<countrycode><local10>
            if not phone.startswith("+") or not phone[1:].isdigit():
                raise serializers.ValidationError({"phone": _("Invalid phone format")})
            # Require at least country code + 10 digits
            if len(phone) < 12:  # e.g., +90 + 10 digits => length >= 13, allow other codes >=12
                raise serializers.ValidationError({"phone": _("Phone must include country code and 10 digits")})
        # Gender constraint
        gender = validated_data.get("gender", "").strip()
        if gender and gender not in {choice[0] for choice in User.Gender.choices}:
            raise serializers.ValidationError({"gender": _("Invalid gender")})
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(request=self.context.get("request"), email=attrs.get("email"), password=attrs.get("password"))
        if not user:
            raise serializers.ValidationError({"detail": _("Invalid credentials")})
        if not user.is_active:
            raise serializers.ValidationError({"detail": _("Inactive account")})
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value

    def validate(self, attrs):
        user: User = self.context["request"].user
        if not user.check_password(attrs["old_password"]):
            raise serializers.ValidationError({"old_password": _("Old password is incorrect")})
        return attrs


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PhoneSerializer(serializers.Serializer):
    phone = serializers.CharField()

    def validate_phone(self, value: str) -> str:
        phone = _normalize_phone(value)
        if not phone.startswith("+") or not phone[1:].isdigit():
            raise serializers.ValidationError(_("Invalid phone format"))
        if len(phone) < 12:
            raise serializers.ValidationError(_("Phone must include country code and 10 digits"))
        return phone


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value


class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = (
            "id",
            "label",
            "address_line",
            "city",
            "district",
            "latitude",
            "longitude",
            "is_default",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")


