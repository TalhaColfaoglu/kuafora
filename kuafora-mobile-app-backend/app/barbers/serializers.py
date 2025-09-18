from __future__ import annotations

from rest_framework import serializers
from .models import (
    Favorite,
    
    Barbershop,
    BarbershopImage,
    Staff,
    StaffCatalogImage,
    WorkSchedule,
    ShopWorkingHours,
    StaffWorkingHours,
    Override,
    SpecialMessage,
    MessageViewLog,
    CalendarAuditLog,
    Review,
    ReviewReply,
    Service,
    ServiceCategory,
    LastViewed,
)


class BarbershopImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BarbershopImage
        fields = ("id", "image")


class BarbershopSerializer(serializers.ModelSerializer):
    images = BarbershopImageSerializer(many=True, read_only=True)
    phone = serializers.CharField(source='phone_number', required=False)  # Frontend'den gelen 'phone' field'ını 'phone_number' olarak map et

    class Meta:
        model = Barbershop
        fields = (
            "id",
            "name",
            "gender",
            "address",
            "latitude","longitude",
            "city",
            "district",
            "phone_number",
            "phone",  # Frontend uyumluluğu için
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
    user_full_name = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = ("id", "barbershop", "user", "photo", "email", "certificate", "is_admin", "catalog", "total_reviews", "user_full_name")
        read_only_fields = ("total_reviews",)

    def get_user_full_name(self, obj):
        u = getattr(obj, "user", None)
        if not u:
            return ""
        return getattr(u, "full_name", None) or f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip() or getattr(u, 'email', '')


class WorkScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkSchedule
        fields = ("id", "staff", "day_of_week", "start_time", "end_time", "break_time")


class ReviewReplySerializer(serializers.ModelSerializer):
    user_display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ReviewReply
        fields = ("id", "review", "user", "reply", "created_at", "user_display_name")
        read_only_fields = ("created_at", "user")
    
    def get_user_display_name(self, obj):
        u = getattr(obj, "user", None)
        if not u:
            return "****"
        name = getattr(u, "full_name", None) or getattr(u, "first_name", None) or getattr(u, "email", None) or "Kullanıcı"
        return name


class ReviewSerializer(serializers.ModelSerializer):
    user_display_name = serializers.SerializerMethodField()
    user_full_name = serializers.SerializerMethodField()
    barbershop_name = serializers.SerializerMethodField()
    replies = ReviewReplySerializer(many=True, read_only=True)
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ("id", "user", "barbershop", "rating", "comment", "is_anonymous", "created_at", "updated_at", "user_display_name", "user_full_name", "barbershop_name", "replies", "replies_count")
        read_only_fields = ("created_at", "updated_at", "user", "barbershop", "user_display_name", "user_full_name", "barbershop_name", "replies", "replies_count")

    def get_user_display_name(self, obj):
        if obj.is_anonymous:
            return "****"
        u = getattr(obj, "user", None)
        if not u:
            return "****"
        name = getattr(u, "full_name", None) or getattr(u, "first_name", None) or getattr(u, "email", None) or "Kullanıcı"
        return name

    def get_user_full_name(self, obj):
        # Asla anonimleştirme uygulama; gerçek görünür ad (UI karar verir)
        u = getattr(obj, "user", None)
        if not u:
            return "Kullanıcı"
        name = getattr(u, "full_name", None) or f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        if not name:
            name = getattr(u, "email", None) or "Kullanıcı"
        return name

    def get_barbershop_name(self, obj):
        bs = getattr(obj, "barbershop", None)
        return getattr(bs, "name", None)
    
    def get_replies_count(self, obj):
        return obj.replies.count()


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ("id", "barbershop", "name", "created_at")
        # barbershop, perform_create içinde atanıyor → inputta zorunlu olmasın
        read_only_fields = ("barbershop", "created_at")


class ServiceSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Service
        fields = ("id", "barbershop", "category", "category_name", "name", "price", "duration", "is_active", "created_at")
        # barbershop, perform_create içinde atanıyor → inputta zorunlu olmasın
        read_only_fields = ("barbershop", "created_at")


class ReviewReplySerializer(serializers.ModelSerializer):
    user_full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ReviewReply
        fields = ("id", "review", "user", "text", "created_at", "user_full_name")
        read_only_fields = ("created_at", "user", "user_full_name")
    
    def get_user_full_name(self, obj):
        u = getattr(obj, "user", None)
        if not u:
            return "Kullanıcı"
        name = getattr(u, "full_name", None) or f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        if not name:
            name = getattr(u, "email", None) or "Kullanıcı"
        return name


class LastViewedSerializer(serializers.ModelSerializer):
    barbershop = BarbershopSerializer(read_only=True)
    class Meta:
        model = LastViewed
        fields = ("id", "user", "barbershop", "viewed_at")
        read_only_fields = ("user", "viewed_at")


class InviteStaffSerializer(serializers.Serializer):
    email = serializers.EmailField()
    is_admin = serializers.BooleanField(default=False)
    barbershop = serializers.IntegerField(required=False)


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


class ShopWorkingHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopWorkingHours
        fields = ("id", "barbershop", "day_of_week", "start_time", "end_time", "is_closed", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")


class StaffWorkingHoursSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.user.email', read_only=True)
    
    class Meta:
        model = StaffWorkingHours
        fields = ("id", "staff", "staff_name", "day_of_week", "start_time", "end_time", "is_closed", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")


class OverrideSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.email', read_only=True)
    staff_name = serializers.CharField(source='staff.user.email', read_only=True)
    
    class Meta:
        model = Override
        fields = (
            "id", "barbershop", "staff", "staff_name", "override_type", "override_scope",
            "start_date", "end_date", "start_time", "end_time", "is_recurring", "recurring_rule",
            "reason", "created_by", "created_by_name", "created_at", "updated_at"
        )
        read_only_fields = ("created_at", "updated_at", "created_by")


class SpecialMessageSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.email', read_only=True)
    target_staff_names = serializers.SerializerMethodField()
    view_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SpecialMessage
        fields = (
            "id", "barbershop", "source", "target_type", "title", "content",
            "target_staff", "target_staff_names", "start_datetime", "end_datetime",
            "created_by", "created_by_name", "created_at", "updated_at", "is_active", "view_count"
        )
        read_only_fields = ("created_at", "updated_at", "created_by", "view_count")
        extra_kwargs = {
            'start_datetime': {'required': False},
            'end_datetime': {'required': False},
            'target_type': {'required': False},
            'is_active': {'required': False},
            'source': {'required': False},
        }
    
    def get_target_staff_names(self, obj):
        return [staff.user.email for staff in obj.target_staff.all()]
    
    def get_view_count(self, obj):
        return obj.view_logs.count()


class MessageViewLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = MessageViewLog
        fields = ("id", "message", "user", "user_name", "device_id", "viewed_at", "dismissed")
        read_only_fields = ("viewed_at",)


class CalendarAuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = CalendarAuditLog
        fields = ("id", "barbershop", "user", "user_name", "action_type", "target_model", "target_id", "changes", "timestamp")
        read_only_fields = ("timestamp",)


# Takvim hesaplama için özel serializer'lar
class CalendarStatusSerializer(serializers.Serializer):
    """Dükkanın günlük durumunu hesaplayan serializer"""
    date = serializers.DateField()
    is_open = serializers.BooleanField()
    opening_time = serializers.TimeField(allow_null=True)
    closing_time = serializers.TimeField(allow_null=True)
    status_message = serializers.CharField(allow_null=True)
    active_overrides = OverrideSerializer(many=True, read_only=True)
    active_messages = SpecialMessageSerializer(many=True, read_only=True)


class StaffCalendarStatusSerializer(serializers.Serializer):
    """Personelin günlük durumunu hesaplayan serializer"""
    staff_id = serializers.IntegerField()
    staff_name = serializers.CharField()
    date = serializers.DateField()
    is_working = serializers.BooleanField()
    start_time = serializers.TimeField(allow_null=True)
    end_time = serializers.TimeField(allow_null=True)
    status_message = serializers.CharField(allow_null=True)
    active_overrides = OverrideSerializer(many=True, read_only=True)


class WeeklyCalendarSerializer(serializers.Serializer):
    """Haftalık takvim görünümü için serializer"""
    barbershop_id = serializers.IntegerField()
    week_start = serializers.DateField()
    week_end = serializers.DateField()
    shop_hours = ShopWorkingHoursSerializer(many=True, read_only=True)
    staff_hours = StaffWorkingHoursSerializer(many=True, read_only=True)
    overrides = OverrideSerializer(many=True, read_only=True)
    messages = SpecialMessageSerializer(many=True, read_only=True)

