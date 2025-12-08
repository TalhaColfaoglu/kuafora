import os
import django
import sys

# Setup Django environment
sys.path.append('/app')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from app.barbers.models import ShopCategory

def create_initial_categories():
    categories = [
        {"name": "Saç Hizmetleri", "icon": "https://d1uiu5mb5i1uph.cloudfront.net/static/categories/hair.png"},
        {"name": "Sakal & Bıyık", "icon": "https://d1uiu5mb5i1uph.cloudfront.net/static/categories/beard.png"},
        {"name": "Cilt Bakımı", "icon": "https://d1uiu5mb5i1uph.cloudfront.net/static/categories/skincare.png"},
        {"name": "Masaj & SPA", "icon": "https://d1uiu5mb5i1uph.cloudfront.net/static/categories/massage.png"},
        {"name": "Çocuk Tıraşı", "icon": "https://d1uiu5mb5i1uph.cloudfront.net/static/categories/kids.png"},
        {"name": "Damat Tıraşı", "icon": "https://d1uiu5mb5i1uph.cloudfront.net/static/categories/groom.png"},
        {"name": "Saç Boyama", "icon": "https://d1uiu5mb5i1uph.cloudfront.net/static/categories/dye.png"},
        {"name": "Epilasyon", "icon": "https://d1uiu5mb5i1uph.cloudfront.net/static/categories/wax.png"},
    ]

    print("Checking categories...")
    for cat_data in categories:
        cat, created = ShopCategory.objects.get_or_create(
            name=cat_data["name"],
            defaults={"icon": cat_data["icon"]}
        )
        if created:
            print(f"Created category: {cat.name}")
        else:
            print(f"Category already exists: {cat.name}")

if __name__ == "__main__":
    create_initial_categories()
