"""Event construction and wire-format serialization."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from appss_sdk._types import AppssEvent, EventProperties


def build_event(
    *,
    event: str,
    distinct_id: str,
    properties: EventProperties | None = None,
) -> AppssEvent:
    """Construct an :class:`AppssEvent` with a fresh UUID and current UTC timestamp."""
    if event.strip() == "":
        raise ValueError("Event name is required and cannot be empty.")

    return AppssEvent(
        event=event,
        distinct_id=distinct_id,
        insert_id=str(uuid.uuid4()),
        timestamp=datetime.now(tz=timezone.utc),
        properties=properties,
    )


def event_to_payload(event: AppssEvent) -> dict[str, Any]:
    """Serialize an :class:`AppssEvent` to its wire-format dict.

    The ``properties`` key is omitted when there are no properties (matches JS:
    ``if (Object.keys(properties).length > 0)``).
    """
    payload: dict[str, Any] = {
        "event": event.event,
        "distinct_id": event.distinct_id,
        "$insert_id": event.insert_id,
        "timestamp": event.timestamp.isoformat(),
    }
    if event.properties:
        payload["properties"] = event.properties
    return payload
