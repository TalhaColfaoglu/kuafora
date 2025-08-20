from rest_framework import serializers
from .models import UploadedImage


class UploadedImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedImage
        fields = ("id", "image", "created_at")
        read_only_fields = ("created_at",)


