"""
Security middleware for additional protection layers.
"""
import logging
import time
import hashlib
import json
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse, JsonResponse, HttpResponseNotModified
from django.core.exceptions import SuspiciousOperation
from django.conf import settings
from django.utils.cache import patch_response_headers

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


class ETagMiddleware(MiddlewareMixin):
    """
    Add ETag support for GET requests to enable conditional requests and reduce bandwidth.
    This middleware generates ETags based on response content and handles If-None-Match headers.
    """
    def process_response(self, request, response):
        # Only process GET requests with 200 OK status
        if request.method != 'GET' or response.status_code != 200:
            return response
        
        # Skip for admin and non-API endpoints
        if request.path.startswith('/admin/') or not request.path.startswith('/api/'):
            return response
        
        # Skip if ETag already set
        if 'ETag' in response:
            return response
        
        # Generate ETag from response content
        try:
            # For DRF Response objects, we need to render them first to get content
            # For regular Django responses, use response.content
            content_to_hash = None
            
            # Ensure DRF Response is rendered (if not already)
            if hasattr(response, 'render') and not response._is_rendered:
                response.render()
            
            if hasattr(response, 'data'):
                # DRF Response - serialize data to JSON string
                import json
                try:
                    # Use rendered content if available, otherwise serialize data
                    if hasattr(response, 'rendered_content') and response.rendered_content:
                        content_to_hash = response.rendered_content
                    else:
                        content_to_hash = json.dumps(response.data, sort_keys=True).encode('utf-8')
                except (TypeError, ValueError):
                    # If data is not JSON serializable, fall back to content
                    if hasattr(response, 'content') and response.content:
                        content_to_hash = response.content
            elif hasattr(response, 'content') and response.content:
                # Regular Django response
                content_to_hash = response.content
            
            if content_to_hash:
                content_hash = hashlib.md5(content_to_hash).hexdigest()
                etag = f'"{content_hash}"'
                
                # Check If-None-Match header
                if_none_match = request.META.get('HTTP_IF_NONE_MATCH', '').strip('"')
                if if_none_match == content_hash:
                    # Content hasn't changed, return 304 Not Modified
                    return HttpResponseNotModified()
                
                # Add ETag to response
                response['ETag'] = etag
                # Add Cache-Control for public caching (adjust max-age as needed)
                if 'Cache-Control' not in response:
                    response['Cache-Control'] = 'public, max-age=300'  # 5 minutes default
        except Exception as e:
            logger.debug(f"ETag generation failed: {e}")
        
        return response


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
