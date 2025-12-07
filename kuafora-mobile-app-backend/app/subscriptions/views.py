from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from .models import SubscriptionPlan, Subscription, Coupon, CouponUsage
from .serializers import (
    SubscriptionPlanSerializer,
    SubscriptionSerializer,
    SubscriptionCreateSerializer,
    CouponValidateSerializer,
    ApplyCouponSerializer,
    CouponPublicSerializer,
)
from app.barbers.models import Barbershop


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """Abonelik planlarını listele"""
    
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # booking_system_type parametresi ile filtreleme
        system_type = self.request.query_params.get('system_type')
        if system_type:
            # JSON field içinde arama
            qs = qs.filter(booking_system_types__contains=[system_type])
        
        return qs.order_by('sort_order', 'price_monthly')


class CouponValidateApi(APIView):
    """Kupon kodu doğrulama - Public API"""
    
    permission_classes = [AllowAny]
    serializer_class = CouponValidateSerializer
    
    def post(self, request):
        serializer = CouponValidateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'valid': False,
                'error': serializer.errors.get('code', ['Geçersiz kupon'])[0]
            }, status=status.HTTP_400_BAD_REQUEST)
        
        code = serializer.validated_data['code']
        coupon = Coupon.objects.get(code=code)
        
        return Response({
            'valid': True,
            'coupon': CouponPublicSerializer(coupon).data,
            'message': self._get_success_message(coupon)
        })
    
    def _get_success_message(self, coupon):
        if coupon.discount_type == 'lifetime':
            remaining = coupon.remaining_uses
            if remaining is not None:
                return f'🎉 Ömür boyu ücretsiz! ({remaining} kullanım hakkı kaldı)'
            return '🎉 Ömür boyu ücretsiz!'
        elif coupon.discount_type == 'free_months':
            return f'🎁 {coupon.discount_value} ay ücretsiz!'
        elif coupon.discount_type == 'percent':
            return f'💰 %{coupon.discount_value} indirim!'
        elif coupon.discount_type == 'fixed':
            return f'💰 {coupon.discount_value}₺ indirim!'
        return 'Kupon geçerli!'


