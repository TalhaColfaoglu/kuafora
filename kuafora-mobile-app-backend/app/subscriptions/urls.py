from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SubscriptionPlanViewSet,
    SubscriptionViewSet,
    CouponValidateApi,
    CreateSubscriptionApi,
    SubscriptionStatusApi,
)

router = DefaultRouter()
router.register(r'plans', SubscriptionPlanViewSet, basename='subscription-plans')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscriptions')

urlpatterns = [
    path('', include(router.urls)),
    
    # Kupon doğrulama
    path('coupons/validate/', CouponValidateApi.as_view(), name='coupon-validate'),
    
    # Abonelik oluşturma (kuaför kaydında)
    path('barbershops/<int:barbershop_id>/subscription/', CreateSubscriptionApi.as_view(), name='create-subscription'),
    
    # Abonelik durumu kontrolü (public)
    path('barbershops/<int:barbershop_id>/subscription/status/', SubscriptionStatusApi.as_view(), name='subscription-status'),
]
