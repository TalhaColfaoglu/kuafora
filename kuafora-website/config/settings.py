"""
Django settings for config project (Kuafora marketing site).

Production-ready settings with TailwindCSS static pipeline and WhiteNoise.
"""

from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables based on environment
if os.getenv('DJANGO_SETTINGS_MODULE') == 'config.settings.production':
    load_dotenv(BASE_DIR / ".env.prod")
else:
    load_dotenv(BASE_DIR / ".env")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-secret-key-change-me"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"

# Host ayarları:
# 1) Öncelik: DJANGO_ALLOWED_HOSTS env (production için önerilen)
# 2) Yoksa: ALLOWED_HOSTS env (eski config'lerle uyumluluk için)
# 3) Yoksa: varsayılan liste
_default_hosts = "localhost,127.0.0.1,kuafora.com,www.kuafora.com,api.kuafora.com,website"
_raw_hosts = os.getenv("DJANGO_ALLOWED_HOSTS") or os.getenv("ALLOWED_HOSTS") or _default_hosts
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]

# Healthcheck'ler ve internal istekler için localhost ve 127.0.0.1'i her zaman ekle
for _h in ("localhost", "127.0.0.1"):
    if _h not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_h)

# Şifre sıfırlama sayfası API'ye POST atarken kullanılacak API base URL (sonunda / yok)
KUAFORA_API_URL = os.getenv("KUAFORA_API_URL", "https://api.kuafora.com").rstrip("/")

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'marketing',
    'partner',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database: DATABASE_URL or fallback to sqlite
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'tr-tr'
TIME_ZONE = 'Europe/Istanbul'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# S3 Configuration (optional - if AWS credentials are provided)
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'eu-central-1')
AWS_S3_CUSTOM_DOMAIN = os.getenv('AWS_S3_CUSTOM_DOMAIN')  # CloudFront domain buraya gelecek
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=31536000',  # 1 year cache - CloudFront için optimize edildi
    'ContentType': 'auto',  # Otomatik content-type algılama
}
AWS_DEFAULT_ACL = 'public-read'
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = False

# CloudFront için optimize edilmiş ayarlar
# CloudFront kullanıldığında görseller CDN üzerinden yüklenir (daha hızlı ve verimli)
USE_CLOUDFRONT = bool(AWS_S3_CUSTOM_DOMAIN and 'cloudfront.net' in AWS_S3_CUSTOM_DOMAIN)

# Use S3 for static files if credentials are provided, otherwise use WhiteNoise
if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME:
    # S3 for static files
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    if AWS_S3_CUSTOM_DOMAIN:
        # CloudFront veya custom domain kullanılıyor
        STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
        if USE_CLOUDFRONT:
            # CloudFront kullanılıyor - ek optimizasyonlar
            AWS_S3_OBJECT_PARAMETERS['CacheControl'] = 'max-age=31536000, public'  # CloudFront için public cache
    else:
        # Direkt S3 kullanılıyor
        STATIC_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/static/'
    
    # S3 for media files
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    if AWS_S3_CUSTOM_DOMAIN:
        # CloudFront veya custom domain kullanılıyor
        MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
    else:
        # Direkt S3 kullanılıyor
        MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/media/'
else:
    # WhiteNoise for production static serving (fallback)
    STORAGES = {
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

# Production-specific settings
if not DEBUG:
    # Security hardening
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "0") == "1"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "0") == "1"
    SECURE_BROWSER_XSS_FILTER = os.getenv("SECURE_BROWSER_XSS_FILTER", "1") == "1"
    SECURE_CONTENT_TYPE_NOSNIFF = os.getenv("SECURE_CONTENT_TYPE_NOSNIFF", "1") == "1"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
    
    # Trusted proxy settings for nginx
    USE_X_FORWARDED_HOST = True
    USE_X_FORWARDED_PORT = True
    
    # Media files configuration
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    
    # Logging configuration
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'loggers': {
            'django': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
        },
    }
    
    # Email configuration for production
    if os.getenv('EMAIL_HOST'):
        EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
        EMAIL_HOST = os.getenv('EMAIL_HOST')
        EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
        EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', '1') == '1'
        EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
        EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
        DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@kuafora.com')
        SERVER_EMAIL = os.getenv('SERVER_EMAIL', 'server@kuafora.com')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
