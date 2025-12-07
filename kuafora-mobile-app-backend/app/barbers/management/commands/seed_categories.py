from django.core.management.base import BaseCommand
from app.barbers.models import ShopCategory
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Seeds initial Shop Categories'

    def handle(self, *args, **kwargs):
        categories = [
            "Berber",
            "Kuaför",
            "Güzellik Merkezi",
            "Tırnak Stüdyosu",
            "Masaj & Spa",
            "Epilasyon & Ağda",
            "Makyaj Stüdyosu",
            "Pet Kuaför",
            "Dövme & Piercing",
            "Diyetisyen"
        ]

        self.stdout.write("Seeding categories...")

        for cat_name in categories:
            # Custom slugify for Turkish characters
            slug = slugify(cat_name.replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c').replace('&', 've'))
            
            obj, created = ShopCategory.objects.get_or_create(
                name=cat_name,
                defaults={'slug': slug, 'is_active': True}
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created: {cat_name}"))
            else:
                self.stdout.write(f"Exists: {cat_name}")

        self.stdout.write(self.style.SUCCESS("Category seeding completed."))

