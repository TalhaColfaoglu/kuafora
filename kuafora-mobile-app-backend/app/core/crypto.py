from __future__ import annotations

import re
from typing import Optional

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.crypto import salted_hmac


def _require_phone_key() -> str:
    key = getattr(settings, "PHONE_ENCRYPTION_KEY", "") or ""
    key = key.strip()
    if not key:
        raise ImproperlyConfigured(
            "PHONE_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"`"
        )
    return key


def _get_fernet():
    # Local import so the app can still boot for non-sensitive operations if cryptography is missing,
    # but any phone encrypt/decrypt will fail fast with a clear error.
    try:
        from cryptography.fernet import Fernet  # type: ignore
    except Exception as e:  # pragma: no cover
        raise ImproperlyConfigured(
            "cryptography is required for phone encryption. Install it and retry."
        ) from e

    return Fernet(_require_phone_key().encode())


def encrypt_text(plain: str) -> str:
    plain = (plain or "").strip()
    if not plain:
        return ""
    f = _get_fernet()
    return f.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_text(token: str) -> str:
    token = (token or "").strip()
    if not token:
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:  # pragma: no cover - invalid token / key rotation
        return ""


_NON_PHONE_CHARS = re.compile(r"[^\d+]")


def normalize_phone(raw: str) -> str:
    """Very small normalization for phone numbers.

    - trims
    - removes spaces, dashes, parentheses
    - keeps leading '+' if present, otherwise leaves digits as-is
    """
    s = (raw or "").strip()
    if not s:
        return ""
    s = _NON_PHONE_CHARS.sub("", s)
    # prevent multiple '+' or '+' not at start
    if "+" in s:
        s = "+" + s.replace("+", "")
    return s


def phone_last4(raw: str) -> str:
    s = normalize_phone(raw)
    digits = "".join([c for c in s if c.isdigit()])
    return digits[-4:] if len(digits) >= 4 else digits


def phone_hash(raw: str) -> str:
    """Deterministic hash for lookups/uniqueness without storing plaintext."""
    s = normalize_phone(raw)
    if not s:
        return ""
    return salted_hmac("user-phone", s).hexdigest()


def mask_phone(raw_or_last4: str, *, keep_last: int = 4) -> str:
    """Mask a phone number for display/logs (never return plaintext)."""
    s = (raw_or_last4 or "").strip()
    digits = "".join([c for c in s if c.isdigit()])
    if not digits:
        return ""
    last = digits[-keep_last:] if len(digits) >= keep_last else digits
    return f"***{last}"


