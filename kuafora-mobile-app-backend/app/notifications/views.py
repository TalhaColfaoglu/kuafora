from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import DatabaseError, OperationalError, ProgrammingError
from .models import Notification, DevicePushToken
from .serializers import NotificationSerializer, DevicePushTokenUpsertSerializer

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or self.request.user.is_anonymous:
            return Notification.objects.none()
        try:
            return Notification.objects.filter(user=self.request.user)
        except (ProgrammingError, OperationalError, DatabaseError):
            # DB hazır değil / tablo yok / migrate uygulanmadıysa boş dönerek 500'ü engelle
            return Notification.objects.none()

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({"detail": "Marked as read"})

    @action(detail=False, methods=["post"])
    def read_all(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"detail": "All marked as read"})

    @action(detail=False, methods=["post"], url_path="push-tokens")
    def upsert_push_token(self, request):
        """
        Register (or refresh) the device push token for the authenticated user.
        Mobile apps should call this:
        - after login
        - on token refresh
        - occasionally (app start) to update last_seen_at
        """
        ser = DevicePushTokenUpsertSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        token = data["token"].strip()
        platform = data["platform"]
        device_id = (data.get("device_id") or "").strip()
        app_version = (data.get("app_version") or "").strip()

        try:
            obj, _created = DevicePushToken.objects.update_or_create(
                user=request.user,
                token=token,
                defaults={
                    "platform": platform,
                    "device_id": device_id,
                    "app_version": app_version,
                    "is_active": True,
                },
            )
        except (ProgrammingError, OperationalError, DatabaseError):
            # DB not ready; don't break app login flow.
            return Response({"detail": "push token not saved"}, status=status.HTTP_202_ACCEPTED)

        return Response(
            {
                "id": obj.id,
                "platform": obj.platform,
                "device_id": obj.device_id,
                "is_active": obj.is_active,
            }
        )

    @action(detail=False, methods=["post"], url_path="push-tokens/disable")
    def disable_push_token(self, request):
        """
        Disable a push token (e.g. on logout).
        """
        token = (request.data.get("token") or "").strip()
        if not token:
            return Response({"detail": "token required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            DevicePushToken.objects.filter(user=request.user, token=token).update(is_active=False)
        except (ProgrammingError, OperationalError, DatabaseError):
            return Response({"detail": "ok"}, status=status.HTTP_202_ACCEPTED)
        return Response({"detail": "ok"})

