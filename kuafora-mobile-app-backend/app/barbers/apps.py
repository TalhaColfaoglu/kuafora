from django.apps import AppConfig
import os


class BarbersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.barbers"

    def ready(self):
        from . import signals  # noqa: F401
        
        # Create media directories for local storage if needed
        from django.conf import settings
        if settings.DEFAULT_FILE_STORAGE == "django.core.files.storage.FileSystemStorage":
            media_dirs = [
                os.path.join(settings.MEDIA_ROOT, 'barbershops', 'main'),
                os.path.join(settings.MEDIA_ROOT, 'barbershops', 'main', 'thumbs'),
                os.path.join(settings.MEDIA_ROOT, 'barbershops', 'extra'),
                os.path.join(settings.MEDIA_ROOT, 'barbershops', 'extra', 'thumbs'),
                os.path.join(settings.MEDIA_ROOT, 'staff', 'photos'),
                os.path.join(settings.MEDIA_ROOT, 'staff', 'photos', 'thumbs'),
                os.path.join(settings.MEDIA_ROOT, 'staff', 'catalog'),
            ]
            for d in media_dirs:
                try:
                    os.makedirs(d, exist_ok=True)
                except Exception:
                    pass

