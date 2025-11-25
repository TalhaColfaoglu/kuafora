from __future__ import annotations

from rest_framework import serializers
from .models import (
    Favorite,
    
    Barbershop,
    BarbershopImage,
    Staff,
    StaffService,
    StaffServiceCategory,
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
    BreakWindow,
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
            "system_type",
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
            # Social
            "instagram", "facebook", "twitter", "whatsapp",
            "features",
        )
        read_only_fields = ("rating_avg", "total_reviews", "views_weekly", "favorites_count", "created_at", "updated_at")
        extra_kwargs = {
            # Alias kullandığımız için phone_number'ı zorunlu yapma; 'phone' ile beslenecek
            'phone_number': {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        # phone aliası ile gelen değeri yakala; en az birinin dolu olması zorunlu
        # attrs burada internal değerleri taşır; phone_number beklenir
        phone_val = attrs.get('phone_number')
        # Bazı durumlarda initial_data üzerinden okumak gerekebilir
        if (not phone_val or str(phone_val).strip() == ''):
            raw = getattr(self, 'initial_data', {}) or {}
            phone_val = raw.get('phone') or raw.get('phone_number')
        if (not phone_val or str(phone_val).strip() == ''):
            raise serializers.ValidationError({'phone': 'Bu alan zorunlu.'})
        return attrs


class StaffCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffCatalogImage
        fields = ("id", "image")


class StaffServiceCategorySerializer(serializers.ModelSerializer):
    category_id = serializers.IntegerField(source='category.id', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = StaffServiceCategory
        fields = ['id', 'category', 'category_id', 'category_name', 'is_active', 'created_at']
        read_only_fields = ['category_id', 'category_name']


class StaffServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True)
    service_id = serializers.IntegerField(source='service.id', read_only=True)
    service_category_name = serializers.CharField(source='service.category.name', read_only=True, allow_null=True)
    service_category_id = serializers.IntegerField(source='service.category.id', read_only=True, allow_null=True)
    
    class Meta:
        model = StaffService
        fields = ("id", "staff", "service", "service_id", "service_name", "service_category_id", "service_category_name", "price", "duration_minutes", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "staff", "service_id", "service_name", "service_category_id", "service_category_name", "is_active", "created_at", "updated_at")
        extra_kwargs = {
            'is_active': {'required': False, 'default': True}
        }


class StaffSerializer(serializers.ModelSerializer):
    catalog = StaffCatalogSerializer(many=True, read_only=True)
    user_full_name = serializers.SerializerMethodField()
    staff_services = serializers.SerializerMethodField()
    rating_avg = serializers.FloatField(read_only=True)
    experience_years = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = (
            "id", "barbershop", "user", "photo", "email", "certificate", "is_admin",
            "catalog", "total_reviews", "user_full_name",
            # Yeni alanlar:
            "bio", "gender_preference", "experience_years", "career_start_year", "tags",
            "rating_avg", "staff_services",
            "auto_approval", "commission_rate", "appointment_interval",
            # Social
            "instagram", "facebook", "twitter", "whatsapp",
        )
        read_only_fields = ("total_reviews", "rating_avg", "experience_years")

    def get_user_full_name(self, obj):
        u = getattr(obj, "user", None)
        if not u:
            return ""
        full = getattr(u, "full_name", None)
        if full and full != "****":
            return full
        combo = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        if combo:
            return combo
        email = getattr(u, 'email', '')
        return email
    
    def get_experience_years(self, obj):
        if obj.career_start_year:
            from datetime import datetime
            return datetime.now().year - obj.career_start_year
        return None
    
    def get_staff_services(self, obj):
        from .models import StaffService
        return StaffServiceSerializer(obj.staff_services.all(), many=True).data


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
    staff_name = serializers.SerializerMethodField()
    replies = ReviewReplySerializer(many=True, read_only=True)
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ("id", "user", "barbershop", "staff", "rating", "comment", "is_anonymous", "created_at", "updated_at", "user_display_name", "user_full_name", "barbershop_name", "staff_name", "replies", "replies_count")
        read_only_fields = ("created_at", "updated_at", "user", "barbershop", "user_display_name", "user_full_name", "barbershop_name", "staff_name", "replies", "replies_count")

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
    
    def get_staff_name(self, obj):
        if not obj.staff:
            return None
        u = getattr(obj.staff, "user", None)
        if not u:
            return None
        return getattr(u, "full_name", None) or getattr(u, "email", None)
    
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
    price_range = serializers.SerializerMethodField()
    
    class Meta:
        model = Service
        fields = ("id", "barbershop", "category", "category_name", "name", "price", "duration", "is_active", "created_at", "price_range")
        # barbershop, perform_create içinde atanıyor → inputta zorunlu olmasın
        read_only_fields = ("barbershop", "created_at", "price_range")
    
    def get_price_range(self, obj):
        from .models import StaffService
        staff_prices = StaffService.objects.filter(service=obj, is_active=True).values_list('price', flat=True)
        if not staff_prices:
            return {'min': float(obj.price), 'max': float(obj.price)}
        return {'min': float(min(staff_prices)), 'max': float(max(staff_prices))}


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
        extra_kwargs = {
            'barbershop': {'required': False},  # Set in perform_create
        }


class StaffWorkingHoursSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.user.email', read_only=True)
    
    class Meta:
        model = StaffWorkingHours
        fields = ("id", "staff", "staff_name", "day_of_week", "start_time", "end_time", "is_closed", "created_at", "updated_at")


class BreakWindowSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.user.full_name", read_only=True)
    barbershop_name = serializers.CharField(source="barbershop.name", read_only=True)

    class Meta:
        model = BreakWindow
        fields = (
            "id",
            "scope",
            "barbershop",
            "barbershop_name",
            "staff",
            "staff_name",
            "date",
            "start_time",
            "end_time",
            "label",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_by", "created_at", "updated_at")

    def validate(self, attrs):
        from datetime import datetime as _dt
        from rest_framework import serializers as drf_serializers
        request = self.context.get("request")
        user = getattr(request, "user", None)

        scope = attrs.get("scope") or getattr(self.instance, "scope", None)
        staff = attrs.get("staff") or getattr(self.instance, "staff", None)
        barbershop = (
            attrs.get("barbershop")
            or getattr(self.instance, "barbershop", None)
            or getattr(staff, "barbershop", None)
        )
        if not barbershop:
            raise drf_serializers.ValidationError({"barbershop": "Dükkan zorunlu"})

        if scope == BreakWindow.Scope.STAFF and not staff:
            raise drf_serializers.ValidationError({"staff": "Personel molası için staff zorunlu"})
        if scope == BreakWindow.Scope.SHOP and staff:
            raise drf_serializers.ValidationError({"staff": "Dükkan molasında staff seçilemez"})
        if staff and staff.barbershop_id != barbershop.id:
            raise drf_serializers.ValidationError({"staff": "Personel bu dükkanda değil"})

        date_val = attrs.get("date") or getattr(self.instance, "date", None)
        start_time = attrs.get("start_time") or getattr(self.instance, "start_time", None)
        end_time = attrs.get("end_time") or getattr(self.instance, "end_time", None)
        if not date_val or not start_time or not end_time:
            raise drf_serializers.ValidationError("Tarih ve saat aralığı zorunlu")
        if start_time >= end_time:
            raise drf_serializers.ValidationError({"start_time": "Başlangıç bitişten küçük olmalı"})

        from app.barbers.services.breaks import (
            get_shop_hours,
            get_effective_staff_window,
        )

        if scope == BreakWindow.Scope.SHOP:
            shop_hours = get_shop_hours(barbershop, date_val)
            if not shop_hours or shop_hours.is_closed:
                raise drf_serializers.ValidationError({"date": "Bu gün dükkan kapalı"})
            open_time = shop_hours.start_time
            close_time = shop_hours.end_time
        else:
            staff_window = get_effective_staff_window(staff, date_val)
            open_time, close_time = staff_window[0], staff_window[1]
            if not open_time or not close_time:
                raise drf_serializers.ValidationError({"date": "Personel bu gün çalışmıyor"})

        if open_time and start_time < open_time:
            raise drf_serializers.ValidationError({"start_time": "Mola başlangıcı çalışma saatinden önce"})
        if close_time and end_time > close_time:
            raise drf_serializers.ValidationError({"end_time": "Mola bitişi çalışma saatinden sonra"})

        qs = BreakWindow.objects.filter(barbershop=barbershop, scope=scope, date=date_val)
        if staff:
            qs = qs.filter(staff=staff)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.filter(start_time__lt=end_time, end_time__gt=start_time).exists():
            raise drf_serializers.ValidationError({"date": "Bu saat aralığında mola zaten var"})

        attrs["barbershop"] = barbershop
        if user and user.is_authenticated:
            attrs["created_by"] = user
        return attrs


# --- Holidays & Special Days ---
from .models import OfficialHoliday, ShopHolidayOverride, DailyOverride


class OfficialHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficialHoliday
        fields = ("id", "date", "name", "type", "country_code", "year")


class ShopHolidayOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopHolidayOverride
        fields = (
            "id",
            "barbershop",
            "date",
            "status",
            "open_time",
            "close_time",
            "title",
            "note",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("barbershop", "created_by", "created_at", "updated_at")


class DailyOverrideSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.email', read_only=True)

    class Meta:
        model = DailyOverride
        fields = (
            "id",
            "barbershop",
            "date",
            "status",
            "note",
            "expires_at",
            "created_by",
            "created_by_name",
            "created_at",
        )
        read_only_fields = ("created_by", "created_by_name", "created_at")

class OverrideSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.email', read_only=True)
    staff_name = serializers.CharField(source='staff.user.email', read_only=True)
    
    class Meta:
        model = Override
        fields = (
            "id", "barbershop", "staff", "staff_name", "override_type", "override_scope",
            "start_date", "end_date", "start_time", "end_time", "is_recurring", "recurring_rule",
            "reason", "is_active", "created_by", "created_by_name", "created_at", "updated_at"
        )
        read_only_fields = ("barbershop", "created_at", "updated_at", "created_by")


class SpecialMessageSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.email', read_only=True)
    target_staff_names = serializers.SerializerMethodField()
    view_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SpecialMessage
        fields = (
            "id", "barbershop", "source", "display_type", "target_type", "title", "content",
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
            'display_type': {'required': False},
            'barbershop': {'required': False},
            'target_staff': {'required': False},
        }
    
    def get_target_staff_names(self, obj):
        return [staff.user.email for staff in obj.target_staff.all()]
    
    def get_view_count(self, obj):
        # DB tablo eksikliği veya yoğunluk için herhangi bir sorgu yapma; sabit 0 dön
        return 0

    def create(self, validated_data):
        from django.utils import timezone
        from datetime import timedelta
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        # Varsayılanlar
        validated_data['source'] = validated_data.get('source') or 'manual'
        validated_data['display_type'] = validated_data.get('display_type') or 'banner'
        validated_data['target_type'] = validated_data.get('target_type') or 'all_shop'
        validated_data['start_datetime'] = validated_data.get('start_datetime') or timezone.now()
        validated_data['end_datetime'] = validated_data.get('end_datetime') or (timezone.now() + timedelta(days=365))
        validated_data['is_active'] = validated_data.get('is_active', True)

        # Barbershop otomatik belirle
        if not validated_data.get('barbershop') and user and user.is_authenticated:
            from .models import Staff
            admin_staff = Staff.objects.filter(user=user, is_admin=True).first()
            if admin_staff:
                validated_data['barbershop'] = admin_staff.barbershop

        # created_by otomatik
        if user and user.is_authenticated:
            validated_data['created_by'] = user

        return super().create(validated_data)


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

