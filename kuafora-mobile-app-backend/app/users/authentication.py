from __future__ import annotations

from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTAuthenticationWithEmailGate(JWTAuthentication):
    """
    Email verification policy:
    - Login itself is allowed even if email is not verified.
    - For accounts created "from now on", we set user.requires_email_verification=True at registration.
    - If such a user is authenticated but email_verified=False, we block most authenticated endpoints
      until they verify their email.
    - Legacy accounts have requires_email_verification=False, so they are NOT blocked.
    """

    # Allow verification-related endpoints so the user can complete verification.
    # Allow forgot-password and reset-password so unverified users can reset password (no "e-posta doğrulanamadı" 403).
    _ALLOWED_PREFIXES = (
        "/api/auth/verify-email/",
        "/api/auth/verify-email/code/",
        "/api/auth/verify-email/confirm/",
        "/api/auth/forgot-password/",
        "/api/auth/reset-password/",
        "/api/auth/reset-password-by-code/",
        "/api/auth/reset-password/confirm/",
    )
    # Allow reading own profile to show status + enable UX.
    _ALLOWED_EXACT = (
        "/api/auth/me/",
        "/api/auth/me",
        "/api/auth/users/me/",
    )

    def authenticate(self, request):
        out = super().authenticate(request)
        if out is None:
            return None

        user, validated_token = out
        try:
            requires = bool(getattr(user, "requires_email_verification", False))
            verified = bool(getattr(user, "email_verified", False))
        except Exception:
            return out

        if requires and not verified:
            path = (getattr(request, "path", "") or "").rstrip() or ""
            if path in self._ALLOWED_EXACT:
                return out
            if any(path.startswith(p.rstrip("/")) for p in self._ALLOWED_PREFIXES):
                return out
            raise PermissionDenied(detail={"detail": "E-posta doğrulaması gerekli.", "reason": "email_verification_required"})

        return out


