"""
Günlük e-posta sayacı ve 400 limit aşımında colfaoglutalha@gmail.com'a uyarı maili.
"""
import logging
from datetime import timedelta

from django.utils import timezone
from django.db.models import Sum
from django.core.mail import send_mail
from django.conf import settings

from .models import EmailDailyLog

logger = logging.getLogger(__name__)

DAILY_EMAIL_ALERT_THRESHOLD = 400
ALERT_RECIPIENT_EMAIL = "colfaoglutalha@gmail.com"


def increment_daily_email_count() -> int:
    """
    Bugünün e-posta sayacını 1 artırır.
    400'ü geçerse (bir kez) colfaoglutalha@gmail.com'a uyarı maili gönderir.
    Dönen değer: güncel günlük toplam.
    """
    today = timezone.now().date()
    log, created = EmailDailyLog.objects.get_or_create(
        date=today,
        defaults={"count": 0, "alert_sent": False},
    )
    log.count += 1
    log.save(update_fields=["count"])

    if log.count > DAILY_EMAIL_ALERT_THRESHOLD and not log.alert_sent:
        _send_daily_limit_alert(log.count)
        log.alert_sent = True
        log.save(update_fields=["alert_sent"])

    return log.count


def _send_daily_limit_alert(count: int) -> None:
    """Günlük limit aşımında uyarı maili gönder (sayaca dahil etmiyoruz)."""
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None) or "noreply@kuafora.com"
    subject = f"Kuafora • Günlük e-posta limiti aşıldı ({count} > {DAILY_EMAIL_ALERT_THRESHOLD})"
    message = (
        f"Bugün gönderilen e-posta sayısı {count} olarak kaydedildi.\n"
        f"Limit: {DAILY_EMAIL_ALERT_THRESHOLD}.\n\n"
        "Lütfen SMTP kotasını veya gönderim sıklığını kontrol edin.\n\n"
        "Kuafora Admin"
    )
    try:
        send_mail(
            subject,
            message,
            from_email,
            [ALERT_RECIPIENT_EMAIL],
            fail_silently=False,
        )
        logger.info("[EMAIL] Günlük limit uyarı maili gönderildi: %s", ALERT_RECIPIENT_EMAIL)
    except Exception as e:
        logger.exception("[EMAIL] Günlük limit uyarı maili gönderilemedi: %s", e)


def get_today_email_count() -> int:
    """Bugün gönderilen e-posta sayısını döner."""
    today = timezone.now().date()
    try:
        log = EmailDailyLog.objects.get(date=today)
        return log.count
    except EmailDailyLog.DoesNotExist:
        return 0


def get_weekly_email_count() -> int:
    """Son 7 günde (bugün dahil) gönderilen e-posta sayısını döner."""
    today = timezone.now().date()
    start = today - timedelta(days=6)
    result = EmailDailyLog.objects.filter(date__gte=start, date__lte=today).aggregate(total=Sum("count"))
    return result["total"] or 0


def get_monthly_email_count() -> int:
    """Son 30 günde (bugün dahil) gönderilen e-posta sayısını döner."""
    today = timezone.now().date()
    start = today - timedelta(days=29)
    result = EmailDailyLog.objects.filter(date__gte=start, date__lte=today).aggregate(total=Sum("count"))
    return result["total"] or 0


def get_yearly_email_count() -> int:
    """Son 365 günde (bugün dahil) gönderilen e-posta sayısını döner."""
    today = timezone.now().date()
    start = today - timedelta(days=364)
    result = EmailDailyLog.objects.filter(date__gte=start, date__lte=today).aggregate(total=Sum("count"))
    return result["total"] or 0
