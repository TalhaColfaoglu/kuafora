from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from app.appointments.models import IdempotencyKey
import json


def _hash_payload(method: str, path: str, body: dict) -> str:
    raw = f"{method}|{path}|{sorted(body.items())}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def ensure_idempotent(*, key: str, actor: str, method: str, path: str, body: dict, ttl_seconds: int = 86400):
    now = timezone.now()
    request_hash = _hash_payload(method, path, body)
    with transaction.atomic():
        obj, created = IdempotencyKey.objects.select_for_update().get_or_create(
            key=key,
            defaults={
                "actor": actor,
                "request_hash": request_hash,
                "expires_at": now + timedelta(seconds=ttl_seconds),
            },
        )
        if not created:
            # If same request hash and not expired, return existing response
            if obj.request_hash == request_hash and obj.expires_at > now:
                return obj.response_json
            # else: update request hash and extend TTL
            obj.request_hash = request_hash
            obj.expires_at = now + timedelta(seconds=ttl_seconds)
            obj.save(update_fields=["request_hash", "expires_at"])
    return None


def store_idempotent_response(*, key: str, response_json: dict):
    # Ensure JSON is serializable (convert UUID/Decimal/Date to str)
    try:
        safe = json.loads(json.dumps(response_json, default=str))
    except Exception:
        # Fallback: store stringified
        safe = {"raw": str(response_json)}
    IdempotencyKey.objects.filter(key=key).update(response_json=safe)


