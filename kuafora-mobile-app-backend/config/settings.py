from __future__ import annotations

import os
import logging
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
    "app.core.middleware.ETagMiddleware",  # ETag support for conditional requests
    "app.core.middleware.SecurityHeadersMiddleware",  # Additional security headers
]

# Security Headers - Production'da zorunlu
# NOT: SECURE_SSL_REDIRECT kapalı çünkü Nginx zaten HTTPS redirect yapıyor.
# Django'nun redirect yapması, Nginx'in backend'e HTTP ile bağlanmasını engelliyor.
if not DEBUG:
    SECURE_SSL_REDIRECT = False  # Nginx handles HTTPS redirect
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
                "title": _("Dashboard & Rehber"),
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": _("📊 Dashboard"),
                        "icon": "dashboard",
                        "link": reverse_lazy("admin-dashboard"),
                    },
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
        # Performance: Connection pooling - reuse connections for 10 minutes
        "CONN_MAX_AGE": 600,  # 10 minutes
    }
}

# Redis Cache Configuration - High performance caching
REDIS_URL = env("REDIS_URL", default="redis://redis:6379/1")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",  # Compress large values
            "IGNORE_EXCEPTIONS": True,  # Don't crash if Redis is down
            # Fix for django-redis 5.4.0 compatibility with newer redis package
            # Override connection pool kwargs to avoid parser class issues
            "CONNECTION_POOL_KWARGS": {
                "decode_responses": False,  # Don't decode responses (binary mode)
            },
        },
        "KEY_PREFIX": "kuafora_backend",
        "TIMEOUT": 300,  # Default cache timeout: 5 minutes
    }
}

# Session storage - Use database for sessions (Redis cache for API responses only)
# Note: Redis sessions can cause 500 errors if Redis is unavailable
# Using database sessions for reliability, Redis cache for API performance
SESSION_ENGINE = "django.contrib.sessions.backends.db"  # Database sessions (more reliable)
# SESSION_ENGINE = "django.contrib.sessions.backends.cache"  # Redis sessions (faster but requires Redis)
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = False  # Only save when session is modified

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
    "CacheControl": "max-age=31536000",  # 1 yıl cache - CloudFront ile optimize edilmiş
    "ContentDisposition": "inline",  # Tarayıcıda açılabilir
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
    # Pagination - Limit results to prevent large responses
    "DEFAULT_PAGINATION_CLASS": "app.core.pagination.StandardPageNumberPagination",
    "PAGE_SIZE": 20,  # Default page size
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

# -----------------------------------------------------------------------------
# AWS CloudWatch Logs Configuration
# -----------------------------------------------------------------------------
AWS_CLOUDWATCH_ENABLED = env.bool('AWS_CLOUDWATCH_ENABLED', default=False)
AWS_CLOUDWATCH_LOG_GROUP_NAME = env('AWS_CLOUDWATCH_LOG_GROUP_NAME', default='kuafora-backend')
AWS_CLOUDWATCH_STREAM_NAME = env('AWS_CLOUDWATCH_STREAM_NAME', default='api')
AWS_CLOUDWATCH_REGION_NAME = env('AWS_CLOUDWATCH_REGION_NAME', default='eu-central-1')
# CloudWatch Log Retention (gün cinsinden) - AWS Console'da da ayarlanmalı
# 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653
AWS_CLOUDWATCH_LOG_RETENTION_DAYS = env.int('AWS_CLOUDWATCH_LOG_RETENTION_DAYS', default=14)

# CloudWatch için AWS credentials
cloudwatch_logs_client = None
cloudwatch_handler_config = None

