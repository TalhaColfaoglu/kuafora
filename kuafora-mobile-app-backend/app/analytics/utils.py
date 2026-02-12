"""
Analytics utility functions for tracking user activity
"""
from app.analytics.signals import track_user_activity, create_user_session


def track_login(user, device_id=None, app_type='main', request=None, **session_kwargs):
    """
    Kullanıcı giriş yaptığında bu fonksiyonu çağırın.
    
    Usage:
        from app.analytics.utils import track_login
        
        # API view içinde:
        track_login(
            user=request.user,
            device_id=request.data.get('device_id'),
            app_type='main',
            request=request,
            platform='iOS',
            app_version='1.0.0',
            os_version='17.0'
        )
    
    Args:
        user: User instance
        device_id: Cihaz benzersiz ID (zorunlu - mobil cihazın unique identifier'ı)
        app_type: 'main' (mobil app) veya 'partner' (partner app)
        request: HTTP request object (optional, IP ve user agent için)
        **session_kwargs: Ek session bilgileri (platform, app_version, os_version, session_id)
    
    Returns:
        UserSession instance
    """
    return create_user_session(
        user=user,
        device_id=device_id,
        app_type=app_type,
        request=request,
        **session_kwargs
    )


def track_activity(user, device_id=None, app_type='main', request=None):
    """
    Basit aktivite tracking - sadece UserActivityLog günceller (session oluşturmaz)
    
    Her API isteğinde çağrılabilir (lightweight)
    
    Args:
        user: User instance
        device_id: Cihaz benzersiz ID
        app_type: 'main' veya 'partner'
        request: HTTP request object (optional)
    
    Returns:
        UserActivityLog instance
    """
    return track_user_activity(
        user=user,
        device_id=device_id,
        app_type=app_type,
        request=request
    )


def get_or_extract_device_id(request):
    """
    Request'ten device_id çıkar (header, query param, veya body'den)
    
    Args:
        request: HTTP request object
    
    Returns:
        str: device_id or None
    """
    # Header'dan al
    device_id = request.META.get('HTTP_X_DEVICE_ID')
    if device_id:
        return device_id
    
    # Query param'dan al
    device_id = request.GET.get('device_id')
    if device_id:
        return device_id
    
    # POST body'den al (DRF request.data)
    if hasattr(request, 'data'):
        device_id = request.data.get('device_id')
        if device_id:
            return device_id
    
    return None


# Middleware için helper
class ActivityTrackingMixin:
    """
    DRF ViewSet veya APIView'lerde kullanılabilir mixin
    
    Usage:
        class MyViewSet(ActivityTrackingMixin, viewsets.ModelViewSet):
            track_activity_on_actions = ['list', 'retrieve', 'create']
            
            def list(self, request, *args, **kwargs):
                self.track_user_activity(request)
                return super().list(request, *args, **kwargs)
    """
    
    def track_user_activity(self, request, app_type='main'):
        """ViewSet/APIView içinden aktivite tracking"""
        if not request.user or not request.user.is_authenticated:
            return None
        
        device_id = get_or_extract_device_id(request)
        if not device_id:
            # Fallback: user ID kullan
            device_id = f"user_{request.user.id}"
        
        return track_activity(
            user=request.user,
            device_id=device_id,
            app_type=app_type,
            request=request
        )
