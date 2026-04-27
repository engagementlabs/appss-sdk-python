"""Transport response handling — maps HTTP status codes to dispatcher actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from appss_sdk._types import TransportResponse
from appss_sdk.errors import ErrorCode


class TransportAction(str, Enum):
    """Dispatcher action emitted by :func:`handle_response`."""

    SUCCESS = "SUCCESS"
    DROP = "DROP"
    RETRY = "RETRY"
    SPLIT_AND_RETRY = "SPLIT_AND_RETRY"
    RATE_LIMIT = "RATE_LIMIT"
    STOP = "STOP"


@dataclass(frozen=True, slots=True)
class HandleResult:
    """Outcome of evaluating a :class:`TransportResponse`."""

    action: TransportAction
    retry_after_ms: int | None = None
    error_code: ErrorCode | None = None
    error_message: str | None = None


def handle_response(response: TransportResponse) -> HandleResult:
    """Map an HTTP response to a :class:`HandleResult` for the dispatcher."""
    status_code = response.status_code

    if 200 <= status_code <= 299:
        return HandleResult(action=TransportAction.SUCCESS)

    if status_code == 400:
        return HandleResult(
            action=TransportAction.DROP,
            error_code=ErrorCode.PROTOCOL_ERROR,
            error_message="Bad request",
        )

    if status_code == 401:
        return HandleResult(
            action=TransportAction.STOP,
            error_code=ErrorCode.API_KEY_REVOKED,
            error_message="API key revoked",
        )

    if status_code == 413:
        return HandleResult(action=TransportAction.SPLIT_AND_RETRY)

    if status_code == 429:
        return HandleResult(
            action=TransportAction.RATE_LIMIT,
            retry_after_ms=_parse_retry_after(response.headers),
        )

    if 500 <= status_code <= 599:
        return HandleResult(
            action=TransportAction.RETRY,
            error_code=ErrorCode.NETWORK_ERROR,
            error_message=f"Server error {status_code}",
        )

    return HandleResult(
        action=TransportAction.DROP,
        error_code=ErrorCode.PROTOCOL_ERROR,
        error_message=f"Unexpected status {status_code}",
    )


def _parse_retry_after(headers: dict[str, str]) -> int | None:
    """Parse a ``Retry-After`` header (delta-seconds form only) to milliseconds.

    Lookup is case-insensitive across common header casings. HTTP-date form is
    not supported (matches JS).
    """
    raw = headers.get("retry-after")
    if raw is None:
        raw = headers.get("Retry-After")
    if raw is None:
        return None

    try:
        seconds = float(raw)
    except (TypeError, ValueError):
        return None

    if seconds <= 0:
        return None

    return int(seconds * 1000)
