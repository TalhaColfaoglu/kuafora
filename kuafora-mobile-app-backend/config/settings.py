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


DEBUG = True  # Temporarily enable debug to see real errors
SECRET_KEY = env("SECRET_KEY", default="change-me")
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
    "https://ec2-3-79-28-13.eu-central-1.compute.amazonaws.com",
]

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    "unfold.contrib.guardians",
    "unfold.contrib.simple_history",
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
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

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
    }
}

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

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="kuafora-media")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="eu-central-1")
AWS_S3_CUSTOM_DOMAIN = "d1uiu5mb5i1uph.cloudfront.net"
AWS_DEFAULT_ACL = "public-read"
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}

# Use S3 for media files
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
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

from datetime import timedelta

SIMPLE_JWT = {
    # Kullanıcı çıkış yapana kadar pratikte oturum açık kalsın
    # Güvenlik politikasına göre daha kısa ayarlamak istenirse buradan güncellenebilir
    "ACCESS_TOKEN_LIFETIME": timedelta(days=365),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=3650),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

AUTHENTICATION_BACKENDS = (
    "app.users.auth_backend.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
)


