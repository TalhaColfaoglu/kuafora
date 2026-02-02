"""
URL helpers for API responses.

Ensures media/image URLs are always public (api.kuafora.com) when the request
reaches Django via internal host (e.g. Nginx proxy, Docker), so mobile clients
can load images.
"""


def build_public_media_uri(request, raw_url):
    """
    Build an absolute URL for a media path, using PUBLIC_API_ORIGIN when
    the request host is internal (Docker/load balancer), so clients get
    a reachable URL (e.g. https://api.kuafora.com/media/...).

    - If raw_url is already a full URL (e.g. CloudFront), return as-is unless
      it points to an internal host, in which case rebuild with PUBLIC_API_ORIGIN.
    - If raw_url is relative (e.g. /media/...), use request.build_absolute_uri
      but replace host with PUBLIC_API_ORIGIN when request host is internal.
    """
    if not raw_url or not raw_url.strip():
        return None
    raw_url = raw_url.strip()

    from django.conf import settings

    origin = (getattr(settings, "PUBLIC_API_ORIGIN", None) or "").strip().rstrip("/")

    def _is_internal_host(host):
        if not host:
            return True
        h = host.lower()
        if h in ("localhost", "127.0.0.1", "backend", "backend_dev", "web"):
            return True
        if h.startswith("172.") or h.startswith("10.") or h.startswith("192.168."):
            return True
        return False

    # Already absolute URL
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        try:
            from urllib.parse import urlparse

            parsed = urlparse(raw_url)
            host = (parsed.hostname or "").lower()
            if _is_internal_host(host) and origin:
                path = parsed.path or "/"
                if parsed.query:
                    path = f"{path}?{parsed.query}"
                return f"{origin}{path}"
        except Exception:
            pass
        return raw_url

    # Relative path: check request host
    try:
        host = request.get_host().split(":")[0].lower()
    except Exception:
        host = ""

    if _is_internal_host(host) and origin:
        path = raw_url if raw_url.startswith("/") else f"/{raw_url}"
        return f"{origin}{path}"

    return request.build_absolute_uri(raw_url)
