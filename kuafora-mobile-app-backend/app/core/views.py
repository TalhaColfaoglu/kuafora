"""
Core views for security and error handling.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


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