if AWS_CLOUDWATCH_ENABLED:
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        AWS_ACCESS_KEY_ID_CW = env('AWS_ACCESS_KEY_ID', default=None)
        AWS_SECRET_ACCESS_KEY_CW = env('AWS_SECRET_ACCESS_KEY', default=None)
        
        if AWS_ACCESS_KEY_ID_CW and AWS_SECRET_ACCESS_KEY_CW:
            try:
                cloudwatch_logs_client = boto3.client(
                    'logs',
                    region_name=AWS_CLOUDWATCH_REGION_NAME,
                    aws_access_key_id=AWS_ACCESS_KEY_ID_CW,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY_CW
                )
                # Log group'un var olup olmadığını kontrol et (oluşturma, sadece kontrol)
                try:
                    cloudwatch_logs_client.describe_log_groups(logGroupNamePrefix=AWS_CLOUDWATCH_LOG_GROUP_NAME)
                except ClientError as e:
                    # İzin hatası varsa, log group'u manuel oluşturulması gerektiğini belirt
                    if e.response['Error']['Code'] == 'AccessDeniedException':
                        print(f"⚠️  CloudWatch: IAM izinleri eksik. Log group'u manuel oluşturun veya IAM izinlerini ekleyin.")
                        print(f"⚠️  CloudWatch devre dışı bırakılıyor. IAM izinleri eklendikten sonra tekrar aktif edin.")
                        AWS_CLOUDWATCH_ENABLED = False
                        cloudwatch_logs_client = None
                    else:
                        raise
                
                # Handler config oluştur (log group oluşturmayı watchtower'a bırakma)
                if cloudwatch_logs_client:
                    # Watchtower'ın log group oluşturmasını engellemek için önce var mı kontrol et
                    try:
                        # Log group'un var olup olmadığını kontrol et
                        response = cloudwatch_logs_client.describe_log_groups(
                            logGroupNamePrefix=AWS_CLOUDWATCH_LOG_GROUP_NAME,
                            limit=1
                        )
                        log_group_exists = any(
                            lg['logGroupName'] == AWS_CLOUDWATCH_LOG_GROUP_NAME 
                            for lg in response.get('logGroups', [])
                        )
                        
                        if not log_group_exists:
                            # Log group yoksa oluşturmayı dene (izin varsa)
                            try:
                                cloudwatch_logs_client.create_log_group(
                                    logGroupName=AWS_CLOUDWATCH_LOG_GROUP_NAME,
                                    # Retention ayarını da ekle (maliyet optimizasyonu)
                                    retentionInDays=AWS_CLOUDWATCH_LOG_RETENTION_DAYS
                                )
                                print(f"✅ CloudWatch log group oluşturuldu: {AWS_CLOUDWATCH_LOG_GROUP_NAME} (retention: {AWS_CLOUDWATCH_LOG_RETENTION_DAYS} gün)")
                            except ClientError as e:
                                if e.response['Error']['Code'] == 'AccessDeniedException':
                                    print(f"⚠️  CloudWatch: Log group oluşturma izni yok. Log group'u manuel oluşturun: {AWS_CLOUDWATCH_LOG_GROUP_NAME}")
                                    print(f"⚠️  CloudWatch devre dışı bırakılıyor. IAM izinleri eklendikten sonra tekrar aktif edin.")
                                    AWS_CLOUDWATCH_ENABLED = False
                                    cloudwatch_logs_client = None
                                else:
                                    raise
                        else:
                            # Log group varsa retention ayarını güncelle (maliyet optimizasyonu)
                            try:
                                cloudwatch_logs_client.put_retention_policy(
                                    logGroupName=AWS_CLOUDWATCH_LOG_GROUP_NAME,
                                    retentionInDays=AWS_CLOUDWATCH_LOG_RETENTION_DAYS
                                )
                                print(f"✅ CloudWatch log retention güncellendi: {AWS_CLOUDWATCH_LOG_RETENTION_DAYS} gün")
                            except ClientError as e:
                                if e.response['Error']['Code'] == 'AccessDeniedException':
                                    print(f"⚠️  CloudWatch: Retention policy güncelleme izni yok. AWS Console'dan manuel ayarlayın.")
                                # Retention hatası kritik değil, devam et
                    except ClientError as e:
                        if e.response['Error']['Code'] == 'AccessDeniedException':
                            print(f"⚠️  CloudWatch: IAM izinleri eksik. Log group'u manuel oluşturun veya IAM izinlerini ekleyin.")
                            print(f"⚠️  CloudWatch devre dışı bırakılıyor.")
                            AWS_CLOUDWATCH_ENABLED = False
                            cloudwatch_logs_client = None
                        else:
                            raise
                    
                    # Handler config oluştur (sadece client varsa)
                    if cloudwatch_logs_client:
                        cloudwatch_handler_config = {
                            'class': 'watchtower.CloudWatchLogHandler',
                            'log_group': AWS_CLOUDWATCH_LOG_GROUP_NAME,
                            'stream_name': AWS_CLOUDWATCH_STREAM_NAME,
                            'use_queues': True,
                            'send_interval': 5,
                            'max_batch_size': 100,
                            'boto3_client': cloudwatch_logs_client,
                            'formatter': 'json',
                        }
                        print(f"✅ CloudWatch yapılandırması başarılı: {AWS_CLOUDWATCH_LOG_GROUP_NAME}/{AWS_CLOUDWATCH_STREAM_NAME}")
            except Exception as e:
                print(f"⚠️  CloudWatch client oluşturma hatası: {e}")
                print(f"⚠️  CloudWatch devre dışı bırakılıyor.")
                AWS_CLOUDWATCH_ENABLED = False
                cloudwatch_logs_client = None
        else:
            print("⚠️  CloudWatch için AWS credentials bulunamadı, CloudWatch devre dışı")
            AWS_CLOUDWATCH_ENABLED = False
    except ImportError:
        print("⚠️  boto3 veya watchtower yüklü değil, CloudWatch devre dışı")
        AWS_CLOUDWATCH_ENABLED = False
    except Exception as e:
        print(f"⚠️  CloudWatch yapılandırma hatası: {e}")
        AWS_CLOUDWATCH_ENABLED = False

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

