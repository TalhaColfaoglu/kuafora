from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import generics, permissions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Count
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
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
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as exc:
            # Yanlış kimlik bilgileri için 401 döndür (400 yerine)
            msgs = exc.detail if hasattr(exc, 'detail') else exc.args
            text = ""
            if isinstance(msgs, dict):
                # {'non_field_errors': ['Invalid email or password.']}
                for v in msgs.values():
                    if isinstance(v, list) and v:
                        text = str(v[0])
                        break
            elif isinstance(msgs, list) and msgs:
                text = str(msgs[0])
            else:
                text = "Invalid email or password."
            if "Invalid email or password" in text:
                return Response({"detail": text}, status=status.HTTP_401_UNAUTHORIZED)
            # Alan eksikliği gibi durumlar için standart 400
            return Response({"detail": text or "Bad request"}, status=status.HTTP_400_BAD_REQUEST)

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
            
            # Update user's profile photo
            user = request.user
            
            # Delete old images first
            if user.image:
                try:
                    old_image_path = user.image.path
                    user.image.delete(save=False)
                    print(f"🗑️ Deleted old image: {old_image_path}")
                except Exception as e:
                    print(f"⚠️ Could not delete old image: {e}")
            
            if user.image_thumb:
                try:
                    old_thumb_path = user.image_thumb.path
                    user.image_thumb.delete(save=False)
                    print(f"🗑️ Deleted old thumbnail: {old_thumb_path}")
                except Exception as e:
                    print(f"⚠️ Could not delete old thumbnail: {e}")
            
            # Set new image
            user.image = image_file
            user.save()
            
            # Reload from DB to get the processed image
            user.refresh_from_db()
            
            # Log success info with thumbnail verification
            print(f"✓ User {user.id} profile photo updated successfully")
            print(f"  → Main image: {user.image.url if user.image else 'None'}")
            print(f"  → Thumbnail: {user.image_thumb.url if user.image_thumb else 'NOT CREATED!'}")
            
            # Verify thumbnail was created
            if user.image and not user.image_thumb:
                print(f"❌ ERROR: Thumbnail was not created for user {user.id}")
            
            return Response({
                "detail": "Profile photo updated successfully",
                "image_url": user.image.url if user.image else None,
                "image_thumb_url": user.image_thumb.url if user.image_thumb else None
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
        # Normalize et: küçük harfe çevir, boşlukları kes
        email = (serializer.validated_data.get("email") or "").strip().lower()

        try:
            # Login'deki davranışla uyum: iexact
            exists = User.objects.filter(email__iexact=email).exists()
        except Exception:
            # DB hazır değilse veya geçici hata varsa 500 yerine güvenli yanıt
            return Response({
                "exists": False,
                "is_registered": False,
                "is_staff": False,
                "barbershop_id": None,
                "barbershop_name": None,
            })

        # Ek alanlar: herhangi bir kuaföre bağlı mı?
        try:
            from app.barbers.models import Staff  # type: ignore
        except Exception:  # döngüsel import riskine karşı
            Staff = None  # type: ignore

        is_staff_attached = False
        attached_barbershop_id = None
        attached_barbershop_name = None
        if exists and Staff is not None:
            try:
                qs = Staff.objects.filter(user__email=email).select_related("barbershop")
                if qs.exists():
                    is_staff_attached = True
                    bs = qs.first().barbershop  # type: ignore
                    attached_barbershop_id = getattr(bs, "id", None)
                    attached_barbershop_name = getattr(bs, "name", None)
            except Exception:
                # İlişkisel sorgu hatalarında da güvenli yanıt
                pass

        return Response({
            "exists": exists,
            "is_registered": exists,  # frontend toleransı için
            "is_staff": is_staff_attached,
            "barbershop_id": attached_barbershop_id,
            "barbershop_name": attached_barbershop_name,
        })


class ResolveUserView(generics.GenericAPIView):
    """Resolve user by email for onboarding flows.
    GET /auth/resolve/?email=foo@bar.com -> {exists, user_id, attached_shop_id}
    Legacy alias: /users/resolve/"""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Kullanıcıyı e-posta ile çözümle",
        parameters=[
            OpenApiParameter(
                name="email",
                required=True,
                location=OpenApiParameter.QUERY,
                description="Sorgulanacak e-posta adresi",
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="Kullanıcının kayıtlı olup olmadığı ve bağlı olduğu kuaför bilgisi",
            ),
            400: OpenApiResponse(description="Eksik email parametresi"),
        },
    )
    def get(self, request, *args, **kwargs):
        email = request.query_params.get('email')
        if not email:
            return Response({"detail": "email query param required"}, status=400)
        user = User.objects.filter(email=email).first()
        if not user:
            return Response({
                "exists": False,
                "user_id": None,
                "attached_shop_id": None,
            })
        # Check staff attachment
        from app.barbers.models import Staff  # lazy import
        staff = Staff.objects.filter(user=user).select_related('barbershop').first()
        attached_shop_id = getattr(getattr(staff, 'barbershop', None), 'id', None)
        return Response({
            "exists": True,
            "user_id": user.id,
            "attached_shop_id": attached_shop_id,
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
        # Toplam görüntülenme: ViewEvent sayısı
        views_qs = ViewEvent.objects.filter(barbershop_id=barbershop_id)
        views_count = views_qs.count()
        
        # Unique: user_id veya device_id'ye göre tekil sayım
        # Giriş yapmış kullanıcılar
        unique_users = views_qs.filter(user__isnull=False).values('user').distinct().count()
        # Misafir kullanıcılar (user null, device_id not null)
        unique_devices = views_qs.filter(user__isnull=True, device_id__isnull=False).values('device_id').distinct().count()
        unique_views_count = unique_users + unique_devices
        
        return Response({'favorites_count': favorites_count, 'views_count': views_count, 'unique_views_count': unique_views_count})


