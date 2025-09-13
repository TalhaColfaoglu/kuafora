from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Count
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.conf import settings

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
    LogoutSerializer,
    BarbershopStatsSerializer,
    
)
from .models import UserAddress
from app.barbers.models import Barbershop, LastViewed, ViewEvent

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


@extend_schema(exclude=True)
class LogoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LogoutSerializer

    @extend_schema(request=LogoutSerializer, responses={205: OpenApiResponse(description="Logged out")})
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

    def update(self, request, *args, **kwargs):
        # Sadece full_name ve gender güncellenebilir; email/phone immutable
        mutable = request.data.copy()
        mutable.pop("email", None)
        mutable.pop("phone", None)
        request._full_data = mutable  # type: ignore
        return super().update(request, *args, **kwargs)


class ProfilePhotoUploadView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'image': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Profile photo image file'
                    }
                }
            }
        },
        responses={
            200: OpenApiResponse(description="Profile photo updated successfully"),
            400: OpenApiResponse(description="Invalid image file"),
            500: OpenApiResponse(description="Server error")
        }
    )
    def post(self, request, *args, **kwargs):
        try:
            if 'image' not in request.FILES:
                return Response(
                    {"detail": "No image file provided"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            image_file = request.FILES['image']
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if image_file.content_type not in allowed_types:
                return Response(
                    {"detail": "Invalid file type. Only JPEG, PNG and GIF are allowed."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate file size (max 5MB)
            if image_file.size > 5 * 1024 * 1024:
                return Response(
                    {"detail": "File size too large. Maximum 5MB allowed."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Ensure media directory exists
            import os
            media_root = os.path.join(settings.MEDIA_ROOT, 'users', 'images')
            os.makedirs(media_root, exist_ok=True)
            
            # Ensure the directory is writable
            if not os.access(media_root, os.W_OK):
                return Response(
                    {"detail": "Media directory is not writable"}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Log directory info for debugging
            print(f"Media root: {settings.MEDIA_ROOT}")
            print(f"Users images dir: {media_root}")
            print(f"Directory exists: {os.path.exists(media_root)}")
            print(f"Directory writable: {os.access(media_root, os.W_OK)}")
            
            # Update user's profile photo
            user = request.user
            user.image = image_file
            user.save()
            
            # Log success info
            print(f"User {user.id} profile photo updated successfully")
            print(f"Image path: {user.image.path if user.image else 'None'}")
            print(f"Image URL: {user.image.url if user.image else 'None'}")
            
            return Response({
                "detail": "Profile photo updated successfully",
                "image_url": user.image.url if user.image else None
            })
        except Exception as e:
            print(f"Profile photo upload error: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {"detail": f"Upload failed: {str(e)}", "error_type": str(type(e).__name__)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
        email = serializer.validated_data["email"]
        exists = User.objects.filter(email=email).exists()
        # Ek alanlar: herhangi bir kuaföre bağlı mı?
        try:
            from app.barbers.models import Staff  # type: ignore
        except Exception:  # döngüsel import riskine karşı
            Staff = None  # type: ignore

        is_staff_attached = False
        attached_barbershop_id = None
        attached_barbershop_name = None
        if exists and Staff is not None:
            qs = Staff.objects.filter(user__email=email).select_related("barbershop")
            if qs.exists():
                is_staff_attached = True
                bs = qs.first().barbershop  # type: ignore
                attached_barbershop_id = getattr(bs, "id", None)
                attached_barbershop_name = getattr(bs, "name", None)

        return Response({
            "exists": exists,
            "is_staff": is_staff_attached,
            "barbershop_id": attached_barbershop_id,
            "barbershop_name": attached_barbershop_name,
        })


class CheckPhoneView(generics.GenericAPIView):
    serializer_class = PhoneSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        exists = User.objects.filter(phone=phone).exists()
        return Response({"exists": exists})


@extend_schema(exclude=True)
class UserAddressViewSet(viewsets.ModelViewSet):
    serializer_class = UserAddressSerializer
    permission_classes = [permissions.IsAuthenticated]
    # Safe default queryset for schema generation
    queryset = UserAddress.objects.none()

    def get_queryset(self):
        # Swagger/spectacular introspection sırasında anon kullanıcı olabilir
        if getattr(self, "swagger_fake_view", False):  # type: ignore[attr-defined]
            return UserAddress.objects.none()
        return UserAddress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        if serializer.validated_data.get("is_default"):
            UserAddress.objects.filter(user=self.request.user, is_default=True).update(is_default=False)
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.is_default:
            UserAddress.objects.filter(user=self.request.user).exclude(pk=instance.pk).update(is_default=False)


"""Favorites yönetimini kullanıcı profiline taşıdık; ayrı endpoint gerekli değil"""


@extend_schema(exclude=True)
class BarbershopStatsView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BarbershopStatsSerializer

    @extend_schema(responses=BarbershopStatsSerializer)
    def get(self, request, barbershop_id):
        favorites_count = (
            Barbershop.objects.filter(id=barbershop_id).values_list('favorites_count', flat=True).first()
            or 0
        )
        # Toplam görüntülenme: ViewEvent sayısı, Unique: farklı kullanıcı sayısı
        views_qs = ViewEvent.objects.filter(barbershop_id=barbershop_id)
        views_count = views_qs.count()
        unique_views_count = views_qs.values('user').distinct().count()
        
        return Response({'favorites_count': favorites_count, 'views_count': views_count, 'unique_views_count': unique_views_count})


