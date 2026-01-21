"""
Additional input validators for security.
"""
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_no_sql_injection(value):
    """
    Basic check for SQL injection patterns.
    Note: Django ORM already protects against SQL injection,
    but this adds an extra layer for user-facing input.
    """
    if not isinstance(value, str):
        return
    
    dangerous_patterns = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
        r"(--|#|/\*|\*/)",
        r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
        r"(\bUNION\b.*\bSELECT\b)",
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValidationError(_("Geçersiz karakterler tespit edildi."))


def validate_no_xss(value):
    """
    Basic check for XSS patterns in user input.
    """
    if not isinstance(value, str):
        return
    
    dangerous_patterns = [
        r"<script[^>]*>",
        r"javascript:",
        r"on\w+\s*=",  # onclick=, onerror=, etc.
        r"<iframe[^>]*>",
        r"<object[^>]*>",
        r"<embed[^>]*>",
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValidationError(_("Geçersiz içerik tespit edildi."))


def validate_file_extension(filename, allowed_extensions=None):
    """
    Validate file extension against whitelist.
    """
    if allowed_extensions is None:
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    
    if not filename:
        raise ValidationError(_("Dosya adı boş olamaz."))
    
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    if f'.{ext}' not in allowed_extensions:
        raise ValidationError(_(f"İzin verilen dosya türleri: {', '.join(allowed_extensions)}"))


def validate_file_size(file, max_size_mb=10):
    """
    Validate file size.
    """
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(_(f"Dosya boyutu {max_size_mb}MB'dan büyük olamaz."))


def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal and other attacks.
    """
    # Remove path components
    filename = filename.split('/')[-1].split('\\')[-1]
    
    # Remove dangerous characters
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    
    return filename

