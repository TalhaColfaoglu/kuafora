from __future__ import annotations

import json
import os
from typing import Iterable

from django.conf import settings

from .models import DevicePushToken


def _load_fcm_credentials():
    """
    Supported configurations (prefer JSON env to avoid file mounts):
    - FCM_SERVICE_ACCOUNT_JSON: full service account json string
    - FCM_SERVICE_ACCOUNT_PATH: path to json file on disk
    """
    raw = (getattr(settings, "FCM_SERVICE_ACCOUNT_JSON", "") or os.getenv("FCM_SERVICE_ACCOUNT_JSON", "")).strip()
    if raw:
        return json.loads(raw)
    path = (getattr(settings, "FCM_SERVICE_ACCOUNT_PATH", "") or os.getenv("FCM_SERVICE_ACCOUNT_PATH", "")).strip()
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _get_firebase_app():
    # Lazy init to avoid import cost on non-push code paths.
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:  # type: ignore[attr-defined]
        return firebase_admin.get_app()

    creds = _load_fcm_credentials()
    if not creds:
        raise RuntimeError("FCM credentials not configured (FCM_SERVICE_ACCOUNT_JSON/PATH).")

    cred_obj = credentials.Certificate(creds)
    return firebase_admin.initialize_app(cred_obj)


def send_push_to_tokens(
    tokens: Iterable[str],
    *,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> dict:
    """
    Send a push to many tokens (chunked for FCM limits).
    Returns summary dict.
    """
    _get_firebase_app()
    from firebase_admin import messaging

    tokens_list = [t for t in tokens if t]
    if not tokens_list:
        return {"success": 0, "failure": 0, "invalid_tokens": 0}

    success = 0
    failure = 0
    invalid_tokens = 0

    # FCM multicast limit: 500 tokens per request.
    for i in range(0, len(tokens_list), 500):
        chunk = tokens_list[i : i + 500]
        msg = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            tokens=chunk,
        )
        resp = messaging.send_multicast(msg)
        success += resp.success_count
        failure += resp.failure_count

        # Deactivate invalid tokens.
        bad = []
        for idx, r in enumerate(resp.responses):
            if r.success:
                continue
            err = getattr(r, "exception", None)
            code = getattr(err, "code", "") if err else ""
            if code in {"invalid-argument", "registration-token-not-registered"}:
                bad.append(chunk[idx])
        if bad:
            invalid_tokens += len(bad)
            DevicePushToken.objects.filter(token__in=bad).update(is_active=False)

    return {"success": success, "failure": failure, "invalid_tokens": invalid_tokens}


def active_tokens_for_users(user_ids: Iterable[int]) -> list[str]:
    qs = DevicePushToken.objects.filter(user_id__in=list(user_ids), is_active=True).values_list("token", flat=True)
    return list(qs)

