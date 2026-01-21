from rest_framework import serializers
from .models import UploadedImage
from app.core.validators import validate_file_extension, validate_file_size, sanitize_filename


class UploadedImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedImage
        fields = ("id", "image", "created_at")
        read_only_fields = ("created_at",)
    
    def validate_image(self, value):
        """Validate uploaded image file."""
        if value:
            # Validate file extension
            validate_file_extension(value.name, allowed_extensions={'.jpg', '.jpeg', '.png', '.gif', '.webp'})
            
            # Validate file size (max 10MB)
            validate_file_size(value, max_size_mb=10)
            
            # Sanitize filename
            if hasattr(value, 'name'):
                value.name = sanitize_filename(value.name)
        
        return value


