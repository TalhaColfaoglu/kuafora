"""
Sunucuda Gmail API token'ının okunup okunmadığını ve neden invalid_grant
olabileceğini kontrol etmek için. Sadece uzunluk ve maskeli önizleme; token yazdırılmaz.
"""
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Gmail API env değişkenlerinin okunup okunmadığını kontrol eder (token içeriği yazdırılmaz)"

    def handle(self, *args, **options):
        refresh = getattr(settings, "GMAIL_API_REFRESH_TOKEN", "") or ""
        client_id = getattr(settings, "GMAIL_API_CLIENT_ID", "") or ""
        client_secret = getattr(settings, "GMAIL_API_CLIENT_SECRET", "") or ""

        refresh_stripped = refresh.strip()
        len_refresh = len(refresh_stripped)
        preview = f"{refresh_stripped[:12]}...{refresh_stripped[-6:]}" if len_refresh > 20 else "(çok kısa)"

        self.stdout.write("Gmail API ortam değişkenleri (sunucuda okunan):")
        self.stdout.write(f"  GMAIL_API_REFRESH_TOKEN: uzunluk={len_refresh}, önizleme={preview}")
        self.stdout.write(f"  GMAIL_API_CLIENT_ID:     ayarlı={'evet' if client_id.strip() else 'hayır'} ({len(client_id.strip())} karakter)")
        self.stdout.write(f"  GMAIL_API_CLIENT_SECRET: ayarlı={'evet' if client_secret.strip() else 'hayır'} ({len(client_secret.strip())} karakter)")

        env_file = getattr(settings, "_env_file_used", None)
        try:
            from django.conf import settings as s
            env_file_name = ".env.prod" if __import__("os").environ.get("DJANGO_ENV") == "production" else ".env"
            self.stdout.write(f"  Okunan env dosyası:      {env_file_name} (DJANGO_ENV={__import__('os').environ.get('DJANGO_ENV', '(boş)')})")
        except Exception:
            pass

        if len_refresh < 50:
            self.stdout.write(self.style.WARNING("\nUyarı: Refresh token çok kısa; muhtemelen kesilmiş veya yanlış. OAuth2 Playground'dan tam token'ı kopyalayın."))
        if not client_id.strip() or not client_secret.strip():
            self.stdout.write(self.style.ERROR("\nHata: CLIENT_ID veya CLIENT_SECRET boş. Token, token'ı üretirken kullandığınız OAuth istemcisiyle eşleşmeli."))

        self.stdout.write("\ninvalid_grant devam ediyorsa kontrol listesi:")
        self.stdout.write("  1. Token'ı OAuth2 Playground'da 'Use your own OAuth credentials' ile aldınız mı? (Client ID/Secret Playground'da ve .env'de AYNI olmalı)")
        self.stdout.write("  2. Scope: https://www.googleapis.com/auth/gmail.send seçili mi?")
        self.stdout.write("  3. .env mi .env.prod mu? Docker'da DJANGO_ENV=production ise .env.prod okunur; token'ı oraya yazın veya compose'da env_file/environment ile verin.")
        self.stdout.write("  4. Container/process yeniden başlatıldı mı? (docker compose restart)")
        self.stdout.write("  5. Token tek satırda, tırnak içinde veya dışında; başında/sonunda boşluk veya satır sonu yok.")
        self.stdout.write("")
