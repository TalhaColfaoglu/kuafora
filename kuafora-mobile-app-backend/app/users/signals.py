from django.db.models.signals import post_migrate
from django.dispatch import receiver
import os
from django.conf import settings


@receiver(post_migrate)
def create_media_directories(sender, **kwargs):
    """Create media directories after migration"""
    if sender.name == 'app.users':
        media_dirs = [
            os.path.join(settings.MEDIA_ROOT, 'users', 'images'),
            os.path.join(settings.MEDIA_ROOT, 'barbershops', 'images'),
        ]
        
        for media_dir in media_dirs:
            os.makedirs(media_dir, exist_ok=True)
