"""
Admin paneline giriş için kullanıcıyı staff/superuser yapar.
Kullanım: python manage.py make_staff kullanici@email.com
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Belirtilen e-posta adresine sahip kullanıcıyı admin paneline giriş yapabilir hale getirir (is_staff=True, is_superuser=True)."

    def add_arguments(self, parser):
        parser.add_argument("email", type=str, help="Kullanıcının e-posta adresi")

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        if not email:
            self.stderr.write(self.style.ERROR("E-posta adresi gerekli."))
            return

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Bu e-posta ile kayıtlı kullanıcı bulunamadı: {email}"))
            return

        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])

        self.stdout.write(
            self.style.SUCCESS(f"'{email}' artık admin paneline giriş yapabilir (is_staff=True, is_superuser=True).")
        )
