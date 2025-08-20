from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    MeView,
    ChangePasswordView,
    VerifyEmailView,
    ForgotPasswordView,
    ResetPasswordView,
)

urlpatterns = [
    path("register", RegisterView.as_view(), name="auth-register"),
    path("login", LoginView.as_view(), name="auth-login"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
    path("me", MeView.as_view(), name="auth-me"),
    path("change-password", ChangePasswordView.as_view(), name="auth-change-password"),
    path("verify-email", VerifyEmailView.as_view(), name="auth-verify-email"),
    path("forgot-password", ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("reset-password", ResetPasswordView.as_view(), name="auth-reset-password"),
    path("token/refresh", TokenRefreshView.as_view(), name="token_refresh"),
]


