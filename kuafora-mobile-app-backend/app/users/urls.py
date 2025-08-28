from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    MeView,
    UserUpdateView,
    ChangePasswordView,
    VerifyEmailView,
    ForgotPasswordView,
    ResetPasswordView,
    CheckEmailView,
    CheckPhoneView,
    UserAddressViewSet,
    FavoriteViewSet,
    LastViewedViewSet,
    BarbershopStatsView,
)

router = DefaultRouter()
router.register(r'addresses', UserAddressViewSet, basename='user-address')
router.register(r'favorites', FavoriteViewSet, basename='favorite')
router.register(r'last-viewed', LastViewedViewSet, basename='last-viewed')

urlpatterns = [
    path('', include(router.urls)),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('update/', UserUpdateView.as_view(), name='user-update'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('check-email/', CheckEmailView.as_view(), name='check-email'),
    path('check-phone/', CheckPhoneView.as_view(), name='check-phone'),
    path('barbershop-stats/<int:barbershop_id>/', BarbershopStatsView.as_view(), name='barbershop-stats'),
]


