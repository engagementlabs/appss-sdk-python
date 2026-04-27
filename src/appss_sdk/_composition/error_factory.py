"""Map ``ErrorCode`` to concrete ``AppssError`` subclasses for transport failures.

``QUEUE_OVERFLOW`` is intentionally absent — that error originates inside the queue
adapter where ``dropped_count`` is known.
"""

from __future__ import annotations

from appss_sdk.errors import (
    ApiKeyRevokedError,
    AppssError,
    ErrorCode,
    InvalidApiKeyError,
    MaxRetriesExceededError,
    NetworkError,
    ProtocolError,
    RateLimitError,
)


def create_transport_error(
    code: ErrorCode,
    message: str | None = None,
    retry_after_ms: int | None = None,
) -> AppssError:
    """Construct the ``AppssError`` subclass that matches ``code``."""
    if code is ErrorCode.NETWORK_ERROR:
        return NetworkError(message) if message is not None else NetworkError()
    if code is ErrorCode.RATE_LIMITED:
        if message is not None:
            return RateLimitError(message, retry_after_ms=retry_after_ms)
        return RateLimitError(retry_after_ms=retry_after_ms)
    if code is ErrorCode.API_KEY_REVOKED:
        return ApiKeyRevokedError(message) if message is not None else ApiKeyRevokedError()
    if code is ErrorCode.PROTOCOL_ERROR:
        return ProtocolError(message) if message is not None else ProtocolError()
    if code is ErrorCode.INVALID_API_KEY:
        return InvalidApiKeyError(message) if message is not None else InvalidApiKeyError()
    if code is ErrorCode.MAX_RETRIES_EXCEEDED:
        return (
            MaxRetriesExceededError(message) if message is not None else MaxRetriesExceededError()
        )
    return ProtocolError(message or f"Transport error: {code.value}")
