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


def _encrypt(plain: str) -> str | None:
    """Encrypt phone number. Returns None if PHONE_ENCRYPTION_KEY is not set."""
    plain = (plain or "").strip()
    if not plain:
        return ""
    key = (getattr(settings, "PHONE_ENCRYPTION_KEY", "") or "").strip()
    if not key:
        # If key is missing, return None to indicate encryption cannot proceed.
        return None
    from cryptography.fernet import Fernet  # type: ignore
    f = Fernet(key.encode())
    return f.encrypt(plain.encode("utf-8")).decode("utf-8")


def forwards(apps, schema_editor):
    User = apps.get_model("users", "User")
    qs = User.objects.exclude(phone="").filter(phone_encrypted="")
    count = qs.count()
    
    if count == 0:
        # No phones to migrate, skip silently
        return
    
    key = (getattr(settings, "PHONE_ENCRYPTION_KEY", "") or "").strip()
    if not key:
        # PHONE_ENCRYPTION_KEY is not set and there are phones to migrate.
        # Skip encryption to avoid data loss; leave phones in plaintext 'phone' field.
        # Admin/deployer should set PHONE_ENCRYPTION_KEY and re-run this migration data step if needed.
        print(f"⚠️  WARNING: PHONE_ENCRYPTION_KEY is not set. Skipping encryption of {count} phone number(s).")
        print(f"   Phone numbers remain in plaintext 'phone' field. Set PHONE_ENCRYPTION_KEY and re-run this migration if needed.")
        return
    
    # Key is set, proceed with encryption
    for u in qs.iterator():
        n = _normalize_phone(u.phone)
        if not n:
            # clear plaintext anyway
            User.objects.filter(pk=u.pk).update(phone="")
            continue
        encrypted = _encrypt(n)
        if encrypted is None:
            # This should not happen if we checked above, but handle gracefully
            continue
        User.objects.filter(pk=u.pk).update(
            phone_encrypted=encrypted,
            phone_hash=_phone_hash(n),
            phone_last4=_last4(n),
            phone="",
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


