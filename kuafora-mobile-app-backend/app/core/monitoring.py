"""
Monitoring utilities for system health checks and metrics collection.
"""
import os
import psutil
import shutil
from typing import Dict, Any, Optional
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def check_database() -> Dict[str, Any]:
    """Check database connection health."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return {"status": "healthy", "error": None}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


def check_cache() -> Dict[str, Any]:
    """Check cache connection health."""
    try:
        test_key = "health_check_cache_test"
        cache.set(test_key, "ok", 10)
        result = cache.get(test_key)
        if result == "ok":
            cache.delete(test_key)
            return {"status": "healthy", "error": None}
        else:
            return {"status": "unhealthy", "error": "Cache get failed"}
    except Exception as e:
        logger.warning(f"Cache health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


def check_disk_space(path: str = "/") -> Dict[str, Any]:
    """Check disk space usage."""
    try:
        total, used, free = shutil.disk_usage(path)
        total_gb = total / (1024 ** 3)
        used_gb = used / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        percent_used = (used / total) * 100
        
        # Warning thresholds
        warning_threshold = 80  # 80% used
        critical_threshold = 90  # 90% used
        
        if percent_used >= critical_threshold:
            status = "critical"
        elif percent_used >= warning_threshold:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "free_gb": round(free_gb, 2),
            "percent_used": round(percent_used, 2),
            "warning_threshold": warning_threshold,
            "critical_threshold": critical_threshold,
        }
    except Exception as e:
        logger.error(f"Disk space check failed: {e}")
        return {"status": "error", "error": str(e)}


def get_system_metrics() -> Dict[str, Any]:
    """Get system metrics (CPU, RAM, Disk)."""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024 ** 3)
        memory_used_gb = memory.used / (1024 ** 3)
        memory_free_gb = memory.available / (1024 ** 3)
        memory_percent = memory.percent
        
        # Disk usage (root partition)
        disk = check_disk_space()
        
        # System load average (Unix only)
        load_avg = None
        try:
            load_avg = os.getloadavg()
        except (OSError, AttributeError):
            pass
        
        return {
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count,
                "status": "warning" if cpu_percent > 80 else "healthy",
            },
            "memory": {
                "total_gb": round(memory_total_gb, 2),
                "used_gb": round(memory_used_gb, 2),
                "free_gb": round(memory_free_gb, 2),
                "percent": round(memory_percent, 2),
                "status": "warning" if memory_percent > 85 else "healthy",
            },
            "disk": disk,
            "load_average": load_avg,
        }
    except Exception as e:
        logger.error(f"System metrics collection failed: {e}")
        return {"error": str(e)}


def get_application_metrics() -> Dict[str, Any]:
    """Get application-specific metrics."""
    try:
        from django.contrib.auth.models import User
        from app.barbers.models import Barbershop
        
        metrics = {
            "users": {
                "total": User.objects.count(),
                "active": User.objects.filter(is_active=True).count(),
            },
            "barbershops": {
                "total": Barbershop.objects.count(),
                "approved": Barbershop.objects.filter(is_approved=True).count(),
                "pending": Barbershop.objects.filter(is_approved=False).count(),
            },
        }
        return metrics
    except Exception as e:
        logger.error(f"Application metrics collection failed: {e}")
        return {"error": str(e)}


def check_health() -> Dict[str, Any]:
    """Comprehensive health check."""
    health_status = {
        "status": "healthy",
        "timestamp": None,
        "database": check_database(),
        "cache": check_cache(),
        "disk": check_disk_space(),
    }
    
    # Import datetime here to avoid circular imports
    from datetime import datetime
    health_status["timestamp"] = datetime.now().isoformat()
    
    # Determine overall status
    if health_status["database"]["status"] != "healthy":
        health_status["status"] = "unhealthy"
    elif health_status["disk"]["status"] == "critical":
        health_status["status"] = "critical"
    elif health_status["disk"]["status"] == "warning":
        health_status["status"] = "warning"
    
    return health_status


def should_send_alert(health_data: Dict[str, Any]) -> tuple:
    """Determine if an alert should be sent based on health data."""
    # Critical alerts
    if health_data.get("status") == "critical":
        return True, "critical"
    
    if health_data.get("status") == "unhealthy":
        return True, "unhealthy"
    
    # Warning alerts (disk space)
    disk = health_data.get("disk", {})
    if disk.get("status") == "critical":
        return True, "disk_critical"
    if disk.get("status") == "warning":
        return True, "disk_warning"
    
    # Database unhealthy
    if health_data.get("database", {}).get("status") != "healthy":
        return True, "database_unhealthy"
    
    return False, None

