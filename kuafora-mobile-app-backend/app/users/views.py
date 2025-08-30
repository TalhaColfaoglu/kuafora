from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Count

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    EmailSerializer,
    PhoneSerializer,
    ResetPasswordSerializer,
    UserAddressSerializer,
    FavoriteSerializer,
    LastViewedSerializer,
)
from .models import UserAddress, Favorite, LastViewed

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class LogoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user


class UserUpdateView(generics.UpdateAPIView):
    serializer_class = UserUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"detail": "Password changed successfully"})


class VerifyEmailView(generics.GenericAPIView):
    serializer_class = EmailSerializer

    def post(self, request, *args, **kwargs):
        # In real production, send an email containing token link
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email=serializer.validated_data["email"]).first()
        if not user:
            return Response({"detail": "If the email exists, a verification mail will be sent."})
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return Response({"uid": uid, "token": token})


class ForgotPasswordView(generics.GenericAPIView):
    serializer_class = EmailSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email=serializer.validated_data["email"]).first()
        if not user:
            return Response({"detail": "If the email exists, a reset mail will be sent."})
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return Response({"uid": uid, "token": token})


class ResetPasswordView(generics.GenericAPIView):
    serializer_class = ResetPasswordSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            uid = force_str(urlsafe_base64_decode(serializer.validated_data["uid"]))
            user = User.objects.get(pk=uid)
        except Exception:
            return Response({"detail": "Invalid uid"}, status=status.HTTP_400_BAD_REQUEST)
        if not default_token_generator.check_token(user, serializer.validated_data["token"]):
            return Response({"detail": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"detail": "Password reset successful"})


class CheckEmailView(generics.GenericAPIView):
    serializer_class = EmailSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exists = User.objects.filter(email=serializer.validated_data["email"]).exists()
        return Response({"exists": exists})


class CheckPhoneView(generics.GenericAPIView):
    serializer_class = PhoneSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        exists = User.objects.filter(phone=phone).exists()
        return Response({"exists": exists})


class UserAddressViewSet(viewsets.ModelViewSet):
    serializer_class = UserAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserAddress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        if serializer.validated_data.get("is_default"):
            UserAddress.objects.filter(user=self.request.user, is_default=True).update(is_default=False)
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.is_default:
            UserAddress.objects.filter(user=self.request.user).exclude(pk=instance.pk).update(is_default=False)


# Favorites yönetimini kullanıcı profiline taşıdık; ayrı endpoint gerekli değil


class LastViewedViewSet(viewsets.ModelViewSet):
    serializer_class = LastViewedSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LastViewed.objects.filter(user=self.request.user)[:7]

    def perform_create(self, serializer):
        # Remove old entries if more than 7
        user_last_viewed = LastViewed.objects.filter(user=self.request.user)
        if user_last_viewed.count() >= 7:
            oldest_entry = user_last_viewed.order_by('viewed_at').first()
            if oldest_entry:
                oldest_entry.delete()
        
        # Update existing entry or create new one
        barbershop = serializer.validated_data['barbershop']
        last_viewed, created = LastViewed.objects.get_or_create(
            user=self.request.user,
            barbershop=barbershop,
            defaults={'viewed_at': serializer.validated_data.get('viewed_at')}
        )
        if not created:
            last_viewed.save()  # Update viewed_at timestamp
        return last_viewed


class BarbershopStatsView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, barbershop_id):
        favorites_count = Favorite.objects.filter(barbershop_id=barbershop_id).count()
        views_count = LastViewed.objects.filter(barbershop_id=barbershop_id).count()
        
        return Response({
            'favorites_count': favorites_count,
            'views_count': views_count,
        })


