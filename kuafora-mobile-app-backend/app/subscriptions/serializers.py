from rest_framework import serializers
from .models import SubscriptionPlan, Subscription, Coupon, CouponUsage


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Abonelik planı serializer"""
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'slug', 'description', 
            'price_monthly', 'price_yearly',
            'features', 'booking_system_types',
            'is_active', 'sort_order'
        ]


class CouponPublicSerializer(serializers.ModelSerializer):
    """Kupon doğrulama için public serializer"""
    
    discount_display = serializers.ReadOnlyField()
    is_valid = serializers.ReadOnlyField()
    remaining_uses = serializers.ReadOnlyField()
    
    class Meta:
        model = Coupon
        fields = [
            'code', 
            'discount_type', 
            'discount_value',
            'discount_display',
            'is_valid',
            'remaining_uses',
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    """Abonelik serializer"""
    
    plan = SubscriptionPlanSerializer(read_only=True)
    coupon_code = serializers.CharField(source='coupon.code', read_only=True, allow_null=True)
    status_info = serializers.ReadOnlyField()
    days_until_trial_ends = serializers.ReadOnlyField()
    is_active_subscription = serializers.ReadOnlyField()
    applied_coupons = serializers.SerializerMethodField()
    
    def get_applied_coupons(self, obj: Subscription):
        # En güncel önce görünsün
        qs = obj.coupon_usages.select_related('coupon').order_by('-applied_at')
        out = []
        for usage in qs:
            c = usage.coupon
            days_added = 0
            if c.discount_type == 'free_months':
                # Basit ve tutarlı: 1 ay = 30 gün
                days_added = int(c.discount_value) * 30
            out.append({
                'code': c.code,
                'discount_type': c.discount_type,
                'discount_value': c.discount_value,
                'discount_display': c.discount_display,
                'applied_at': usage.applied_at,
                'days_added': days_added,
            })
        return out
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'status', 'status_info',
            'started_at', 'trial_ends_at',
            'current_period_start', 'current_period_end',
            'coupon_code', 'coupon_applied_at',
            'days_until_trial_ends', 'is_active_subscription',
            'applied_coupons',
            'created_at', 'updated_at'
        ]


class SubscriptionCreateSerializer(serializers.Serializer):
    """Abonelik oluşturma serializer"""
    
    plan_slug = serializers.CharField(required=False, allow_blank=True)
    coupon_code = serializers.CharField(required=False, allow_blank=True)
    
    def validate_plan_slug(self, value):
        if value:
            try:
                SubscriptionPlan.objects.get(slug=value, is_active=True)
            except SubscriptionPlan.DoesNotExist:
                raise serializers.ValidationError("Geçersiz plan")
        return value
    
    def validate_coupon_code(self, value):
        if value:
            value = value.upper().strip()
            try:
                coupon = Coupon.objects.get(code=value)
                if not coupon.is_valid:
                    raise serializers.ValidationError("Kupon geçersiz veya süresi dolmuş")
            except Coupon.DoesNotExist:
                raise serializers.ValidationError("Kupon bulunamadı")
        return value


class CouponValidateSerializer(serializers.Serializer):
    """Kupon doğrulama serializer"""
    
    code = serializers.CharField(max_length=50)
    
    def validate_code(self, value):
        value = value.upper().strip()
        try:
            coupon = Coupon.objects.get(code=value)
            if not coupon.is_valid:
                if not coupon.is_active:
                    raise serializers.ValidationError("Bu kupon aktif değil")
                if coupon.max_uses and coupon.current_uses >= coupon.max_uses:
                    raise serializers.ValidationError("Bu kuponun kullanım limiti doldu")
                raise serializers.ValidationError("Kupon geçerli değil")
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Kupon bulunamadı")
        return value


class ApplyCouponSerializer(serializers.Serializer):
    """Kupon uygulama serializer"""
    
    code = serializers.CharField(max_length=50)
    
    def validate_code(self, value):
        value = value.upper().strip()
        try:
            coupon = Coupon.objects.get(code=value)
            if not coupon.is_valid:
                raise serializers.ValidationError("Kupon geçerli değil")
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Kupon bulunamadı")
        return value
