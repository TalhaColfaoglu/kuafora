#!/usr/bin/env python
"""
Container içinde management command olmadan Gmail API env ve refresh testi.
Kullanım (sunucuda): docker compose exec backend_dev python /app/scripts/check_gmail_in_container.py
"""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.conf import settings

def main():
    r = (getattr(settings, "GMAIL_API_REFRESH_TOKEN", "") or "").strip()
    cid = (getattr(settings, "GMAIL_API_CLIENT_ID", "") or "").strip()
    csec = (getattr(settings, "GMAIL_API_CLIENT_SECRET", "") or "").strip()

    print("Gmail API (container içinde okunan):")
    print(f"  GMAIL_API_REFRESH_TOKEN: length={len(r)}, preview={r[:12]}...{r[-6:] if len(r) > 20 else '(kısa)'}")
    print(f"  GMAIL_API_CLIENT_ID:     set={bool(cid)}, len={len(cid)}")
    print(f"  GMAIL_API_CLIENT_SECRET: set={bool(csec)}, len={len(csec)}")

    if not r or not cid or not csec:
        print("\nEksik: Token, Client ID veya Client Secret boş. env/backend.dev.env dosyasını kontrol edin.")
        sys.exit(1)

    if len(r) < 50:
        print("\nUyarı: Token çok kısa; kesilmiş olabilir.")

    print("\nRefresh deniyor...")
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        creds = Credentials(
            token=None,
            refresh_token=r,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=cid,
            client_secret=csec,
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )
        creds.refresh(Request())
        print("OK: Refresh başarılı. Gmail API kullanılabilir.")
    except Exception as e:
        print(f"HATA: {e}")
        if getattr(e, "args", ()) and len(e.args) >= 2 and isinstance(e.args[1], dict):
            print("Google yanıtı:", e.args[1])
        print("\ninvalid_grant ise: Token'ı env/backend.dev.env'deki Client ID/Secret ile OAuth2 Playground'dan yeniden alın.")
        sys.exit(1)

if __name__ == "__main__":
    main()
