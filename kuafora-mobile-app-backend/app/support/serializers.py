from __future__ import annotations

from rest_framework import serializers

from .models import SupportRequest


class SupportRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportRequest
        fields = ("type", "message", "email", "phone", "app_version", "platform", "device_info")

    def validate_message(self, value: str) -> str:
        v = (value or "").strip()
        if len(v) < 10:
            raise serializers.ValidationError("Mesaj en az 10 karakter olmalı.")
        if len(v) > 5000:
            raise serializers.ValidationError("Mesaj çok uzun.")
        return v

    def validate(self, attrs):
        req = self.context.get("request")
        is_auth = bool(req and getattr(req, "user", None) and req.user.is_authenticated)

        email = (attrs.get("email") or "").strip()
        phone = (attrs.get("phone") or "").strip()

        # If guest, require at least one contact channel
        if not is_auth and not email and not phone:
            raise serializers.ValidationError({"detail": "Lütfen e-posta veya telefon girin."})

        attrs["email"] = email
        attrs["phone"] = phone
        return attrs


