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
    ConfirmEmailView,
    VerifyEmailCodeView,
    ForgotPasswordView,
    ResetPasswordView,
    ResetPasswordByCodeView,
    ResetPasswordConfirmView,
    CheckEmailView,
    CheckPhoneView,
    UserAddressViewSet,
    BarbershopStatsView,
    ProfilePhotoUploadView,
    ProfilePhotoServeView,
    UserPhotoServeView,
    UserPhotoUrlView,
    ResolveUserView,
)

router = DefaultRouter()
router.register(r'addresses', UserAddressViewSet, basename='user-address')

urlpatterns = [
    path('', include(router.urls)),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    # APPEND_SLASH=False olduğu için hem /logout hem /logout/ çalışsın
    path('logout', LogoutView.as_view(), name='logout-no-slash'),
    path('me/', MeView.as_view(), name='me'),
    path('me', MeView.as_view(), name='me-no-slash'),  # Alias without trailing slash
    path('users/me/', MeView.as_view(), name='me-legacy'),
    path('me/photo/', ProfilePhotoUploadView.as_view(), name='profile-photo-upload'),
    path('me/photo/serve/', ProfilePhotoServeView.as_view(), name='profile-photo-serve'),
    path('users/<uuid:user_id>/photo/serve/', UserPhotoServeView.as_view(), name='user-photo-serve'),
    path('users/<uuid:user_id>/photo/url/', UserPhotoUrlView.as_view(), name='user-photo-url'),
    path('update/', UserUpdateView.as_view(), name='user-update'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('verify-email/confirm/', ConfirmEmailView.as_view(), name='verify-email-confirm'),
    path('verify-email/code/', VerifyEmailCodeView.as_view(), name='verify-email-code'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('reset-password-by-code/', ResetPasswordByCodeView.as_view(), name='reset-password-by-code'),
    path('reset-password/confirm/', ResetPasswordConfirmView.as_view(), name='reset-password-confirm'),
    path('check-email/', CheckEmailView.as_view(), name='check-email'),
    path('check-phone/', CheckPhoneView.as_view(), name='check-phone'),
    path('resolve/', ResolveUserView.as_view(), name='user-resolve'),
    path('barbershop-stats/<int:barbershop_id>/', BarbershopStatsView.as_view(), name='barbershop-stats'),
]