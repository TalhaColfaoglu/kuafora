from __future__ import annotations

from rest_framework import serializers

from .models import Appointment, Hold


class AvailabilityQuerySerializer(serializers.Serializer):
    shop_id = serializers.IntegerField()
    staff_id = serializers.IntegerField(required=False)
    date = serializers.DateField()
    duration = serializers.IntegerField(min_value=1)
    grid = serializers.IntegerField(required=False)


class AvailabilityResponseSerializer(serializers.Serializer):
    slots = serializers.ListField(child=serializers.CharField())


class HoldCreateSerializer(serializers.Serializer):
    shop_id = serializers.IntegerField()
    staff_id = serializers.IntegerField()
    date = serializers.DateField()
    start_time = serializers.TimeField()
    service_items = serializers.ListField(child=serializers.DictField(), allow_empty=False)


class HoldResponseSerializer(serializers.Serializer):
    hold_id = serializers.UUIDField()
    expires_in = serializers.IntegerField()


class AppointmentCreateSerializer(serializers.Serializer):
    hold_id = serializers.UUIDField()
    note = serializers.CharField(required=False, allow_blank=True)
    source = serializers.ChoiceField(choices=[("partner", "partner"), ("mobile_customer", "mobile_customer")], required=False)


class AppointmentSerializer(serializers.ModelSerializer):
    staff_grid = serializers.IntegerField(source="staff.appointment_interval", read_only=True)
    staff_name = serializers.SerializerMethodField()
    shop_name = serializers.SerializerMethodField()
    class Meta:
        model = Appointment
        fields = (
            "id",
            "shop",
            "staff",
            "customer",
            "status",
            "start_datetime",
            "end_datetime",
            "duration_minutes",
            "service_items",
            "price_total",
            "note",
            "source",
            "staff_grid",
            "staff_name",
            "shop_name",
        )

    def get_staff_name(self, obj):
        u = getattr(obj.staff, "user", None)
        return getattr(u, "full_name", None) or getattr(u, "email", "")

    def get_shop_name(self, obj):
        return getattr(obj.shop, "name", "")


class ShiftSerializer(serializers.Serializer):
    shift_minutes = serializers.IntegerField()


class RescheduleSerializer(serializers.Serializer):
    new_start_dt = serializers.DateTimeField()


class AppointmentListQuerySerializer(serializers.Serializer):
    staff_id = serializers.IntegerField(required=False)
    shop_id = serializers.IntegerField(required=False)
    status = serializers.CharField(required=False)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)


