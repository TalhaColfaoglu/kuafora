"""
Gmail API refresh token'ı gerçekten deneyip Google'ın döndüğü hatayı yazdırır.
Sunucuda çalıştırın: python manage.py test_gmail_refresh
"""
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Gmail API refresh token'ı dener ve Google'ın tam hata yanıtını gösterir"

    def handle(self, *args, **options):
        refresh = (getattr(settings, "GMAIL_API_REFRESH_TOKEN", "") or "").strip()
        client_id = (getattr(settings, "GMAIL_API_CLIENT_ID", "") or "").strip()
        client_secret = (getattr(settings, "GMAIL_API_CLIENT_SECRET", "") or "").strip()

        self.stdout.write(f"Token uzunluğu: {len(refresh)}, Client ID: {'var' if client_id else 'yok'}, Client Secret: {'var' if client_secret else 'yok'}")

        if not refresh or not client_id or not client_secret:
            self.stdout.write(self.style.ERROR("Eksik: GMAIL_API_REFRESH_TOKEN, CLIENT_ID veya CLIENT_SECRET boş."))
            return

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google.auth.exceptions import RefreshError

            creds = Credentials(
                token=None,
                refresh_token=refresh,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=["https://www.googleapis.com/auth/gmail.send"],
            )
            creds.refresh(Request())
            self.stdout.write(self.style.SUCCESS("Refresh başarılı. Gmail API kullanılabilir."))
        except RefreshError as e:
            self.stdout.write(self.style.ERROR("RefreshError (invalid_grant vb.):"))
            self.stdout.write(str(e))
            if getattr(e, "args", ()) and len(e.args) >= 2 and isinstance(e.args[1], dict):
                self.stdout.write("Google yanıtı (detay):")
                for k, v in e.args[1].items():
                    self.stdout.write(f"  {k}: {v}")
            self.stdout.write("")
            self.stdout.write("Sık nedenler:")
            self.stdout.write("  1. OAuth izin ekranı 'Testing' modunda: Refresh token 7 gün sonra düşer.")
            self.stdout.write("     Çözüm: Google Cloud Console → API ve Hizmetler → OAuth izin ekranı →")
            self.stdout.write("     'Test kullanıcılar' bölümüne mailleri göndereceğiniz Gmail adresini ekleyin.")
            self.stdout.write("     Veya uygulamayı 'Yayınla' edin (Production).")
            self.stdout.write("  2. Token, farklı Client ID/Secret ile alındı. Playground'da sunucudaki CLIENT_ID ve CLIENT_SECRET ile token alın.")
            self.stdout.write("  3. Token kopyalanırken kesilmiş. OAuth2 Playground'dan tekrar alıp tek satırda yapıştırın.")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Beklenmeyen hata: {type(e).__name__}: {e}"))
