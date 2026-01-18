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
        # If key is missing in a target environment, fail fast rather than store plaintext.
        raise RuntimeError("PHONE_ENCRYPTION_KEY is not set; cannot migrate phone numbers securely.")
    from cryptography.fernet import Fernet  # type: ignore
    f = Fernet(key.encode())
    return f.encrypt(plain.encode("utf-8")).decode("utf-8")


def forwards(apps, schema_editor):
    User = apps.get_model("users", "User")
    qs = User.objects.exclude(phone="").filter(phone_encrypted="")
    for u in qs.iterator():
        n = _normalize_phone(u.phone)
        if not n:
            # clear plaintext anyway
            User.objects.filter(pk=u.pk).update(phone="")
            continue
        User.objects.filter(pk=u.pk).update(
            phone_encrypted=_encrypt(n),
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


