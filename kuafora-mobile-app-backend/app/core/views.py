"""
Core views for security and error handling.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import logging

from .monitoring import (
    check_health,
    get_system_metrics,
    get_application_metrics,
    should_send_alert,
)

logger = logging.getLogger(__name__)


def csrf_failure(request, reason=""):
    """
    Custom CSRF failure handler that doesn't expose internal details.
    """
    return JsonResponse(
        {
            "detail": "CSRF doğrulaması başarısız. Lütfen sayfayı yenileyin.",
            "error_code": "CSRF_FAILED"
        },
        status=403
    )


@never_cache
@require_http_methods(["GET"])
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    Comprehensive health check endpoint.
    Returns 200 if healthy, 503 if unhealthy.
    """
    try:
        health_data = check_health()
        
        # Determine HTTP status code
        if health_data["status"] == "healthy":
            http_status = status.HTTP_200_OK
        elif health_data["status"] == "critical":
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        
        return Response(health_data, status=http_status)
    except Exception as e:
        logger.error(f"Health check endpoint error: {e}", exc_info=True)
        return Response(
            {
                "status": "error",
                "error": "Health check failed",
                "timestamp": None,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@never_cache
@require_http_methods(["GET"])
@api_view(["GET"])
@permission_classes([AllowAny])
def metrics(request):
    """
    System and application metrics endpoint.
    """
    try:
        metrics_data = {
            "system": get_system_metrics(),
            "application": get_application_metrics(),
        }
        return Response(metrics_data, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Metrics endpoint error: {e}", exc_info=True)
        return Response(
            {
                "error": "Metrics collection failed",
                "detail": str(e) if settings.DEBUG else "Internal error",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@never_cache
@require_http_methods(["GET"])
@api_view(["GET"])
@permission_classes([AllowAny])
def health_simple(request):
    """
    Simple health check endpoint (for load balancers).
    Returns 200 OK if database is accessible.
    """
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Simple health check failed: {e}")
        return Response(
            {"status": "error"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


@never_cache
@require_http_methods(["GET"])
@api_view(["GET"])
@permission_classes([AllowAny])
def version_check(request):
    """
    Uygulama versiyon kontrolü endpoint'i.
    
    Query Parameters:
    - current_version: Mevcut uygulama versiyonu (örn: "1.0.0-internal.2")
    - current_build: Mevcut build numarası (örn: 2)
    - platform: Platform ("android" veya "ios")
    
    Returns:
    - update_available: Güncelleme mevcut mu?
    - force_update: Zorunlu güncelleme mi?
    - latest_version: En son versiyon numarası
    - update_message: Güncelleme mesajı
    - play_store_url: Play Store / App Store URL
    """
    try:
        from .models import AppVersion
        
        current_version = request.query_params.get('current_version', '').strip()
        current_build_str = request.query_params.get('current_build', '0')
        platform = request.query_params.get('platform', 'android').strip().lower()
        
        # Platform kontrolü
        if platform not in ['android', 'ios']:
            platform = 'android'
        
        # Build numarasını integer'a çevir
        try:
            current_build = int(current_build_str)
        except (ValueError, TypeError):
            current_build = 0
        
        # En son aktif versiyonu bul
        latest_version = AppVersion.objects.filter(
            platform=platform,
            is_active=True
        ).order_by('-version_code').first()
        
        if not latest_version:
            # Hiç versiyon yoksa güncelleme yok
            return Response({
                'update_available': False,
                'force_update': False,
            }, status=status.HTTP_200_OK)
        
        # Güncelleme kontrolü
        update_available = current_build < latest_version.version_code
        
        # Zorunlu güncelleme kontrolü
        force_update = False
        if latest_version.force_update:
            # Eğer bu versiyon zorunlu güncelleme olarak işaretlenmişse
            force_update = current_build < latest_version.version_code
        elif latest_version.min_version_code:
            # Eğer min_version_code belirtilmişse, o build'den eski olanlar için zorunlu
            force_update = current_build < latest_version.min_version_code
        
        response_data = {
            'update_available': update_available,
            'force_update': force_update,
        }
        
        if update_available:
            response_data['latest_version'] = latest_version.version_name
            response_data['update_message'] = latest_version.update_message or 'Yeni özellikler ve iyileştirmeler için uygulamayı güncelleyin.'
            
            # Play Store URL
            if latest_version.play_store_url:
                response_data['play_store_url'] = latest_version.play_store_url
            elif platform == 'android':
                response_data['play_store_url'] = 'https://play.google.com/store/apps/details?id=com.kuafora.app'
            else:
                response_data['play_store_url'] = 'https://apps.apple.com/app/id...'  # iOS App Store URL'i buraya eklenebilir
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Version check endpoint error: {e}", exc_info=True)
        return Response(
            {
                'update_available': False,
                'force_update': False,
                'error': 'Version check failed' if settings.DEBUG else None,
            },
            status=status.HTTP_200_OK  # Hata durumunda bile 200 döndür, kullanıcıyı rahatsız etme
        )