# CloudWatch Handler Factory (graceful fail için)
def _create_cloudwatch_handler():
    """CloudWatch handler'ı oluştur, hata olursa NullHandler döndür"""
    # Global değişkenleri kullan
    global cloudwatch_logs_client, AWS_CLOUDWATCH_LOG_GROUP_NAME, AWS_CLOUDWATCH_STREAM_NAME
    
    # Client yoksa NullHandler döndür
    if not cloudwatch_logs_client:
        import logging as logging_module
        return logging_module.NullHandler()
    
    try:
        import watchtower
        handler = watchtower.CloudWatchLogHandler(
            log_group=AWS_CLOUDWATCH_LOG_GROUP_NAME,
            stream_name=AWS_CLOUDWATCH_STREAM_NAME,
            use_queues=True,
            send_interval=5,
            max_batch_size=100,
            boto3_client=cloudwatch_logs_client,
        )
        # CloudWatch'a sadece WARNING ve ERROR seviyesindeki logları gönder (maliyet optimizasyonu)
        handler.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter('{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d}'))
        print(f"✅ CloudWatch handler başarıyla oluşturuldu: {AWS_CLOUDWATCH_LOG_GROUP_NAME}/{AWS_CLOUDWATCH_STREAM_NAME} (sadece WARNING+ seviyesi)")
        return handler
    except Exception as e:
        import logging as logging_module
        print(f"⚠️  CloudWatch handler oluşturulamadı: {e}")
        print(f"⚠️  NullHandler kullanılıyor (CloudWatch devre dışı)")
        return logging_module.NullHandler()

# Logging Configuration with Rotation
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d}',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/logs/django.log',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,  # Keep 5 backup files (total ~50MB)
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/logs/django_errors.log',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,  # Keep 5 backup files
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        # CloudWatch Logs Handler
        # Handler oluşturulurken hata olursa graceful fail yap
        'cloudwatch': {
            '()': 'config.settings._create_cloudwatch_handler',  # Custom factory function
        } if AWS_CLOUDWATCH_ENABLED else {
            'class': 'logging.NullHandler',  # Devre dışıysa hiçbir şey yapma
        },
    },
        'root': {
            'handlers': ['console', 'file'] + (['cloudwatch'] if AWS_CLOUDWATCH_ENABLED else []),
            'level': 'INFO',
        },
    'loggers': {
        'django': {
            # Django logları CloudWatch'a sadece ERROR seviyesinde gider (maliyet optimizasyonu)
            'handlers': ['file', 'error_file', 'console'] + (['cloudwatch'] if AWS_CLOUDWATCH_ENABLED and cloudwatch_logs_client else []),
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['error_file', 'console'] + (['cloudwatch'] if AWS_CLOUDWATCH_ENABLED and cloudwatch_logs_client else []),
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['error_file', 'console'] + (['cloudwatch'] if AWS_CLOUDWATCH_ENABLED and cloudwatch_logs_client else []),
            'level': 'ERROR',
            'propagate': False,
        },
        'app': {
            # CloudWatch handler'ı WARNING seviyesinde filtreliyor (maliyet optimizasyonu)
            # INFO ve DEBUG logları sadece dosya ve console'a gider
            'handlers': ['file', 'console'] + (['cloudwatch'] if AWS_CLOUDWATCH_ENABLED and cloudwatch_logs_client else []),
            'level': 'INFO',  # Dosya ve console için INFO
            'propagate': False,
        },
        # Security audit logs için özel logger
        'app.core.middleware': {
            'handlers': ['file', 'error_file', 'console'] + (['cloudwatch'] if AWS_CLOUDWATCH_ENABLED and cloudwatch_logs_client else []),
            'level': 'WARNING',  # Sadece önemli güvenlik olayları
            'propagate': False,
        },
    },
}


