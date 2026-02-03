from rest_framework import serializers
from app.barbers.models import Barbershop, ShopCategory
from app.barbers.serializers import _ensure_cloudfront_barbershop_images
from app.campaigns.models import Campaign

class ShopCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopCategory
        fields = ("id", "name", "slug", "icon")

class BarbershopHomeSerializer(serializers.ModelSerializer):
    distance = serializers.FloatField(read_only=True)

    class Meta:
        model = Barbershop
        fields = ("id", "name", "city", "district", "main_image", "rating_avg", "total_reviews", "distance", "latitude", "longitude")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        _ensure_cloudfront_barbershop_images(data, instance, keys=("main_image",))
        return data

class CampaignHomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = ("id", "name", "type", "discount_value", "start_date", "end_date")

