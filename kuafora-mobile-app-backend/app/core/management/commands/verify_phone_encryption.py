"""
Telefon şifreleme anahtarının çalıştığını doğrular.

Kullanım:
  python manage.py verify_phone_encryption

PHONE_ENCRYPTION_KEY .env veya .env.prod içinde olmalı (backend root).
Anahtar yoksa veya geçersizse hata verir; encrypt/decrypt testi başarılıysa OK yazar.
"""
from django.core.management.base import BaseCommand

from app.core.crypto import encrypt_text, decrypt_text, _require_phone_key


class Command(BaseCommand):
    help = "PHONE_ENCRYPTION_KEY'in ayarlı ve çalışır olduğunu doğrular."

    def handle(self, *args, **options):
        key = _require_phone_key()
        if not key:
            self.stderr.write(
                self.style.ERROR(
                    "PHONE_ENCRYPTION_KEY ayarlı değil veya geçersiz. "
                    "Anahtar oluşturmak için: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
            )
            return

        self.stdout.write("PHONE_ENCRYPTION_KEY ayarlı ve format geçerli.")

        test_phone = "+905551234567"
        encrypted = encrypt_text(test_phone)
        if not encrypted:
            self.stderr.write(self.style.ERROR("Şifreleme başarısız (boş dönüş)."))
            return

        decrypted = decrypt_text(encrypted)
        if decrypted != test_phone:
            self.stderr.write(
                self.style.ERROR(f"Şifre çözme uyuşmuyor: beklenen {test_phone!r}, alınan {decrypted!r}")
            )
            return

        self.stdout.write(self.style.SUCCESS("Encrypt/decrypt testi başarılı. Telefon şifrelemesi çalışıyor."))
