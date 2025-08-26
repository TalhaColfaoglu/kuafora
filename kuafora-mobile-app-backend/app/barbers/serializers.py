from __future__ import annotations

from rest_framework import serializers
from .models import (
    Barbershop,
    BarbershopImage,
    Staff,
    StaffCatalogImage,
    WorkSchedule,
    Review,
    Service,
    Favorite,
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
            "latitude",
            "longitude",
            "created_at",
            "updated_at",
            "rating_avg",
            "total_reviews",
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
    class Meta:
        model = Review
        fields = ("id", "user", "barbershop", "rating", "comment", "created_at")
        read_only_fields = ("created_at",)


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ("id", "barbershop", "category", "name", "price", "duration", "is_active")


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ("id", "user", "barbershop", "created_at")
        read_only_fields = ("created_at",)


class LastViewedSerializer(serializers.ModelSerializer):
    class Meta:
        model = LastViewed
        fields = ("id", "user", "barbershop", "created_at")
        read_only_fields = ("created_at",)


class InviteStaffSerializer(serializers.Serializer):
    email = serializers.EmailField()
    is_admin = serializers.BooleanField(default=False)


class StaffHoursSerializer(serializers.Serializer):
    day_of_week = serializers.ChoiceField(choices=WorkSchedule.Weekday.choices)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    break_time = serializers.IntegerField(required=False, default=0)



# Test serializer removed

