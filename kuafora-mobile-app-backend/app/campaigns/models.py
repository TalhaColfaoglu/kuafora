from django.db import models
from django.conf import settings
from app.barbers.models import Barbershop

class CampaignType(models.TextChoices):
    TIME_BASED = "time_based", "Time Based"
    BUNDLE = "bundle", "Bundle"
    SPECIAL = "special", "Special/Condition"

class SystemType(models.TextChoices):
    BOOKING = "booking", "Booking System"
    INFO = "info", "Info System"
    BOTH = "both", "Both"

class DiscountType(models.TextChoices):
    PERCENT = "percent", "Percentage"
    FIXED_AMOUNT = "fixed_amount", "Fixed Amount"
    FIXED_PRICE = "fixed_price", "Fixed Price"

class Campaign(models.Model):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="campaigns")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=CampaignType.choices)
    
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    
    system_type = models.CharField(
        max_length=10, 
        choices=SystemType.choices, 
        default=SystemType.BOTH,
        help_text="Hangi sistemlerde geçerli olduğu"
    )
    
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Rules Storage
    # For Time Based: { "days": [1,2], "start_time": "10:00", "end_time": "14:00", "services": [1, 2] }
    # For Bundle: { "service_ids": [1, 2, 3] }
    # For Special: { "label": "Student", "condition_text": "Show ID" }
    rules = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.barbershop.name} - {self.name}"
