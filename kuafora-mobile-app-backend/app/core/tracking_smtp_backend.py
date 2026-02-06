"""
Django SMTP email backend with automatic email tracking.
Her başarılı email gönderiminde increment_daily_email_count() çağrılır.
"""
import logging
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend

logger = logging.getLogger(__name__)


class TrackingSMTPEmailBackend(SMTPEmailBackend):
    """
    SMTP email backend with automatic email tracking.
    Her başarılı email gönderiminde email tracking yapılır.
    """

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        
        # Django'nun standart SMTP backend'ini kullan
        sent = super().send_messages(email_messages)
        
        # Her başarılı email gönderiminde tracking yap
        if sent > 0:
            try:
                from app.users.email_tracking import increment_daily_email_count
                # Her gönderilen email için tracking yap
                for _ in range(sent):
                    increment_daily_email_count()
            except Exception as tracking_err:
                logger.warning("Email tracking failed (non-critical): %s", tracking_err)
        
        return sent
