"""
Cache invalidation helpers.

Used to invalidate API response caches when data changes (e.g. barbershop
main_image) so clients get fresh data without waiting for TTL.
"""
from django.core.cache import cache


def invalidate_home_dashboard_cache():
    """
    Invalidate all home dashboard cache entries (newest_shops, top_rated_shops, etc.).
    Call this when barbershop data that appears on home changes (e.g. main_image).
    Uses Redis delete_pattern when available; no-op otherwise.
    """
    try:
        if hasattr(cache, "delete_pattern"):
            cache.delete_pattern("home_dashboard_*")
    except Exception:
        pass
