from __future__ import annotations

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import (
    Favorite,
    Barbershop,
    BarbershopImage,
    BarbershopCatalog,
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
    ShopCategory,
    OfficialHoliday,
    ShopHolidayOverride,
    DailyOverride,
)

logger = logging.getLogger(__name__)


# Staff/user avatars are shown in both public (main app) and authenticated (partner) clients.
# When user photos are stored in private S3/CloudFront, direct `.url` may return 403.
# For staff listings we return a short-lived S3 presigned URL when AWS is configured.
_USER_PHOTO_SIGNED_URL_EXPIRES = 300  # 5 minutes
_S3_CLIENT = None


def _get_s3_client():
    global _S3_CLIENT
    if _S3_CLIENT is not None:
        return _S3_CLIENT
    try:
        import boto3

        _S3_CLIENT = boto3.client(
            "s3",
            region_name=getattr(settings, "AWS_S3_REGION_NAME", "eu-central-1"),
            aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
            aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
        )
        return _S3_CLIENT
    except Exception as e:
        logger.warning("S3 client init failed: %s", e)
        _S3_CLIENT = None
        return None


def _presign_file_field(file_field) -> str | None:
    """Return a short-lived presigned URL for a Django FileField, if possible."""
    if not file_field:
        return None
    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
    key = getattr(file_field, "name", None) or ""
    if not bucket_name or not key:
        return None
    if not (getattr(settings, "AWS_ACCESS_KEY_ID", None) and getattr(settings, "AWS_SECRET_ACCESS_KEY", None)):
        return None
    client = _get_s3_client()
    if client is None:
        return None
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": key},
            ExpiresIn=_USER_PHOTO_SIGNED_URL_EXPIRES,
        )
    except Exception as e:
        logger.warning("Presign failed key=%s err=%s", key, e)
        return None


def _public_media_uri(serializer: serializers.Serializer, raw_url: str | None) -> str | None:
    """Make media URLs reachable by rewriting internal hosts to PUBLIC_API_ORIGIN."""
    if not raw_url:
        return None
    request = getattr(serializer, "context", {}).get("request") if hasattr(serializer, "context") else None
    if request is None:
        return raw_url
    try:
        from app.core.url_utils import build_public_media_uri

        return build_public_media_uri(request, raw_url) or raw_url
    except Exception:
        return raw_url


class BarbershopImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = BarbershopImage
        fields = ("id", "image", "image_thumb")

    def to_representation(self, instance):
        """
        Ensure extra image URLs are always reachable:
        - Keep CloudFront URLs as-is
        - Rewrite internal hosts to PUBLIC_API_ORIGIN
        - Make relative /media URLs absolute using request/origin
        """
        data = super().to_representation(instance)

        # If AWS is configured, always return CloudFront URLs (optimize delivery).
        aws_ok = bool(getattr(settings, "AWS_ACCESS_KEY_ID", None) and getattr(settings, "AWS_SECRET_ACCESS_KEY", None))
        cdn_domain = (getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None) or "").strip()
        cdn_origin = f"https://{cdn_domain}".rstrip("/") if (aws_ok and cdn_domain) else ""

        def _to_cloudfront(raw: str) -> str:
            raw = (raw or "").strip()
            if not raw or not cdn_origin:
                return raw
            # Absolute URL
            if raw.startswith("http://") or raw.startswith("https://"):
                try:
                    from urllib.parse import urlparse

                    p = urlparse(raw)
                    path = p.path or "/"
                    q = f"?{p.query}" if p.query else ""
                    if path.startswith("/media/"):
                        path = path.replace("/media", "", 1)
                    return f"{cdn_origin}{path}{q}"
                except Exception:
                    return raw
            # Relative path / key
            path = raw if raw.startswith("/") else f"/{raw}"
            if path.startswith("/media/"):
                path = path.replace("/media", "", 1)
            return f"{cdn_origin}{path}"

        if cdn_origin:
            for k in ("image", "image_thumb"):
                raw = data.get(k)
                if raw:
                    data[k] = _to_cloudfront(raw)
            return data

        # Fallback: local/dev → make URLs reachable via PUBLIC_API_ORIGIN when possible
        request = self.context.get("request") if hasattr(self, "context") else None
        if request is not None:
            try:
                from app.core.url_utils import build_public_media_uri

                for k in ("image", "image_thumb"):
                    raw = data.get(k)
                    if raw:
                        data[k] = build_public_media_uri(request, raw) or raw
            except Exception:
                _normalize_barbershop_image_urls(data, instance, keys=("image", "image_thumb"))
        else:
            _normalize_barbershop_image_urls(data, instance, keys=("image", "image_thumb"))
        return data

    def validate_image(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Görsel boyutu 5MB'dan büyük olamaz.")
        return value


class BarbershopCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BarbershopCatalog
        fields = ("id", "image", "image_thumb", "name", "description", "is_active", "order", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def to_representation(self, instance):
        """
        Ensure catalog image URLs are always reachable:
        - Keep CloudFront URLs as-is
        - Rewrite internal hosts to PUBLIC_API_ORIGIN
        - Make relative /media URLs absolute using request/origin
        """
        data = super().to_representation(instance)

        # If AWS is configured, always return CloudFront URLs (optimize delivery).
        aws_ok = bool(getattr(settings, "AWS_ACCESS_KEY_ID", None) and getattr(settings, "AWS_SECRET_ACCESS_KEY", None))
        cdn_domain = (getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None) or "").strip()
        cdn_origin = f"https://{cdn_domain}".rstrip("/") if (aws_ok and cdn_domain) else ""

        def _to_cloudfront(raw: str) -> str:
            raw = (raw or "").strip()
            if not raw or not cdn_origin:
                return raw
            # Absolute URL
            if raw.startswith("http://") or raw.startswith("https://"):
                try:
                    from urllib.parse import urlparse

                    p = urlparse(raw)
                    path = p.path or "/"
                    q = f"?{p.query}" if p.query else ""
                    if path.startswith("/media/"):
                        path = path.replace("/media", "", 1)
                    return f"{cdn_origin}{path}{q}"
                except Exception:
                    return raw
            # Relative path / key
            path = raw if raw.startswith("/") else f"/{raw}"
            if path.startswith("/media/"):
                path = path.replace("/media", "", 1)
            return f"{cdn_origin}{path}"

        if cdn_origin:
            for k in ("image", "image_thumb"):
                raw = data.get(k)
                if raw:
                    data[k] = _to_cloudfront(raw)
            return data

        # Fallback: local/dev → make URLs reachable via PUBLIC_API_ORIGIN when possible
        request = self.context.get("request") if hasattr(self, "context") else None
        if request is not None:
            try:
                from app.core.url_utils import build_public_media_uri

                for k in ("image", "image_thumb"):
                    raw = data.get(k)
                    if raw:
                        data[k] = build_public_media_uri(request, raw) or raw
            except Exception:
                _normalize_barbershop_image_urls(data, instance, keys=("image", "image_thumb"))
        else:
            _normalize_barbershop_image_urls(data, instance, keys=("image", "image_thumb"))
        return data

    def validate_image(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Görsel boyutu 5MB'dan büyük olamaz.")
        return value


def _normalize_barbershop_image_urls(data, obj, keys=("main_image", "main_image_thumb")):
    """Internal host (Docker/backend) URL'lerini PUBLIC_API_ORIGIN ile değiştir; CloudFront veya api/media zaten çalışan URL'leri dokunma."""
    origin = (getattr(settings, "PUBLIC_API_ORIGIN", None) or "").strip().rstrip("/")
    if not origin:
        return

    def _is_internal_host(host):
        if not host:
            return True
        h = host.lower()
        if h in ("localhost", "127.0.0.1", "backend", "backend_dev", "web"):
            return True
        if h.startswith("172.") or h.startswith("10.") or h.startswith("192.168."):
            return True
        return False

    for key in keys:
        if key not in data:
            continue
        val = data.get(key)
        if not val or not isinstance(val, str):
            continue
        val = val.strip()
        if not val.startswith("http://") and not val.startswith("https://"):
            path = val if val.startswith("/") else f"/{val}"
            if "/media/" in path or path.startswith("/barbershops/") or path.startswith("/staff/"):
                if not path.startswith("/media/"):
                    path = f"/media{path}" if path.startswith("/") else f"/media/{path}"
                data[key] = f"{origin}{path}"
            continue
        try:
            from urllib.parse import urlparse
            parsed = urlparse(val)
            host = (parsed.hostname or "").lower()
            if _is_internal_host(host):
                path = parsed.path or "/"
                if parsed.query:
                    path = f"{path}?{parsed.query}"
                data[key] = f"{origin}{path}"
        except Exception:
            pass


class BarbershopSerializer(serializers.ModelSerializer):
    images = BarbershopImageSerializer(many=True, read_only=True)
    catalog = serializers.SerializerMethodField()
    phone = serializers.CharField(source='phone_number', required=False)  # Frontend'den gelen 'phone' field'ını 'phone_number' olarak map et
    categories = serializers.PrimaryKeyRelatedField(many=True, queryset=ShopCategory.objects.all(), required=False)
    weekly_schedule = serializers.SerializerMethodField()

    def get_catalog(self, obj):
        """Sadece aktif katalog öğelerini döndür"""
        catalog_items = obj.catalog.filter(is_active=True).order_by('order', 'created_at')
        return BarbershopCatalogSerializer(catalog_items, many=True, context=self.context).data

    class Meta:
        model = Barbershop
        fields = (
            "id",
            "name",
            "gender",
            "address",
            "system_type",
            "external_booking",
            "latitude","longitude",
            "city",
            "district",
            "phone_number",
            "phone",  # Frontend uyumluluğu için
            "main_image",
            "main_image_thumb",
            "images",
            "catalog",
            "is_verified",
            "is_approved",
            "rejection_reason",
            "rejected_at",
            "description",
            "google_maps_link",
            "categories",
            "weekly_schedule",
            "service_duration_interval",
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
        read_only_fields = ("rating_avg", "total_reviews", "views_weekly", "favorites_count", "created_at", "updated_at", "main_image_thumb", "is_approved", "rejection_reason", "rejected_at")
        extra_kwargs = {
            # Alias kullandığımız için phone_number'ı zorunlu yapma; 'phone' ile beslenecek
            'phone_number': {'required': False, 'allow_blank': True},
            # Vitrin onboarding'de şehir/ilçe daha sonra doldurulabilsin diye zorunlu değil
            'city': {'required': False, 'allow_blank': True},
            'district': {'required': False, 'allow_blank': True},
        }

    def to_representation(self, obj):
        data = super().to_representation(obj)
        _normalize_barbershop_image_urls(data, obj)
        return data

    @extend_schema_field(serializers.DictField)
    def get_weekly_schedule(self, obj):
        schedule = {}
        hours = obj.shop_working_hours.all()
        for h in hours:
            # MON -> mon
            day_code = h.day_of_week.lower()
            if h.is_closed:
                # Frontend treats invalid times as not working
                schedule[day_code] = {"start": -1, "end": -1}
            else:
                schedule[day_code] = {
                    "start": h.start_time.strftime("%H:%M") if h.start_time else "09:00",
                    "end": h.end_time.strftime("%H:%M") if h.end_time else "18:00"
                }
        return schedule

    def validate(self, attrs):
        # phone aliası ile gelen değeri yakala.
        # attrs burada internal değerleri taşır; phone_number beklenir
        phone_val = attrs.get('phone_number')
        # Bazı durumlarda initial_data üzerinden okumak gerekebilir
        if (not phone_val or str(phone_val).strip() == ''):
            raw = getattr(self, 'initial_data', {}) or {}
            phone_val = raw.get('phone') or raw.get('phone_number')
        # Frontend tarafında zaten zorunlu alan kontrolü yapıldığı için
        # backend'de ekstra ValidationError fırlatmayalım; sadece normalize edelim.
        if phone_val is None:
            phone_val = ''
        attrs['phone_number'] = phone_val
        
        # Latitude ve longitude string'den float'a çevir
        if 'latitude' in attrs and attrs['latitude'] is not None:
            try:
                attrs['latitude'] = float(attrs['latitude'])
            except (ValueError, TypeError):
                attrs['latitude'] = None
        
        if 'longitude' in attrs and attrs['longitude'] is not None:
            try:
                attrs['longitude'] = float(attrs['longitude'])
            except (ValueError, TypeError):
                attrs['longitude'] = None
        
        # Google Maps link: zorunlu değil, format doğrulaması yok - herhangi bir metin kabul
        # (Partner uygulamasında ilk kayıtta validation yok, direkt devam edebilsinler)

        # External booking validation
        system_type = attrs.get('system_type')
        external_booking = attrs.get('external_booking', {})
        
        if system_type == 'external':
            # En az bir harici yontem secilmeli
            has_enabled_method = False
            for method in ['whatsapp', 'website', 'instagram', 'other_app', 'custom']:
                method_data = external_booking.get(method, {})
                if isinstance(method_data, dict) and method_data.get('enabled'):
                    has_enabled_method = True
                    break
            if not has_enabled_method:
                raise serializers.ValidationError({
                    'external_booking': 'En az bir harici randevu yontemi secmelisiniz.'
                })
        
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Banlı veya pasif abonelikli kuaförler için favorites_count'u sıfırla
        try:
            status = getattr(instance, "subscription", None)
            is_active_sub = status and getattr(status, "status", None) in ['trial', 'active', 'lifetime', 'grace_period']
            if (not getattr(instance, "is_verified", True)) or (not is_active_sub):
                data["favorites_count"] = 0
        except Exception:
            data["favorites_count"] = 0
        return data

    def validate_main_image(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Görsel boyutu 5MB'dan büyük olamaz.")
        return value


class StaffCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffCatalogImage
        fields = ("id", "image")

    def validate_image(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Görsel boyutu 5MB'dan büyük olamaz.")
        return value


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
    weekly_schedule = serializers.SerializerMethodField()
    user_image_url = serializers.SerializerMethodField()
    user_image_thumb_url = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = (
            "id", "barbershop", "user", "photo", "photo_thumb", "email", "certificate", "is_admin",
            "catalog", "total_reviews", "user_full_name",
            "bio", "gender_preference", "experience_years", "career_start_year", "tags",
            "rating_avg", "staff_services", "weekly_schedule",
            "auto_approval", "commission_rate", "appointment_interval",
            "instagram", "facebook", "twitter", "whatsapp",
            "user_image_url", "user_image_thumb_url"
        )
        read_only_fields = ("total_reviews", "rating_avg", "experience_years", "photo_thumb", "user_image_url", "user_image_thumb_url")

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_user_image_url(self, obj):
        u = getattr(obj, "user", None)
        if u and u.image:
            signed = _presign_file_field(u.image)
            if signed:
                return signed
            return _public_media_uri(self, u.image.url) or u.image.url
        return None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_user_image_thumb_url(self, obj):
        u = getattr(obj, "user", None)
        if u and u.image_thumb:
            signed = _presign_file_field(u.image_thumb)
            if signed:
                return signed
            return _public_media_uri(self, u.image_thumb.url) or u.image_thumb.url
        elif u and u.image:
            signed = _presign_file_field(u.image)
            if signed:
                return signed
            return _public_media_uri(self, u.image.url) or u.image.url
        return None

    def to_representation(self, instance):
        """
        Ensure staff avatar URLs are reachable in both apps.
        Staff photos can be stored in private S3; direct `.url` or CDN rewrites may 403.
        If AWS is configured, return short-lived presigned URLs for `photo` and `photo_thumb`.
        """
        data = super().to_representation(instance)
        try:
            for attr, key in (("photo_thumb", "photo_thumb"), ("photo", "photo")):
                ff = getattr(instance, attr, None)
                if not ff:
                    continue
                signed = _presign_file_field(ff)
                if signed:
                    data[key] = signed
                else:
                    raw = data.get(key)
                    data[key] = _public_media_uri(self, raw) or raw
        except Exception:
            pass
        return data

    @extend_schema_field(serializers.DictField)
    def get_weekly_schedule(self, obj):
        # Ana uygulama (barber detail) her zaman mon..sun 7 gün bekliyor; eksik günler Kapalı sayılıyor.
        # Bu yüzden her zaman 7 gün döndürüyoruz.
        from django.utils import timezone
        from django.db.models import Q

        WEEK_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        schedule = {d: {"start": -1, "end": -1} for d in WEEK_DAYS}
        today = timezone.localdate()

        # 1. StaffWorkingHours (yeni model) — bugün geçerli segmentleri kullan
        new_hours = obj.staff_working_hours.filter(
            valid_from__lte=today
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=today))
        # Aynı kullanıcının aynı dükkandaki başka bir Staff kaydında saat varsa onu kullan (çift kayıt senaryosu)
        if not new_hours.exists() and obj.user_id and obj.barbershop_id:
            other_staff = Staff.objects.filter(
                barbershop_id=obj.barbershop_id, user_id=obj.user_id
            ).exclude(pk=obj.pk).first()
            if other_staff:
                new_hours = other_staff.staff_working_hours.filter(
                    valid_from__lte=today
                ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=today))

        if new_hours.exists():
            for h in new_hours:
                day_code = h.day_of_week.lower()
                if day_code not in schedule:
                    continue
                if h.is_closed:
                    schedule[day_code] = {"start": -1, "end": -1}
                elif h.start_time:
                    schedule[day_code] = {
                        "start": h.start_time.strftime("%H:%M"),
                        "end": h.end_time.strftime("%H:%M") if h.end_time else "18:00"
                    }
            return schedule

        # 2. Fallback: WorkSchedule (eski model)
        old_hours = obj.work_schedules.all()
        if old_hours.exists():
            for h in old_hours:
                day_code = h.day_of_week.lower()
                if day_code in schedule and h.start_time and h.end_time:
                    schedule[day_code] = {
                        "start": h.start_time.strftime("%H:%M"),
                        "end": h.end_time.strftime("%H:%M")
                    }
        return schedule

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
        return StaffServiceSerializer(obj.staff_services.all(), many=True).data

    def validate_photo(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Görsel boyutu 5MB'dan büyük olamaz.")
        return value


class WorkScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkSchedule
        fields = ("id", "staff", "day_of_week", "start_time", "end_time", "break_time")


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


class ReviewSerializer(serializers.ModelSerializer):
    user_display_name = serializers.SerializerMethodField()
    user_full_name = serializers.SerializerMethodField()
    barbershop_name = serializers.SerializerMethodField()
    staff_name = serializers.SerializerMethodField()
    user_image_url = serializers.SerializerMethodField()
    user_image_thumb_url = serializers.SerializerMethodField()
    replies = ReviewReplySerializer(many=True, read_only=True)
    replies_count = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    user_has_liked = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = (
            "id", 
            "user", 
            "barbershop", 
            "staff", 
            "rating", 
            "comment", 
            "reply", 
            "replied_at", 
            "is_anonymous", 
            "created_at", 
            "updated_at", 
            "user_display_name", 
            "user_full_name", 
            "barbershop_name", 
            "staff_name", 
            "user_image_url",
            "user_image_thumb_url",
            "replies", 
            "replies_count",
            "likes_count",
            "user_has_liked",
        )
        read_only_fields = (
            "created_at", 
            "updated_at", 
            "user", 
            "barbershop", 
            "reply", 
            "replied_at", 
            "user_display_name", 
            "user_full_name", 
            "barbershop_name", 
            "staff_name", 
            "user_image_url",
            "user_image_thumb_url",
            "replies", 
            "replies_count",
            "likes_count",
            "user_has_liked",
        )

    def get_user_image_url(self, obj):
        if obj.is_anonymous:
            return None
        u = getattr(obj, "user", None)
        if u and u.image:
            return u.image.url
        return None

    def get_user_image_thumb_url(self, obj):
        if obj.is_anonymous:
            return None
        u = getattr(obj, "user", None)
        if u and u.image_thumb:
            return u.image_thumb.url
        elif u and u.image:
            return u.image.url
        return None

    def get_user_display_name(self, obj):
        if obj.is_anonymous:
            return "****"
        u = getattr(obj, "user", None)
        if not u:
            return "****"
        name = getattr(u, "full_name", None) or getattr(u, "first_name", None) or getattr(u, "email", None) or "Kullanıcı"
        return name

    def get_user_full_name(self, obj):
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

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_user_has_liked(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return obj.likes.filter(id=user.id).exists()

class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ("id", "barbershop", "name", "created_at")
        read_only_fields = ("barbershop", "created_at")


class ServiceSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    price_range = serializers.SerializerMethodField()
    
    class Meta:
        model = Service
        fields = ("id", "barbershop", "category", "category_name", "name", "price", "duration", "is_active", "target_gender", "created_at", "price_range")
        read_only_fields = ("barbershop", "created_at", "price_range")
    
    def get_price_range(self, obj):
        from .models import StaffService
        staff_prices = list(
            StaffService.objects.filter(service=obj, is_active=True, price__isnull=False)
            .values_list('price', flat=True)
        )
        if not staff_prices:
            if obj.price is None:
                return None  # Fiyat girilmemiş — müşteri uygulaması "Fiyat belirtilmemiş" gösterir
            return {'min': float(obj.price), 'max': float(obj.price)}
        base = float(obj.price) if obj.price is not None else None
        prices = [float(p) for p in staff_prices]
        if base is not None:
            prices.append(base)
        return {'min': min(prices), 'max': max(prices)}


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


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ("id", "barbershop", "created_at")


class BarbershopWithFavoriteSerializer(serializers.ModelSerializer):
    is_favorited = serializers.SerializerMethodField()
    
    class Meta:
        model = Barbershop
        fields = (
            "id", 
            "name", 
            "address", 
            "city", 
            "district", 
            "main_image", 
            "main_image_thumb", 
            "rating_avg", 
            "total_reviews", 
            "is_favorited", 
            "favorites_count", 
            "description", 
            "phone_number", 
        )
    
    @extend_schema_field(serializers.BooleanField)
    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from .models import Favorite
            return Favorite.objects.filter(user=request.user, barbershop=obj).exists()
        return False

    def to_representation(self, instance):
        data = super().to_representation(instance)
        _normalize_barbershop_image_urls(data, instance)
        try:
            status = getattr(instance, "subscription", None)
            is_active_sub = status and getattr(status, "status", None) in ['trial', 'active', 'lifetime', 'grace_period']
            if (not getattr(instance, "is_verified", True)) or (not is_active_sub):
                data["favorites_count"] = 0
        except Exception:
            data["favorites_count"] = 0
        return data


class BarbershopDetailSerializer(BarbershopSerializer):
    is_favorited = serializers.SerializerMethodField()

    class Meta(BarbershopSerializer.Meta):
        fields = BarbershopSerializer.Meta.fields + ("is_favorited",)

    @extend_schema_field(serializers.BooleanField)
    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            from .models import Favorite
            return Favorite.objects.filter(user=request.user, barbershop=obj).exists()
        return False


class ShopWorkingHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopWorkingHours
        fields = ("id", "barbershop", "day_of_week", "start_time", "end_time", "break_start_time", "break_end_time", "is_closed", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {
            'barbershop': {'required': False},  # Set in perform_create
        }


class StaffWorkingHoursSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.user.email', read_only=True)
    
    class Meta:
        model = StaffWorkingHours
        fields = ("id", "staff", "staff_name", "day_of_week", "start_time", "end_time", "break_start_time", "break_end_time", "is_closed", "created_at", "updated_at")


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
        )
        # BreakWindow model has created_at but no updated_at
        read_only_fields = ("created_by", "created_at")

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

        from app.barbers.services.breaks import validate_break_window_constraints

        try:
            validate_break_window_constraints(
                barbershop=barbershop,
                staff=staff,
                scope=scope,
                date_value=date_val,
                start_time=start_time,
                end_time=end_time,
                instance=self.instance,
            )
        except ValidationError as exc:
            raise drf_serializers.ValidationError(exc.message_dict or exc.messages) from exc

        attrs["barbershop"] = barbershop
        if user and user.is_authenticated:
            attrs["created_by"] = user
        return attrs


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
    is_on_break = serializers.BooleanField(required=False, default=False)
    is_on_leave = serializers.BooleanField(required=False, default=False)
    start_time = serializers.TimeField(allow_null=True)
    end_time = serializers.TimeField(allow_null=True)
    break_start_time = serializers.TimeField(allow_null=True, required=False)
    break_end_time = serializers.TimeField(allow_null=True, required=False)
    break_ends_in = serializers.IntegerField(allow_null=True, required=False)
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

class ShopCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopCategory
        fields = "__all__"

