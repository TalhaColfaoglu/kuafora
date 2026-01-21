from __future__ import annotations

import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)

env_file_name = ".env.prod" if os.getenv("DJANGO_ENV") == "production" else ".env"
environ.Env.read_env(env_file=os.path.join(BASE_DIR, env_file_name))


# DEBUG must be controlled via env; never force-enable in prod
DEBUG = env("DEBUG", default=False)
SECRET_KEY = env("SECRET_KEY", default="change-me")
# Required for encrypting sensitive fields (e.g., phone numbers) at rest.
# Must be a Fernet key (urlsafe base64-encoded 32-byte key).
PHONE_ENCRYPTION_KEY = env("PHONE_ENCRYPTION_KEY", default="")
# Extend ALLOWED_HOSTS with safe defaults to avoid DisallowedHost in EC2 and container
_allowed = set(env.list("ALLOWED_HOSTS", default=[]))
_allowed.update({"*", "0.0.0.0", "localhost", "127.0.0.1", ".compute.amazonaws.com"})
ALLOWED_HOSTS = list(_allowed)

# Proxy & security headers (for correct scheme/host behind Nginx)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# CORS settings for Flutter frontend and docs
CORS_ALLOWED_ORIGINS = [
    "http://ec2-3-79-28-13.eu-central-1.compute.amazonaws.com",
    "http://3.79.28.13",
    "https://api.kuafora.com",
    "https://api-dev.kuafora.com",
    "https://ec2-3-79-28-13.eu-central-1.compute.amazonaws.com",
]
CORS_ALLOW_CREDENTIALS = True
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

# CSRF settings
CSRF_TRUSTED_ORIGINS = [
    "http://ec2-3-79-28-13.eu-central-1.compute.amazonaws.com",
    "http://3.79.28-13.eu-central-1.compute.amazonaws.com".replace("-13.eu", ".eu"),  # safety
    "http://3.79.28.13",
    "https://api.kuafora.com",
    "https://api-dev.kuafora.com",
    "https://ec2-3-79-28-13.eu-central-1.compute.amazonaws.com",
]

INSTALLED_APPS = [
    "unfold",
    # "unfold.contrib.filters",
    # "unfold.contrib.forms",
    # "unfold.contrib.inlines",
    # "unfold.contrib.import_export",
    # "unfold.contrib.guardians",
    # "unfold.contrib.simple_history",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "django_filters",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "storages",  # AWS S3 Storage
    # Local apps
    "app.core",
    "app.users",
    "app.barbers",
    "app.uploads",
    "app.appointments",
    "app.campaigns",
    "app.chat",
    "app.notifications",
    "app.subscriptions",
    "app.search",
    "app.support",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "app.core.middleware.RequestSizeLimitMiddleware",  # Request size limiting
    "app.core.middleware.AuditLoggingMiddleware",  # Security audit logging
    "app.core.middleware.IPWhitelistMiddleware",  # Optional IP whitelist for admin
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "app.core.middleware.SecurityHeadersMiddleware",  # Additional security headers
]

# Security Headers - Production'da zorunlu
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
else:
    # Development'ta daha esnek ayarlar
    SECURE_SSL_REDIRECT = False
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'SAMEORIGIN'

ROOT_URLCONF = "config.urls"

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.templatetags.static import static

UNFOLD = {
    "SITE_TITLE": "Kuafora Yönetim",
    "SITE_HEADER": "Kuafora Admin",
    "SITE_URL": "https://kuafora.com",
    "SITE_ICON": {
        "light": lambda request: static("images/logo-icon.png"),  # light mode
        "dark": lambda request: static("images/logo-icon-dark.png"),  # dark mode
    },
    # "SITE_LOGO": {
    #     "light": lambda request: static("images/logo.svg"),
    #     "dark": lambda request: static("images/logo-dark.svg"),
    # },
    "THEME": "dark",  # Force dark mode or "light"
    "STYLES": [
        lambda request: static("css/admin.css"),
    ],
    "COLORS": {
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "200": "221 214 254",
            "300": "196 181 253",
            "400": "167 139 250",
            "500": "139 92 246",
            "600": "124 58 237",
            "700": "109 40 217",
            "800": "91 33 182",
            "900": "76 29 149",
            "950": "46 16 101",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": _("Rehber"),
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": _("Admin Rehberi (Nasıl kullanılır?)"),
                        "icon": "help",
                        "link": reverse_lazy("admin-help"),
                    },
                ],
            },
            {
                "title": _("Yönetim"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Kullanıcılar"),
                        "icon": "people",
                        "link": reverse_lazy("admin:users_user_changelist"),
                    },
                    {
                        "title": _("Gruplar"),
                        "icon": "groups",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                ],
            },
            {
                "title": _("Abonelik & Finans"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Abonelikler"),
                        "icon": "card_membership",
                        "link": reverse_lazy("admin:subscriptions_subscription_changelist"),
                    },
                    {
                        "title": _("Planlar"),
                        "icon": "view_agenda",
                        "link": reverse_lazy("admin:subscriptions_subscriptionplan_changelist"),
                    },
                    {
                        "title": _("Kuponlar"),
                        "icon": "confirmation_number",
                        "link": reverse_lazy("admin:subscriptions_coupon_changelist"),
                    },
                ],
            },
            {
                "title": _("İşletmeler"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Kuaför Salonları"),
                        "icon": "store",
                        "link": reverse_lazy("admin:barbers_barbershop_changelist"),
                    },
                    {
                        "title": _("Personeller"),
                        "icon": "badge",
                        "link": reverse_lazy("admin:barbers_staff_changelist"),
                    },
                    {
                        "title": _("Hizmetler"),
                        "icon": "content_cut",
                        "link": reverse_lazy("admin:barbers_service_changelist"),
                    },
                ],
            },
            {
                "title": _("Operasyon"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Randevular"),
                        "icon": "calendar_today",
                        "link": reverse_lazy("admin:appointments_appointment_changelist"),
                    },
                    {
                        "title": _("Kampanyalar"),
                        "icon": "campaign",
                        "link": reverse_lazy("admin:campaigns_campaign_changelist"),
                    },
                ],
            },
            {
                "title": _("İletişim & İçerik"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Mesajlar"),
                        "icon": "chat",
                        "link": reverse_lazy("admin:chat_chatroom_changelist"),
                    },
                    {
                        "title": _("Yorumlar"),
                        "icon": "reviews",
                        "link": reverse_lazy("admin:barbers_review_changelist"),
                    },
                    {
                        "title": _("Bildirimler"),
                        "icon": "notifications",
                        "link": reverse_lazy("admin:notifications_notification_changelist"),
                    },
                    {
                        "title": _("Destek Talepleri"),
                        "icon": "support_agent",
                        "link": reverse_lazy("admin:support_supportrequest_changelist"),
                    },
                ],
            },
            {
                "title": _("Sistem"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Yüklenen Görseller"),
                        "icon": "image",
                        "link": reverse_lazy("admin:uploads_uploadedimage_changelist"),
                    },
                ],
            },
        ],
    },
}

