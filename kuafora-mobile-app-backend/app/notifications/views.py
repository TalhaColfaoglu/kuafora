from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import ProgrammingError
from .models import Notification
from .serializers import NotificationSerializer

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or self.request.user.is_anonymous:
            return Notification.objects.none()
        try:
        return Notification.objects.filter(user=self.request.user)
        except ProgrammingError:
            # Tablo yoksa (migration uygulanmadıysa) boş dönerek 500'ü engelle
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

