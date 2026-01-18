from __future__ import annotations

from rest_framework import generics, permissions

from .models import SupportRequest
from .serializers import SupportRequestCreateSerializer


def _get_client_ip(request) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # May contain "client, proxy1, proxy2"
        return xff.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR")


class SupportRequestCreateApi(generics.CreateAPIView):
    serializer_class = SupportRequestCreateSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "support_create"

    def perform_create(self, serializer):
        req = self.request
        user = req.user if req.user.is_authenticated else None

        ua = (req.META.get("HTTP_USER_AGENT") or "").strip()
        ip = _get_client_ip(req)

        # If authenticated, fill missing contact email from user.
        email = (serializer.validated_data.get("email") or "").strip()
        if user and not email:
            email = getattr(user, "email", "") or ""

        serializer.save(
            user=user,
            email=email,
            user_agent=ua,
            ip_address=ip,
        )


