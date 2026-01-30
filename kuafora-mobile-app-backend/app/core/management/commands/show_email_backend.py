"""
Hangi e-posta backend'inin kullanıldığını gösterir (Gmail API / SMTP / console / dummy).
"""
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Show which email backend is currently active (Gmail API, SMTP, console, or dummy)"

    def handle(self, *args, **options):
        backend = getattr(settings, "EMAIL_BACKEND", "")
        gmail_enabled = getattr(settings, "GMAIL_API_ENABLED", False)
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")

        self.stdout.write(f"EMAIL_BACKEND: {backend}")
        self.stdout.write(f"GMAIL_API_ENABLED: {gmail_enabled}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL: {from_email or '(not set)'}")

        if "gmail_api_backend" in backend:
            self.stdout.write(self.style.SUCCESS("\n✓ Gmail API backend is active. Emails will be sent via Google Gmail API."))
        elif "smtp" in backend:
            self.stdout.write(self.style.WARNING("\n○ SMTP backend is active. Gmail API env vars are missing or incomplete."))
        elif "console" in backend:
            self.stdout.write(self.style.WARNING("\n○ Console backend: emails are printed to stdout (DEBUG)."))
        else:
            self.stdout.write(self.style.WARNING("\n○ Dummy or other backend: emails are not actually sent."))
