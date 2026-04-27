"""Data types for the SDK."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeAlias

from appss_sdk.errors import AppssError

EventProperties: TypeAlias = dict[str, Any]
UserProperties: TypeAlias = dict[str, Any]

OnErrorCallback: TypeAlias = Callable[[AppssError], None] | Callable[[AppssError], Awaitable[None]]
"""User-supplied error callback. May be sync or async — the client awaits if it's a coroutine."""


@dataclass(frozen=True, slots=True)
class AppssEvent:
    """Internal event representation. Wire format is produced by domain.event.event_to_payload."""

    event: str
    distinct_id: str
    insert_id: str
    timestamp: datetime
    properties: EventProperties | None = None


@dataclass(frozen=True, slots=True)
class TransportResponse:
    """HTTP response structure exposed by ITransport.send."""

    status_code: int
    headers: dict[str, str]
    body: Any = None
