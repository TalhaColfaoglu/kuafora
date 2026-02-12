"""
API Tracking Integration Examples
Bu dosya tracking sisteminin API endpoint'lere nasıl ekleneceğini gösterir
"""

# ============================================================================
# ÖRNEK 1: DRF Authentication View (Login/Register)
# ============================================================================

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from app.analytics.utils import track_login


@api_view(['POST'])
@permission_classes([AllowAny])
def mobile_login(request):
    """
    Mobil uygulama login endpoint'i
    
    POST /api/auth/login/
    {
        "email": "user@example.com",
        "password": "password123",
        "device_id": "unique-device-uuid",
        "platform": "iOS",
        "app_version": "1.0.0",
        "os_version": "17.0"
    }
    """
    email = request.data.get('email')
    password = request.data.get('password')
    device_id = request.data.get('device_id')
    platform = request.data.get('platform', 'unknown')
    app_version = request.data.get('app_version', '')
    os_version = request.data.get('os_version', '')
    
    # Kullanıcıyı authenticate et
    user = authenticate(email=email, password=password)
    
    if user is None:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # ✅ TRACKING EKLE - Kullanıcı başarıyla giriş yaptı
    track_login(
        user=user,
        device_id=device_id or f"device_{user.id}",  # Fallback
        app_type='main',  # 'main' = mobil app, 'partner' = partner app
        request=request,
        platform=platform,
        app_version=app_version,
        os_version=os_version
    )
    
    # Token oluştur ve response döndür
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {
            'id': str(user.id),
            'email': user.email,
            'full_name': user.full_name,
        }
    })


# ============================================================================
# ÖRNEK 2: DRF ViewSet ile Automatic Tracking
# ============================================================================

from rest_framework import viewsets
from app.analytics.utils import ActivityTrackingMixin


class BarbershopViewSet(ActivityTrackingMixin, viewsets.ReadOnlyModelViewSet):
    """
    Barbershop listesi ve detay endpoint'leri
    
    ActivityTrackingMixin sayesinde her istekte otomatik tracking
    """
    
    def list(self, request, *args, **kwargs):
        # ✅ Her liste isteğinde aktivite tracking
        if request.user.is_authenticated:
            self.track_user_activity(request, app_type='main')
        
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        # ✅ Her detay görüntülemede aktivite tracking
        if request.user.is_authenticated:
            self.track_user_activity(request, app_type='main')
        
        return super().retrieve(request, *args, **kwargs)


# ============================================================================
# ÖRNEK 3: Token Refresh Endpoint (Lightweight Tracking)
# ============================================================================

from app.analytics.utils import track_activity


@api_view(['POST'])
def token_refresh(request):
    """
    Token refresh endpoint
    
    POST /api/auth/refresh/
    {
        "refresh": "refresh-token-here",
        "device_id": "unique-device-uuid"
    }
    """
    # Token refresh işlemi...
    # (RefreshToken logic)
    
    # ✅ LIGHTWEIGHT TRACKING - Sadece aktivite logu (session oluşturmaz)
    if request.user and request.user.is_authenticated:
        device_id = request.data.get('device_id')
        track_activity(
            user=request.user,
            device_id=device_id,
            app_type='main',
            request=request
        )
    
    return Response({'access': 'new-access-token'})


# ============================================================================
# ÖRNEK 4: Custom Middleware (Tüm API İsteklerinde Otomatik)
# ============================================================================

from django.utils.deprecation import MiddlewareMixin
from app.analytics.utils import get_or_extract_device_id, track_activity


