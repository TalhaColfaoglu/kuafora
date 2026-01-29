from __future__ import annotations

from django.conf import settings
from django.db import migrations, models
from django.utils.crypto import salted_hmac


def _normalize_phone(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    # keep digits and '+'
    out = []
    for ch in s:
        if ch.isdigit() or ch == "+":
            out.append(ch)
    s = "".join(out)
    if "+" in s:
        s = "+" + s.replace("+", "")
    return s


def _last4(raw: str) -> str:
    s = _normalize_phone(raw)
    digits = "".join([c for c in s if c.isdigit()])
    return digits[-4:] if len(digits) >= 4 else digits


def _phone_hash(raw: str) -> str:
    s = _normalize_phone(raw)
    if not s:
        return ""
    return salted_hmac("user-phone", s).hexdigest()


def _encrypt(plain: str) -> str:
    plain = (plain or "").strip()
    if not plain:
        return ""
    key = (getattr(settings, "PHONE_ENCRYPTION_KEY", "") or "").strip()
    if not key:
        print("⚠️  WARNING: PHONE_ENCRYPTION_KEY is not set. Skipping phone encryption in migration.")
        print("   Generate one: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        return ""
    try:
        from cryptography.fernet import Fernet  # type: ignore
        f = Fernet(key.encode())
        return f.encrypt(plain.encode("utf-8")).decode("utf-8")
    except (ValueError, Exception) as e:
        # Invalid key (wrong format, padding, etc.): skip encryption so migration can complete
        print("⚠️  WARNING: PHONE_ENCRYPTION_KEY is invalid (e.g. wrong format). Skipping phone encryption.")
        print("   Generate a valid key: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        return ""


def _is_valid_fernet_key(key: str) -> bool:
    if not key:
        return False
    try:
        from cryptography.fernet import Fernet  # type: ignore
        Fernet(key.encode())
        return True
    except (ValueError, Exception):
        return False


def forwards(apps, schema_editor):
    User = apps.get_model("users", "User")
    qs = User.objects.exclude(phone="").filter(phone_encrypted="")
    key = (getattr(settings, "PHONE_ENCRYPTION_KEY", "") or "").strip()
    has_key = _is_valid_fernet_key(key)
    if key and not has_key:
        print("⚠️  WARNING: PHONE_ENCRYPTION_KEY is invalid. Phones will stay in plaintext until a valid key is set.")
    
    for u in qs.iterator():
        n = _normalize_phone(u.phone)
        if not n:
            # clear plaintext anyway
            User.objects.filter(pk=u.pk).update(phone="")
            continue
        
        encrypted = _encrypt(n) if has_key else ""
        # If no key, keep phone in plaintext temporarily (will be encrypted when key is added)
        if has_key and encrypted:
            User.objects.filter(pk=u.pk).update(
                phone_encrypted=encrypted,
                phone_hash=_phone_hash(n),
                phone_last4=_last4(n),
                phone="",  # Clear plaintext only if encryption succeeded
            )
        else:
            # Key missing: keep phone in plaintext, but set hash/last4 for uniqueness checks
            User.objects.filter(pk=u.pk).update(
                phone_hash=_phone_hash(n),
                phone_last4=_last4(n),
                # phone stays in plaintext until key is added and data migration runs
            )


def backwards(apps, schema_editor):
    # We intentionally do NOT restore plaintext phone numbers.
    User = apps.get_model("users", "User")
    User.objects.all().update(phone="")


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0010_user_requires_email_verification"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="phone_encrypted",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="user",
            name="phone_hash",
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="user",
            name="phone_last4",
            field=models.CharField(blank=True, default="", max_length=4),
        ),
        migrations.RunPython(forwards, backwards),
    ]


