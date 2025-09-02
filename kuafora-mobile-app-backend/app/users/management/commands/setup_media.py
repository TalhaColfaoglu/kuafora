from django.core.management.base import BaseCommand
import os
from django.conf import settings


class Command(BaseCommand):
    help = 'Setup media directories for the application'

    def handle(self, *args, **options):
        # Create media directories
        media_dirs = [
            os.path.join(settings.MEDIA_ROOT, 'users', 'images'),
            os.path.join(settings.MEDIA_ROOT, 'barbershops', 'images'),
        ]
        
        for media_dir in media_dirs:
            os.makedirs(media_dir, exist_ok=True)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created directory: {media_dir}')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Media directories setup completed successfully!')
        )
