from rest_framework import mixins, viewsets, permissions
from .models import UploadedImage
from .serializers import UploadedImageSerializer


class UploadedImageViewSet(mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = UploadedImage.objects.all()
    serializer_class = UploadedImageSerializer
    permission_classes = [permissions.IsAuthenticated]


