"""
Cache monitoring utilities for performance tracking
"""
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def get_cache_stats():
    """
    Get cache statistics (if using Redis)
    Returns cache hit/miss information
    """
    try:
        if hasattr(cache, 'client'):
            # Redis cache backend
            redis_client = cache.client.get_client()
            info = redis_client.info('stats')
            
            # Calculate hit rate
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0
            
            return {
                'hits': hits,
                'misses': misses,
                'total': total,
                'hit_rate': round(hit_rate, 2),
                'keyspace_hits': hits,
                'keyspace_misses': misses,
            }
    except Exception as e:
        logger.warning(f"Could not get cache stats: {e}")
    
    return {
        'hits': 0,
        'misses': 0,
        'total': 0,
        'hit_rate': 0,
    }


def log_cache_operation(operation, key, hit=None):
    """
    Log cache operations for monitoring
    """
    if settings.DEBUG:
        if hit is True:
            logger.debug(f"Cache HIT: {key}")
        elif hit is False:
            logger.debug(f"Cache MISS: {key}")
        else:
            logger.debug(f"Cache {operation.upper()}: {key}")