class SubscriptionViewSet(viewsets.ModelViewSet):
    """Abonelik yönetimi - Partner API"""
    
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        # Kullanıcının admin olduğu salonların abonelikleri
        barbershop_ids = user.staff_profiles.filter(is_admin=True).values_list('barbershop_id', flat=True)
        return Subscription.objects.filter(barbershop_id__in=barbershop_ids)
    
    @action(detail=False, methods=['get'])
    def my_subscription(self, request):
        """Mevcut salonun abonelik durumu"""
        barbershop_id = request.query_params.get('barbershop_id')
        
        if not barbershop_id:
            # İlk admin olduğu salonu al
            staff = request.user.staff_profiles.filter(is_admin=True).first()
            if not staff:
                return Response({'error': 'Salon bulunamadı'}, status=404)
            barbershop_id = staff.barbershop_id
        
        try:
            subscription = Subscription.objects.select_related('plan', 'coupon').get(
                barbershop_id=barbershop_id
            )
            return Response(SubscriptionSerializer(subscription).data)
        except Subscription.DoesNotExist:
            return Response({'error': 'Abonelik bulunamadı'}, status=404)
    
    @action(detail=False, methods=['post'])
    def apply_coupon(self, request):
        """Mevcut aboneliğe kupon uygula"""
        serializer = ApplyCouponSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': serializer.errors.get('code', ['Geçersiz kupon'])[0]
            }, status=status.HTTP_400_BAD_REQUEST)
        
        barbershop_id = request.data.get('barbershop_id')
        if not barbershop_id:
            staff = request.user.staff_profiles.filter(is_admin=True).first()
            if not staff:
                return Response({'error': 'Salon bulunamadı'}, status=404)
            barbershop_id = staff.barbershop_id
        
        # Yetki kontrolü
        if not request.user.staff_profiles.filter(barbershop_id=barbershop_id, is_admin=True).exists():
            return Response({'error': 'Bu salon için yetkiniz yok'}, status=403)
        
        try:
            subscription = Subscription.objects.select_related('coupon').get(
                barbershop_id=barbershop_id
            )
        except Subscription.DoesNotExist:
            return Response({'error': 'Abonelik bulunamadı'}, status=404)
        
        # Zaten kupon uygulanmış mı?
        if subscription.coupon:
            return Response({
                'success': False,
                'error': f'Bu aboneliğe zaten "{subscription.coupon.code}" kuponu uygulanmış'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        code = serializer.validated_data['code']
        coupon = Coupon.objects.get(code=code)
        
        # Kuponu uygula
        with transaction.atomic():
            subscription.coupon = coupon
            subscription.coupon_applied_at = timezone.now()
            
            if coupon.discount_type == 'lifetime':
                subscription.status = 'lifetime'
            elif coupon.discount_type == 'free_months':
                # Trial süresini uzat
                subscription.trial_ends_at = subscription.trial_ends_at + timedelta(days=30 * coupon.discount_value)
            # percent ve fixed ödeme altyapısı gelince işlenecek
            
            subscription.save()
            
            # Kupon kullanım sayısını artır
            coupon.current_uses += 1
            coupon.save()
            
            # Kullanım kaydı oluştur
            CouponUsage.objects.create(coupon=coupon, subscription=subscription)
        
        return Response({
            'success': True,
            'subscription': SubscriptionSerializer(subscription).data,
            'message': self._get_success_message(coupon)
        })
    
    def _get_success_message(self, coupon):
        if coupon.discount_type == 'lifetime':
            return '🎉 Tebrikler! Aboneliğiniz ömür boyu ücretsiz oldu!'
        elif coupon.discount_type == 'free_months':
            return f'🎁 {coupon.discount_value} ay eklendi!'
        elif coupon.discount_type == 'percent':
            return f'💰 %{coupon.discount_value} indirim uygulandı!'
        elif coupon.discount_type == 'fixed':
            return f'💰 {coupon.discount_value}₺ indirim uygulandı!'
        return 'Kupon uygulandı!'


class CreateSubscriptionApi(APIView):
    """Kuaför kaydında abonelik oluşturma"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = SubscriptionCreateSerializer
    
    def post(self, request, barbershop_id):
        """Yeni abonelik oluştur"""
        
        # Salon kontrolü
        barbershop = get_object_or_404(Barbershop, id=barbershop_id)
        
        # Yetki kontrolü
        if not request.user.staff_profiles.filter(barbershop=barbershop, is_admin=True).exists():
            return Response({'error': 'Bu salon için yetkiniz yok'}, status=403)
        
        # Zaten abonelik var mı?
        if hasattr(barbershop, 'subscription'):
            return Response({
                'error': 'Bu salon için zaten abonelik mevcut',
                'subscription': SubscriptionSerializer(barbershop.subscription).data
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = SubscriptionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        plan_slug = serializer.validated_data.get('plan_slug')
        coupon_code = serializer.validated_data.get('coupon_code')
        
        # Plan belirleme
        if plan_slug:
            plan = SubscriptionPlan.objects.get(slug=plan_slug, is_active=True)
        else:
            # Salonun randevu sistemine göre otomatik plan seçimi
            booking_type = barbershop.booking_system  # info_system, external, kuafora_booking
            
            if booking_type == 'kuafora_booking':
                plan = SubscriptionPlan.objects.filter(
                    slug='randevu', 
                    is_active=True
                ).first()
            else:
                plan = SubscriptionPlan.objects.filter(
                    slug='bilgi', 
                    is_active=True
                ).first()
            
            if not plan:
                # Fallback: İlk aktif plan
                plan = SubscriptionPlan.objects.filter(is_active=True).first()
                if not plan:
                    return Response({'error': 'Aktif plan bulunamadı'}, status=500)
        
        with transaction.atomic():
            # Abonelik oluştur
            subscription = Subscription.objects.create(
                barbershop=barbershop,
                plan=plan,
                status='trial',
                trial_ends_at=timezone.now() + timedelta(days=90)
            )
            
            # Kupon varsa uygula
            if coupon_code:
                coupon = Coupon.objects.get(code=coupon_code)
                
                subscription.coupon = coupon
                subscription.coupon_applied_at = timezone.now()
                
                if coupon.discount_type == 'lifetime':
                    subscription.status = 'lifetime'
                elif coupon.discount_type == 'free_months':
                    subscription.trial_ends_at = subscription.trial_ends_at + timedelta(days=30 * coupon.discount_value)
                
                subscription.save()
                
                coupon.current_uses += 1
                coupon.save()
                
                CouponUsage.objects.create(coupon=coupon, subscription=subscription)
        
        return Response({
            'success': True,
            'subscription': SubscriptionSerializer(subscription).data
        }, status=status.HTTP_201_CREATED)


class SubscriptionStatusApi(APIView):
    """Abonelik durumu kontrolü - Public (sadece aktif mi değil mi)"""
    
    permission_classes = [AllowAny]
    serializer_class = None
    
    def get(self, request, barbershop_id):
        """Salonun abonelik durumunu kontrol et"""
        
        try:
            subscription = Subscription.objects.get(barbershop_id=barbershop_id)
            return Response({
                'is_active': subscription.is_active_subscription,
                'status': subscription.status,
            })
        except Subscription.DoesNotExist:
            return Response({
                'is_active': False,
                'status': 'none',
            })
