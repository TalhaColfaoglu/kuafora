from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.db import connection
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

@never_cache
@require_http_methods(["GET"])
def health_check(request):
    """
    Health check endpoint for load balancer and monitoring
    """
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "cache": "unknown"
    }
    
    status_code = 200
    
    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            health_status["database"] = "healthy"
    except Exception as e:
        health_status["database"] = "unhealthy"
        health_status["status"] = "unhealthy"
        status_code = 503
        logger.error(f"Database health check failed: {e}")
    
    # Check cache connection (optional)
    try:
        cache.set("health_check", "ok", 10)
        if cache.get("health_check") == "ok":
            health_status["cache"] = "healthy"
        else:
            health_status["cache"] = "unhealthy"
    except Exception as e:
        health_status["cache"] = "unhealthy"
        logger.warning(f"Cache health check failed: {e}")
    
    return JsonResponse(health_status, status=status_code)
