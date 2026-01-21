"""
Security middleware for additional protection layers.
"""
import logging
import time
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import SuspiciousOperation
from django.conf import settings

logger = logging.getLogger(__name__)


class RequestSizeLimitMiddleware(MiddlewareMixin):
    """
    Limit request body size to prevent DoS attacks.
    """
    MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
    
    def process_request(self, request):
        if request.method in ('POST', 'PUT', 'PATCH'):
            content_length = request.META.get('CONTENT_LENGTH', 0)
            try:
                content_length = int(content_length)
                if content_length > self.MAX_REQUEST_SIZE:
                    logger.warning(f"Request size limit exceeded: {content_length} bytes from {request.META.get('REMOTE_ADDR')}")
                    return JsonResponse(
                        {'detail': 'İstek boyutu çok büyük.'},
                        status=413
                    )
            except (ValueError, TypeError):
                pass
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add additional security headers to all responses.
    """
    def process_response(self, request, response):
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Swagger UI için gerekli
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none';"
        )
        response['Content-Security-Policy'] = csp
        
        # Additional security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Remove server information
        response['Server'] = 'Kuafora'
        
        return response


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Log security-relevant events for audit purposes.
    """
    SENSITIVE_PATHS = ['/api/auth/login/', '/api/auth/register/', '/api/auth/change-password/']
    
    def process_request(self, request):
        request._audit_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        # Log authentication attempts
        if any(path in request.path for path in self.SENSITIVE_PATHS):
            duration = time.time() - getattr(request, '_audit_start_time', time.time())
            status = response.status_code
            
            # Don't log sensitive data, just metadata
            audit_data = {
                'path': request.path,
                'method': request.method,
                'status': status,
                'duration': f"{duration:.3f}s",
                'ip': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:100],  # Limit length
            }
            
            if status >= 400:
                logger.warning(f"[AUDIT] Failed attempt: {audit_data}")
            else:
                logger.info(f"[AUDIT] Success: {audit_data}")
        
        return response


class IPWhitelistMiddleware(MiddlewareMixin):
    """
    Optional IP whitelist for admin endpoints (can be enabled via settings).
    """
    def process_request(self, request):
        # Only apply to admin if enabled
        if hasattr(settings, 'ADMIN_IP_WHITELIST') and settings.ADMIN_IP_WHITELIST:
            if request.path.startswith('/admin/'):
                client_ip = request.META.get('REMOTE_ADDR')
                if client_ip not in settings.ADMIN_IP_WHITELIST:
                    logger.warning(f"Blocked admin access from unauthorized IP: {client_ip}")
                    return HttpResponse('Unauthorized', status=403)
        return None

