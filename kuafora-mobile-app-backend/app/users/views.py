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
from django.utils import timezone
from django.http import HttpResponse
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils.crypto import salted_hmac
import secrets

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    EmailSerializer,
    VerifyEmailCodeSerializer,
    PhoneSerializer,
    ResetPasswordSerializer,
    UserAddressSerializer,
    LogoutSerializer,
    BarbershopStatsSerializer,
    
)
from .models import UserAddress
from .models import EmailVerificationCode
from app.barbers.models import Barbershop, LastViewed, ViewEvent

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    throttle_scope = "auth_register"

    def perform_create(self, serializer):
        user = serializer.save()
        # Always mark as unverified for first-time verification.
        if getattr(user, "email_verified", False):
            user.email_verified = False
            user.email_verified_at = None
            user.save(update_fields=["email_verified", "email_verified_at", "updated_at"])
        # Send OTP code (best-effort)
        try:
            _send_email_verification_code(user, request=self.request)
        except Exception as e:
            print(f"[EMAIL][VERIFY_CODE][REGISTER] failed: {e}")


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as exc:
            msgs = exc.detail if hasattr(exc, "detail") else exc.args

            # If serializer raised structured error, pass it through.
            if isinstance(msgs, dict) and ("detail" in msgs or "reason" in msgs):
                def _first_str(v) -> str:
                    # DRF often wraps values as [ErrorDetail(...)]
                    if isinstance(v, list) and v:
                        return str(v[0])
                    return str(v or "")

                reason = _first_str(msgs.get("reason", ""))
                detail = _first_str(msgs.get("detail", ""))
                # Map known reasons to proper status codes
                if reason == "banned":
                    return Response({"detail": detail, "reason": reason}, status=status.HTTP_403_FORBIDDEN)
                if reason == "email_not_verified":
                    return Response({"detail": detail, "reason": reason}, status=status.HTTP_403_FORBIDDEN)
                if reason in {"wrong_password", "user_not_found", "invalid_credentials"}:
                    return Response({"detail": detail, "reason": reason}, status=status.HTTP_401_UNAUTHORIZED)
                if reason == "missing_fields":
                    return Response({"detail": detail, "reason": reason}, status=status.HTTP_400_BAD_REQUEST)
                # Default fallback for structured errors
                return Response({"detail": detail, "reason": reason}, status=status.HTTP_400_BAD_REQUEST)

            # Legacy fallback: turn any validation error into a plain text detail
            text = ""
            if isinstance(msgs, dict):
                for v in msgs.values():
                    if isinstance(v, list) and v:
                        text = str(v[0])
                        break
                    if isinstance(v, str) and v:
                        text = v
                        break
            elif isinstance(msgs, list) and msgs:
                text = str(msgs[0])
            else:
                text = "Bad request"

            if "Invalid email or password" in text:
                return Response({"detail": text, "reason": "invalid_credentials"}, status=status.HTTP_401_UNAUTHORIZED)
            return Response({"detail": text or "Bad request"}, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "email_verified": bool(getattr(user, "email_verified", False)),
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
            # Force a unique filename to avoid collisions/caching issues (CloudFront/S3 key reuse)
            import os
            from uuid import uuid4
            ext = os.path.splitext(getattr(image_file, "name", "") or "")[1].lower()
            if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                ext = ".jpg"
            image_file.name = f"profile_{uuid4().hex}{ext}"
            
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
    throttle_scope = "auth_verify_email"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = (serializer.validated_data["email"] or "").strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        # Always return a generic response to prevent email enumeration
        generic = {"detail": "If the email exists, a verification code will be sent."}
        if not user:
            return Response(generic)

        # If already verified, we can still return generic (no-op)
        if getattr(user, "email_verified", False):
            return Response(generic)

        try:
            _send_email_verification_code(user, request=request)
        except Exception as e:
            print(f"[EMAIL][VERIFY_CODE] send_mail failed: {e}")

        return Response(generic)


class VerifyEmailCodeView(generics.GenericAPIView):
    """Verify email with OTP code."""

    serializer_class = VerifyEmailCodeSerializer
    throttle_scope = "auth_verify_email"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = (serializer.validated_data["email"] or "").strip().lower()
        code = (serializer.validated_data["code"] or "").strip()

        # Generic invalid response (do not reveal whether email exists)
        invalid = {"detail": "Kod hatalı veya süresi dolmuş.", "reason": "invalid_or_expired"}

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response(invalid, status=status.HTTP_400_BAD_REQUEST)

        if getattr(user, "email_verified", False):
            return Response({"detail": "E-posta zaten doğrulanmış."})

        # Latest active code
        ev = (
            EmailVerificationCode.objects.filter(user=user, consumed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if not ev or ev.is_expired:
            return Response(invalid, status=status.HTTP_400_BAD_REQUEST)

        # Basic attempt limiting
        if ev.attempts >= 5:
            ev.consumed_at = timezone.now()
            ev.save(update_fields=["consumed_at"])
            return Response(invalid, status=status.HTTP_400_BAD_REQUEST)

        expected = _hash_email_code(user_id=str(user.pk), code=code)
        if not secrets.compare_digest(ev.code_hash, expected):
            ev.attempts += 1
            ev.save(update_fields=["attempts"])
            return Response(invalid, status=status.HTTP_400_BAD_REQUEST)

        # Success
        ev.consumed_at = timezone.now()
        ev.save(update_fields=["consumed_at"])
        user.email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified", "email_verified_at", "updated_at"])
        return Response({"detail": "E-posta doğrulandı."})


def _hash_email_code(*, user_id: str, code: str) -> str:
    # Use SECRET_KEY via salted_hmac internally; no need to import settings here.
    return salted_hmac("email-verify-otp", f"{user_id}:{code}").hexdigest()


def _send_email_verification_code(user, request=None) -> None:
    # Delete previous active codes
    EmailVerificationCode.objects.filter(user=user, consumed_at__isnull=True).delete()

    code = f"{secrets.randbelow(1000000):06d}"
    code_hash = _hash_email_code(user_id=str(user.pk), code=code)
    expires_at = timezone.now() + timezone.timedelta(minutes=10)
    EmailVerificationCode.objects.create(user=user, code_hash=code_hash, expires_at=expires_at)

    subject = "Kuafora • E-posta Doğrulama Kodu"
    body = (
        "Merhaba,\n\n"
        "Kuafora hesabınızı doğrulamak için doğrulama kodunuz:\n\n"
        f"{code}\n\n"
        "Kod 10 dakika içinde geçerliliğini yitirir.\n"
        "Bu isteği siz yapmadıysanız bu e-postayı yok sayabilirsiniz.\n\n"
        "Kuafora"
    )
    send_mail(
        subject,
        body,
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        [user.email],
        fail_silently=False,
    )


class ConfirmEmailView(generics.GenericAPIView):
    """Link target used in verification email.
    GET /api/auth/verify-email/confirm/?uid=...&token=..."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        uid = request.query_params.get("uid") or ""
        token = request.query_params.get("token") or ""

        def _html(title: str, message: str) -> HttpResponse:
            return HttpResponse(
                f"""<!doctype html>
<html lang="tr">
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>{title}</title>
    <style>
      body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background:#fff;margin:0;padding:40px;}}
      .card{{max-width:520px;margin:0 auto;border:1px solid #eee;border-radius:16px;padding:24px;}}
      h1{{font-size:22px;margin:0 0 8px;}}
      p{{color:#444;line-height:1.5;margin:0;}}
      .ok{{color:#059669;font-weight:700;}}
      .bad{{color:#b91c1c;font-weight:700;}}
    </style>
  </head>
  <body>
    <div class="card">
      <h1>{title}</h1>
      <p>{message}</p>
    </div>
  </body>
</html>""",
                content_type="text/html; charset=utf-8",
            )

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except Exception:
            return _html("Geçersiz bağlantı", "<span class='bad'>Bağlantı geçersiz.</span>")

        if not default_token_generator.check_token(user, token):
            return _html("Bağlantı süresi doldu", "<span class='bad'>Doğrulama bağlantısı geçersiz veya süresi dolmuş.</span>")

        if not getattr(user, "email_verified", False):
            user.email_verified = True
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified", "email_verified_at", "updated_at"])

        return _html("E-posta doğrulandı", "<span class='ok'>E-postanız doğrulandı.</span> Artık uygulamaya geri dönebilirsiniz.")


class ForgotPasswordView(generics.GenericAPIView):
    serializer_class = EmailSerializer
    throttle_scope = "auth_forgot_password"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = (serializer.validated_data["email"] or "").strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        # Always generic response to prevent email enumeration
        generic = {"detail": "If the email exists, a reset mail will be sent."}
        if not user:
            return Response(generic)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        api_origin = getattr(settings, "PUBLIC_API_ORIGIN", "").rstrip("/")
        if not api_origin:
            api_origin = (request.build_absolute_uri("/") or "").rstrip("/")

        confirm_url = f"{api_origin}/api/auth/reset-password/confirm/?uid={uid}&token={token}"

        subject = "Kuafora • Şifre Sıfırlama"
        body = (
            "Merhaba,\n\n"
            "Kuafora hesabınızın şifresini sıfırlamak için aşağıdaki bağlantıya tıklayın:\n\n"
            f"{confirm_url}\n\n"
            "Bu isteği siz yapmadıysanız bu e-postayı yok sayabilirsiniz.\n\n"
            "Kuafora"
        )

        try:
            send_mail(
                subject,
                body,
                getattr(settings, "DEFAULT_FROM_EMAIL", None),
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"[EMAIL][RESET] send_mail failed: {e}")

        return Response(generic)


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


@method_decorator(csrf_exempt, name="dispatch")
class ResetPasswordConfirmView(generics.GenericAPIView):
    """HTML reset page.
    GET renders the form, POST sets the new password after validating uid/token."""

    permission_classes = [permissions.AllowAny]

    def _render(self, title: str, message: str, uid: str = "", token: str = "", is_error: bool = False) -> HttpResponse:
        status_cls = "bad" if is_error else "ok"
        return HttpResponse(
            f"""<!doctype html>
<html lang="tr">
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>{title}</title>
    <style>
      body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background:#fff;margin:0;padding:40px;}}
      .card{{max-width:560px;margin:0 auto;border:1px solid #eee;border-radius:18px;padding:24px;}}
      h1{{font-size:22px;margin:0 0 10px;}}
      p{{color:#444;line-height:1.55;margin:0 0 14px;}}
      label{{display:block;margin:10px 0 6px;color:#111827;font-weight:700;font-size:13px;}}
      input{{width:100%;padding:12px 14px;border:1px solid #e5e7eb;border-radius:12px;font-size:14px;}}
      .row{{display:flex;gap:12px;}}
      .btn{{margin-top:14px;width:100%;padding:12px 14px;border:0;border-radius:12px;background:#111827;color:#fff;font-weight:800;font-size:14px;cursor:pointer;}}
      .hint{{font-size:12px;color:#6b7280;margin-top:10px;}}
      .ok{{color:#059669;font-weight:800;}}
      .bad{{color:#b91c1c;font-weight:800;}}
      .msg{{margin:10px 0 14px;}}
      .pill{{display:inline-block;padding:6px 10px;border-radius:999px;background:#f3f4f6;color:#111827;font-weight:700;font-size:12px;}}
    </style>
  </head>
  <body>
    <div class="card">
      <h1>{title}</h1>
      <div class="msg"><span class="{status_cls}">{message}</span></div>
      <div class="pill">Kuafora</div>
      <form method="post" style="margin-top:14px;">
        <input type="hidden" name="uid" value="{uid}"/>
        <input type="hidden" name="token" value="{token}"/>
        <label>Yeni şifre</label>
        <input type="password" name="password1" placeholder="En az 8 karakter, harf + rakam" required minlength="8"/>
        <label>Yeni şifre (tekrar)</label>
        <input type="password" name="password2" placeholder="Tekrar girin" required minlength="8"/>
        <button class="btn" type="submit">Şifreyi Güncelle</button>
        <div class="hint">İpucu: Çok yaygın şifreler kabul edilmeyebilir. Harf + rakam kullanın.</div>
      </form>
    </div>
  </body>
</html>""",
            content_type="text/html; charset=utf-8",
        )

    def get(self, request, *args, **kwargs):
        uid = request.query_params.get("uid") or ""
        token = request.query_params.get("token") or ""
        if not uid or not token:
            return self._render("Geçersiz bağlantı", "Bağlantı eksik veya hatalı.", is_error=True)
        return self._render("Şifre Sıfırlama", "Yeni şifrenizi belirleyin.", uid=uid, token=token, is_error=False)

    def post(self, request, *args, **kwargs):
        uid = (request.POST.get("uid") or "").strip()
        token = (request.POST.get("token") or "").strip()
        p1 = request.POST.get("password1") or ""
        p2 = request.POST.get("password2") or ""

        if not uid or not token:
            return self._render("Geçersiz bağlantı", "Bağlantı eksik veya hatalı.", is_error=True)
        if not p1 or len(p1) < 8:
            return self._render("Şifre geçersiz", "Şifre en az 8 karakter olmalı.", uid=uid, token=token, is_error=True)
        if p1 != p2:
            return self._render("Şifreler uyuşmuyor", "İki şifre aynı olmalı.", uid=uid, token=token, is_error=True)

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except Exception:
            return self._render("Geçersiz bağlantı", "Bağlantı geçersiz.", is_error=True)

        if not default_token_generator.check_token(user, token):
            return self._render("Bağlantı süresi doldu", "Bağlantı geçersiz veya süresi dolmuş.", is_error=True)

        # Validate password using Django validators
        try:
            from django.contrib.auth.password_validation import validate_password
            validate_password(p1, user=user)
        except Exception as e:
            # e may be ValidationError with messages
            msg = "Şifre çok zayıf. Lütfen daha güçlü bir şifre deneyin."
            try:
                msgs = getattr(e, "messages", None)
                if msgs:
                    msg = " ".join([str(m) for m in msgs])
            except Exception:
                pass
            return self._render("Şifre kabul edilmedi", msg, uid=uid, token=token, is_error=True)

        user.set_password(p1)
        user.save()
        return self._render("Şifre güncellendi", "Şifreniz güncellendi. Uygulamaya geri dönüp giriş yapabilirsiniz.", is_error=False)


class CheckEmailView(generics.GenericAPIView):
    serializer_class = EmailSerializer
    throttle_scope = "auth_check_email"

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