# Using Unfold templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="makas"),
        "USER": env("POSTGRES_USER", default="makas"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="makas"),
        "HOST": env("POSTGRES_HOST", default="db"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        # Security: Connection options
        "OPTIONS": {
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000",  # 30 second query timeout
        },
        # Security: Connection pooling
        "CONN_MAX_AGE": 600,  # 10 minutes
    }
}

# Optional: IP whitelist for admin panel (set in production .env)
# Format: ADMIN_IP_WHITELIST=1.2.3.4,5.6.7.8
ADMIN_IP_WHITELIST = env.list("ADMIN_IP_WHITELIST", default=[])

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "tr-tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

# APPEND_SLASH=False to prevent POST redirect issues
APPEND_SLASH = False

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="kuafora-media")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="eu-central-1")
AWS_S3_CUSTOM_DOMAIN = "d1uiu5mb5i1uph.cloudfront.net"
AWS_DEFAULT_ACL = None
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}

# Use S3 for media files only if AWS credentials are configured
# Fall back to local storage for dev environments without AWS access
if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"
else:
    # Local file storage fallback for dev
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
    MEDIA_URL = "/media/"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "app.users.authentication.JWTAuthenticationWithEmailGate",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    # Abuse protection (second layer after Nginx): scope-based throttling
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        # Auth endpoints - stricter limits to prevent brute force
        "auth_login": "5/min",  # Reduced from 10/min
        "auth_register": "3/min",  # Reduced from 6/min
        "auth_check_email": "10/min",  # Reduced from 12/min
        "auth_forgot_password": "3/min",  # Reduced from 5/min
        "auth_verify_email": "5/min",
        # Support / feedback
        "support_create": "6/min",
        # General API rate limit
        "default": "1000/hour",
    },
    # Security: Don't expose API structure in error messages
    "EXCEPTION_HANDLER": "app.core.exceptions.custom_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Makas API",
    "DESCRIPTION": "Kuaför randevu uygulaması için REST API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Docs içinde doğru base url görünsün
    "SERVERS": [
        {"url": "https://api.kuafora.com", "description": "Production"},
    ],
}

# -----------------------------------------------------------------------------
# Email (SMTP) - used for email verification and password reset
# -----------------------------------------------------------------------------
# If SMTP vars are not configured, fall back to console backend in DEBUG.
PUBLIC_API_ORIGIN = env("PUBLIC_API_ORIGIN", default="").strip()  # e.g. https://api.kuafora.com

EMAIL_HOST = env("EMAIL_HOST", default="").strip()
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="").strip()
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="").strip()
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@kuafora.com").strip()

if EMAIL_HOST and EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    # Dev-safe fallback (shows emails in logs/console)
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.dummy.EmailBackend"

from datetime import timedelta

SIMPLE_JWT = {
    # Kullanıcı çıkış yapana kadar pratikte oturum açık kalsın
    # Güvenlik politikasına göre daha kısa ayarlamak istenirse buradan güncellenebilir
    "ACCESS_TOKEN_LIFETIME": timedelta(days=365),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=3650),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    # Security: Token signing algorithm
    "ALGORITHM": "HS256",
    # Security: Token verification
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    # Security: Require HTTPS in production for token transmission
    "AUTH_COOKIE_SECURE": not DEBUG,
    "AUTH_COOKIE_HTTPONLY": True,
    "AUTH_COOKIE_SAMESITE": "Lax",
}

AUTHENTICATION_BACKENDS = (
    "app.users.auth_backend.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
)

# Session Security
SESSION_COOKIE_SECURE = not DEBUG  # HTTPS only in production
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
SESSION_COOKIE_AGE = 86400 * 30  # 30 days
SESSION_SAVE_EVERY_REQUEST = False  # Only save on changes
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Persist across browser restarts

# CSRF Security
CSRF_COOKIE_SECURE = not DEBUG  # HTTPS only in production
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_FAILURE_VIEW = 'app.core.views.csrf_failure'  # Custom CSRF failure view

# File Upload Security
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000  # Prevent DoS via form fields

# Security: Prevent information disclosure
SECRET_KEY_FALLBACKS = []  # Don't use fallback keys
ALLOWED_INCLUDE_ROOTS = []  # Prevent SSI attacks


