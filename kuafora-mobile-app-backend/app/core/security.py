"""
Security utilities and middleware for protecting sensitive data.
"""
import re
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Sensitive field patterns that should never be logged or exposed
SENSITIVE_FIELDS = {
    'password', 'password1', 'password2', 'old_password', 'new_password',
    'secret', 'secret_key', 'api_key', 'access_token', 'refresh_token',
    'token', 'authorization', 'auth', 'credentials',
    'phone_encrypted', 'phone_hash',  # Encrypted phone data
    'aws_access_key_id', 'aws_secret_access_key',
    'email_host_password', 'database_password',
}

# Patterns to detect sensitive data in strings
SENSITIVE_PATTERNS = [
    r'password["\']?\s*[:=]\s*["\']?([^"\']+)',  # password: "value"
    r'token["\']?\s*[:=]\s*["\']?([^"\']+)',     # token: "value"
    r'secret["\']?\s*[:=]\s*["\']?([^"\']+)',    # secret: "value"
    r'key["\']?\s*[:=]\s*["\']?([^"\']+)',       # key: "value"
]


def sanitize_dict(data: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
    """
    Recursively sanitize dictionary by masking sensitive fields.
    Prevents sensitive data from being logged or exposed.
    """
    if depth > 10:  # Prevent infinite recursion
        return {"error": "Max depth reached"}
    
    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        
        # Check if this is a sensitive field
        is_sensitive = any(
            sensitive in key_lower 
            for sensitive in SENSITIVE_FIELDS
        )
        
        if is_sensitive:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value, depth + 1)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_dict(item, depth + 1) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            # Check if value contains sensitive patterns
            if isinstance(value, str):
                for pattern in SENSITIVE_PATTERNS:
                    if re.search(pattern, value, re.IGNORECASE):
                        sanitized[key] = "***REDACTED***"
                        break
                else:
                    sanitized[key] = value
            else:
                sanitized[key] = value
    
    return sanitized


def sanitize_string(text: str) -> str:
    """Sanitize a string by masking sensitive patterns."""
    sanitized = text
    for pattern in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, r'\1***REDACTED***', sanitized, flags=re.IGNORECASE)
    return sanitized


class SecurityLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that automatically sanitizes sensitive data."""
    
    def process(self, msg, kwargs):
        # Sanitize extra kwargs
        if 'extra' in kwargs:
            kwargs['extra'] = sanitize_dict(kwargs['extra'])
        
        # Sanitize message if it's a dict
        if isinstance(msg, dict):
            msg = sanitize_dict(msg)
        elif isinstance(msg, str):
            msg = sanitize_string(msg)
        
        return msg, kwargs


def get_security_logger(name: str) -> SecurityLoggerAdapter:
    """Get a logger that automatically sanitizes sensitive data."""
    return SecurityLoggerAdapter(logging.getLogger(name), {})

