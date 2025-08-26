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