class ActivityTrackingMiddleware(MiddlewareMixin):
    """
    Tüm authenticated API isteklerinde otomatik tracking
    
    UYARI: Bu her istekte çalışır, sadece gerekiyorsa kullanın
    Çok fazla DB yazımı oluşturabilir - tercih edilen yöntem endpoint bazlı tracking
    """
    
    EXCLUDED_PATHS = [
        '/admin/',
        '/static/',
        '/media/',
        '/health/',
    ]
    
    def process_request(self, request):
        # Admin ve static dosyaları hariç tut
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return None
        
        # Sadece authenticated kullanıcılar için
        if not request.user or not request.user.is_authenticated:
            return None
        
        # Staff kullanıcıları hariç tut (gerçek uygulama kullanıcıları için)
        if request.user.is_staff or request.user.is_superuser:
            return None
        
        # ✅ Tracking
        device_id = get_or_extract_device_id(request)
        if device_id:
            try:
                track_activity(
                    user=request.user,
                    device_id=device_id,
                    app_type='main',
                    request=request
                )
            except Exception as e:
                # Tracking hatası uygulamayı durdurmamalı
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Activity tracking failed: {e}")
        
        return None


# ============================================================================
# ÖRNEK 5: Django Rest Framework Authentication Backend Override
# ============================================================================

from rest_framework_simplejwt.authentication import JWTAuthentication
from app.analytics.utils import track_activity, get_or_extract_device_id


class TrackingJWTAuthentication(JWTAuthentication):
    """
    JWT Authentication ile otomatik tracking
    
    settings.py'da kullan:
    REST_FRAMEWORK = {
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'app.analytics.auth.TrackingJWTAuthentication',
        ],
    }
    """
    
    def authenticate(self, request):
        result = super().authenticate(request)
        
        if result is not None:
            user, token = result
            
            # ✅ Her authenticated istek için tracking
            if not user.is_staff and not user.is_superuser:
                device_id = get_or_extract_device_id(request)
                if device_id:
                    try:
                        track_activity(
                            user=user,
                            device_id=device_id,
                            app_type='main',
                            request=request
                        )
                    except Exception:
                        pass  # Tracking hatası authentication'ı etkilememeli
        
        return result


# ============================================================================
# ÖRNEK 6: Celery Task ile Asenkron Tracking (Optional - Performance için)
# ============================================================================

from celery import shared_task
from app.analytics.utils import track_activity


@shared_task
def async_track_activity(user_id, device_id, app_type='main'):
    """
    Asenkron aktivite tracking - performans için
    
    Kullanım:
        async_track_activity.delay(
            user_id=str(user.id),
            device_id=device_id,
            app_type='main'
        )
    """
    from app.users.models import User
    
    try:
        user = User.objects.get(id=user_id)
        track_activity(
            user=user,
            device_id=device_id,
            app_type=app_type,
            request=None
        )
    except User.DoesNotExist:
        pass


# View'de kullanım:
@api_view(['GET'])
def some_api_view(request):
    # ✅ Asenkron tracking - API response'u yavaşlatmaz
    if request.user.is_authenticated:
        device_id = get_or_extract_device_id(request)
        async_track_activity.delay(
            user_id=str(request.user.id),
            device_id=device_id or f"user_{request.user.id}",
            app_type='main'
        )
    
    return Response({'data': 'some data'})


# ============================================================================
# BEST PRACTICES
# ============================================================================

"""
✅ DO:
- Login/register endpoint'lerinde mutlaka track_login() kullan
- device_id'yi mobil app'ten al (cihaz unique ID)
- Hata durumlarında tracking'i try/except ile sarmalayın
- Staff/superuser kullanıcılarını tracking'den hariç tut (gerçek metrikler için)

❌ DON'T:
- Her API isteğinde session oluşturma (track_login yerine track_activity kullan)
- Tracking hatası yüzünden API isteğini fail etme
- device_id olmadan tracking yapma (fallback kullan)
- Admin/static dosya isteklerini track etme

💡 PERFORMANS:
- Çok yoğun endpoint'lerde asenkron tracking kullan (Celery)
- Middleware yerine endpoint bazlı tracking tercih et
- Database indexleri doğru kurulu (migration'da zaten var)

📊 MONITORING:
- Günlük calculate_daily_metrics command'ı çalıştır (cron job)
- UserActivityLog tablosunu düzenli temizle (eski kayıtları arşivle)
- DailyMetrics tablosunda tarihsel veri sakla
"""
