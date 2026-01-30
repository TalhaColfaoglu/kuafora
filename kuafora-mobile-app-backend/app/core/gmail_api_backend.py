"""
Django email backend that sends mail via Gmail API (OAuth2 refresh token).
SMTP yerine Google API ile gönderim için: GMAIL_API_* ortam değişkenlerini ayarlayın.
"""
import base64
import logging
from email.generator import BytesGenerator
from io import BytesIO

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class GmailAPIEmailBackend(BaseEmailBackend):
    """
    Gmail API ile e-posta gönderir.
    OAuth2 refresh token ile yetkilendirme (Gmail veya Google Workspace).
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self._service = None

    def _get_service(self):
        if self._service is not None:
            return self._service
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            refresh_token = getattr(settings, "GMAIL_API_REFRESH_TOKEN", "").strip()
            client_id = getattr(settings, "GMAIL_API_CLIENT_ID", "").strip()
            client_secret = getattr(settings, "GMAIL_API_CLIENT_SECRET", "").strip()
            if not refresh_token or not client_id or not client_secret:
                raise ValueError("GMAIL_API_REFRESH_TOKEN, GMAIL_API_CLIENT_ID, GMAIL_API_CLIENT_SECRET are required")

            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=["https://www.googleapis.com/auth/gmail.send"],
            )
            if not creds.valid:
                try:
                    creds.refresh(Request())
                except Exception as refresh_err:  # noqa: BLE001
                    err_str = str(refresh_err).lower()
                    if "invalid_grant" in err_str or "refresherror" in type(refresh_err).__name__.lower():
                        logger.error(
                            "Gmail API: Refresh token geçersiz veya süresi dolmuş (invalid_grant). "
                            "OAuth2 Playground ile yeni refresh token alın: GMAIL_API_SETUP.md"
                        )
                    raise
            self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            return self._service
        except Exception as e:
            logger.exception("Gmail API service build failed: %s", e)
            if not self.fail_silently:
                raise
            return None

    def _email_to_raw(self, email_message):
        """Django EmailMessage -> RFC 2822 bytes -> base64url (Gmail API raw)."""
        msg = email_message.message()
        buf = BytesIO()
        g = BytesGenerator(buf, mangle_from_=False)
        g.flatten(msg, linesep="\r\n")
        raw_bytes = buf.getvalue()
        return base64.urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("=")

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        service = self._get_service()
        if service is None:
            return 0
        sent = 0
        for email_message in email_messages:
            try:
                raw = self._email_to_raw(email_message)
                service.users().messages().send(userId="me", body={"raw": raw}).execute()
                sent += 1
            except Exception as e:
                logger.exception("Gmail API send failed: %s", e)
                if not self.fail_silently:
                    raise
        return sent
