from __future__ import annotations

from django.contrib.auth import authenticate, password_validation
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "image",
            "full_name",
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


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("full_name", "email", "password", "gender", "phone")

    def validate_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
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


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value


