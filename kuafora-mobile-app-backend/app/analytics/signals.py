"""Analytics signals for tracking user activity"""
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import F

from app.analytics.models import UserActivityLog, UserSession
import uuid


def track_user_activity(user, device_id=None, app_type='main', request=None):
    """
    Track user activity - kullanıcı her giriş yaptığında çağrılır
    
    Args:
        user: User instance
        device_id: Cihaz benzersiz ID
        app_type: 'main' veya 'partner'
        request: HTTP request object (optional)
    """
    if not device_id:
        device_id = f"device_{user.id}"
    
    today = timezone.now().date()
    
    # UserActivityLog kaydı oluştur veya güncelle
    activity, created = UserActivityLog.objects.get_or_create(
        user=user,
        device_id=device_id,
        activity_date=today,
        app_type=app_type,
        defaults={
            'login_count': 1,
            'last_activity': timezone.now()
        }
    )
    
    if not created:
        # Varolan kaydı güncelle
        activity.login_count = F('login_count') + 1
        activity.last_activity = timezone.now()
        activity.save(update_fields=['login_count', 'last_activity'])
    
    return activity


def create_user_session(user, device_id=None, app_type='main', request=None, **kwargs):
    """
    UserSession kaydı oluştur - her giriş için
    
    Args:
        user: User instance
        device_id: Cihaz benzersiz ID
        app_type: 'main' veya 'partner'
        request: HTTP request object (optional)
        **kwargs: Ek session bilgileri (platform, app_version, os_version, etc.)
    """
    if not device_id:
        device_id = f"device_{user.id if user else uuid.uuid4()}"
    
    session_id = kwargs.get('session_id', str(uuid.uuid4()))
    platform = kwargs.get('platform', 'unknown')
    app_version = kwargs.get('app_version', '')
    os_version = kwargs.get('os_version', '')
    
    # IP ve user agent bilgilerini request'ten al
    ip_address = None
    user_agent = ''
    if request:
        # Get IP from headers (proxy aware)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        
        user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Session kaydı oluştur
    session = UserSession.objects.create(
        user=user,
        session_id=session_id,
        device_id=device_id,
        app_type=app_type,
        platform=platform,
        app_version=app_version,
        os_version=os_version,
        start_time=timezone.now(),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    # UserActivityLog'u da güncelle
    track_user_activity(user, device_id, app_type, request)
    
    return session


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """
    Django'nun built-in user_logged_in sinyali ile otomatik tracking
    NOT: Bu sadece Django admin/web girişleri için çalışır.
    Mobil API için ayrı endpoint'ten track_user_activity veya create_user_session çağrılmalı.
    """
    # Web/admin girişlerini track et
    device_id = request.session.session_key or f"web_{user.id}"
    app_type = 'partner' if request.path.startswith('/partner') else 'main'
    
    track_user_activity(
        user=user,
        device_id=device_id,
        app_type=app_type,
        request=request
    )
