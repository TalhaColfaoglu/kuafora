from rest_framework import serializers
from .models import Campaign, CampaignType, SystemType, DiscountType

class CampaignSerializer(serializers.ModelSerializer):
    discount_value = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False)

    class Meta:
        model = Campaign
        fields = (
            "id", "barbershop", "name", "description", "type",
            "start_date", "end_date", "is_active", "system_type",
            "discount_type", "discount_value", "rules",
            "created_at", "updated_at"
        )
        read_only_fields = ("barbershop", "created_at", "updated_at")

class CampaignCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = (
            "name", "description", "type",
            "start_date", "end_date", "is_active", "system_type",
            "discount_type", "discount_value", "rules"
        )

    def validate(self, attrs):
        # Basic validation for rules based on type
        c_type = attrs.get("type")
        rules = attrs.get("rules", {})
        
        if c_type == CampaignType.TIME_BASED:
            if "days" not in rules and "start_time" not in rules:
                raise serializers.ValidationError("Zaman bazlı kampanyalar için gün/saat kuralları gereklidir.")
        elif c_type == CampaignType.BUNDLE:
            if "service_ids" not in rules or not isinstance(rules["service_ids"], list) or len(rules["service_ids"]) < 2:
                raise serializers.ValidationError("Paket kampanyası için en az 2 hizmet seçilmelidir.")
        
        return attrs

