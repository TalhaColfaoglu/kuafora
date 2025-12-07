from django.core.management.base import BaseCommand
from app.subscriptions.models import SubscriptionPlan

class Command(BaseCommand):
    help = 'Seeds initial Subscription Plans'

    def handle(self, *args, **kwargs):
        plans = [
            {
                "name": "Kuafora Partner",
                "price_monthly": 190.00,
                "features": {
                    "description": "Bilgi sistemi ve harici randevu kullanan salonlar için",
                    "booking_system": False,
                    "vitrin_listing": True
                }
            },
            {
                "name": "Kuafora Randevu Partneri",
                "price_monthly": 890.00,
                "features": {
                    "description": "Kuafora randevu sistemini kullananlar için",
                    "booking_system": True,
                    "vitrin_listing": True
                }
            }
        ]

        self.stdout.write("Seeding subscription plans...")

        for p in plans:
            obj, created = SubscriptionPlan.objects.get_or_create(
                name=p["name"],
                defaults={
                    "price_monthly": p["price_monthly"],
                    "features": p["features"],
                    "is_active": True
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created plan: {p['name']} - {p['price_monthly']}TL"))
            else:
                # Update price if changed
                if float(obj.price_monthly) != p["price_monthly"]:
                    obj.price_monthly = p["price_monthly"]
                    obj.features = p["features"]
                    obj.save()
                    self.stdout.write(self.style.WARNING(f"Updated plan: {p['name']}"))
                else:
                    self.stdout.write(f"Exists plan: {p['name']}")

        self.stdout.write(self.style.SUCCESS("Plan seeding completed."))

