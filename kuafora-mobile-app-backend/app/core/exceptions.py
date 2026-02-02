"""
Custom exception handlers for security and better error messages.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from django.http import Http404
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from rest_framework.exceptions import (
    ValidationError,
    AuthenticationFailed,
    PermissionDenied as DRFPermissionDenied,
    NotFound,
    Throttled,
)
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that:
    1. Prevents information disclosure in error messages
    2. Sanitizes sensitive data
    3. Provides consistent error format
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # If response is None, it's an unhandled exception
    if response is None:
        # Log the full exception for debugging (server-side only)
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        
        # Return generic error to client (don't expose internal details)
        return Response(
            {
                "detail": "Uygulama bakımda. Lütfen daha sonra tekrar deneyin.",
                "error_code": "INTERNAL_ERROR"
            },
            status=500
        )
    
    # Sanitize error messages to prevent information disclosure
    if isinstance(exc, ValidationError):
        # Don't expose field names or validation details that could help attackers
        detail = exc.detail
        if isinstance(detail, dict):
            # Only expose non-sensitive field errors
            sanitized = {}
            sensitive_fields = {'password', 'token', 'secret', 'key', 'phone', 'email'}
            for field, errors in detail.items():
                if field.lower() not in sensitive_fields:
                    sanitized[field] = errors
                else:
                    sanitized[field] = ["Bu alan geçersiz."]
            response.data = sanitized if sanitized else {"detail": "Girilen veriler geçersiz."}
        elif isinstance(detail, list):
            # Generic validation error
            response.data = {"detail": "Girilen veriler geçersiz."}
    
    elif isinstance(exc, AuthenticationFailed):
        # Don't reveal why authentication failed
        response.data = {
            "detail": "Kimlik doğrulama başarısız.",
            "error_code": "AUTHENTICATION_FAILED"
        }
    
    elif isinstance(exc, (PermissionDenied, DRFPermissionDenied)):
        response.data = {
            "detail": "Bu işlem için yetkiniz yok.",
            "error_code": "PERMISSION_DENIED"
        }
    
    elif isinstance(exc, (Http404, NotFound)):
        response.data = {
            "detail": "İstenen kaynak bulunamadı.",
            "error_code": "NOT_FOUND"
        }
    
    elif isinstance(exc, Throttled):
        response.data = {
            "detail": "Çok fazla istek gönderdiniz. Lütfen bir süre bekleyin.",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "retry_after": exc.wait
        }
    
    # Ensure error responses don't expose sensitive headers
    if response:
        # Remove potentially sensitive headers
        sensitive_headers = ['X-Debug-Info', 'X-Exception-Type', 'X-Exception-Value']
        for header in sensitive_headers:
            response.headers.pop(header, None)
    
    return response

