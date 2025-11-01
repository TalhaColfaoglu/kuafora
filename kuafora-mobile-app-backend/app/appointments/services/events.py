from __future__ import annotations

from typing import Any
from app.appointments.models import NotificationEvent


def emit(topic: str, payload: dict[str, Any]) -> None:
    NotificationEvent.objects.create(topic=topic, payload=payload)


def staff_topic(staff_id: int) -> str:
    return f"staff_{staff_id}"


def shop_topic(shop_id: int) -> str:
    return f"shop_{shop_id}"


