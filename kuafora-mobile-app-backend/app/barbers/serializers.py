from __future__ import annotations

from rest_framework import serializers
from .models import (
    Favorite,
    
    Barbershop,
    BarbershopImage,
    Staff,
    StaffCatalogImage,
    WorkSchedule,
    Review,
    Service,
    LastViewed,
)


class BarbershopImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BarbershopImage
        fields = ("id", "image")


class BarbershopSerializer(serializers.ModelSerializer):
    images = BarbershopImageSerializer(many=True, read_only=True)

    class Meta:
        model = Barbershop
        fields = (
            "id",
            "name",
            "gender",
            "address",
            "city",
            "district",
            "phone_number",
            "main_image",
            "images",
            "is_verified",
            "description",
            "created_at",
            "updated_at",
            "rating_avg",
            "total_reviews",
            "star_1_count","star_2_count","star_3_count","star_4_count","star_5_count",
            "views_weekly",
            "favorites_count",
        )
        read_only_fields = ("rating_avg", "total_reviews", "views_weekly", "favorites_count", "created_at", "updated_at")


class StaffCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffCatalogImage
        fields = ("id", "image")


class StaffSerializer(serializers.ModelSerializer):
    catalog = StaffCatalogSerializer(many=True, read_only=True)

    class Meta:
        model = Staff
        fields = ("id", "barbershop", "user", "photo", "email", "certificate", "is_admin", "catalog", "total_reviews")
        read_only_fields = ("total_reviews",)


class WorkScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkSchedule
        fields = ("id", "staff", "day_of_week", "start_time", "end_time", "break_time")


class ReviewSerializer(serializers.ModelSerializer):
    user_display_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ("id", "user", "barbershop", "rating", "comment", "is_anonymous", "created_at", "updated_at", "user_display_name")
        read_only_fields = ("created_at", "updated_at", "user", "barbershop", "user_display_name")

    def get_user_display_name(self, obj):
        if obj.is_anonymous:
            return "****"
        u = getattr(obj, "user", None)
        if not u:
            return "****"
        name = getattr(u, "full_name", None) or getattr(u, "first_name", None) or getattr(u, "email", None) or "Kullanıcı"
        return name


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ("id", "barbershop", "category", "name", "price", "duration", "is_active")


class LastViewedSerializer(serializers.ModelSerializer):
    class Meta:
        model = LastViewed
        fields = ("id", "user", "barbershop", "viewed_at")
        read_only_fields = ("viewed_at",)


class InviteStaffSerializer(serializers.Serializer):
    email = serializers.EmailField()
    is_admin = serializers.BooleanField(default=False)


class StaffHoursSerializer(serializers.Serializer):
    day_of_week = serializers.ChoiceField(choices=WorkSchedule.Weekday.choices)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    break_time = serializers.IntegerField(required=False, default=0)



# Test serializer removed


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ("id", "barbershop", "created_at")


class BarbershopWithFavoriteSerializer(serializers.ModelSerializer):
    is_favorited = serializers.SerializerMethodField()
    
    class Meta:
        model = Barbershop
        fields = ("id", "name", "address", "is_favorited", "favorites_count")
    
    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from .models import Favorite
            return Favorite.objects.filter(user=request.user, barbershop=obj).exists()
        return False


class BarbershopDetailSerializer(BarbershopSerializer):
    is_favorited = serializers.SerializerMethodField()

    class Meta(BarbershopSerializer.Meta):
        fields = BarbershopSerializer.Meta.fields + ("is_favorited",)

    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from .models import Favorite
            return Favorite.objects.filter(user=request.user, barbershop=obj).exists()
        return False

