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

