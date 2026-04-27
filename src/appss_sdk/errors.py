"""SDK error hierarchy.

Each error carries a stable :class:`ErrorCode`, a :data:`ErrorSeverity` (``"warn"``
or ``"error"``), and a ``retryable`` flag. User-supplied ``on_error`` callbacks
receive concrete :class:`AppssError` subclasses and can dispatch on ``code`` or
``isinstance`` checks.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

ErrorSeverity = Literal["warn", "error"]


class ErrorCode(str, Enum):
    """Stable error codes exposed to user callbacks.

    Values equal their names so that ``ErrorCode.NETWORK_ERROR == "NETWORK_ERROR"``
    holds, allowing callbacks to dispatch on the string code or the enum member
    interchangeably.
    """

    NOT_INITIALIZED = "NOT_INITIALIZED"
    NOT_IDENTIFIED = "NOT_IDENTIFIED"
    INVALID_API_KEY = "INVALID_API_KEY"
    NETWORK_ERROR = "NETWORK_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    API_KEY_REVOKED = "API_KEY_REVOKED"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    QUEUE_OVERFLOW = "QUEUE_OVERFLOW"
    MAX_RETRIES_EXCEEDED = "MAX_RETRIES_EXCEEDED"


class AppssError(Exception):
    """Base class for all SDK errors."""

    def __init__(
        self,
        message: str,
        code: ErrorCode,
        severity: ErrorSeverity,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self._code = code
        self._severity: ErrorSeverity = severity
        self._retryable = retryable

    @property
    def code(self) -> ErrorCode:
        return self._code

    @property
    def severity(self) -> ErrorSeverity:
        return self._severity

    @property
    def retryable(self) -> bool:
        return self._retryable


class NotInitializedError(AppssError):
    def __init__(self, message: str = "SDK not initialized. Call init() first.") -> None:
        super().__init__(message, ErrorCode.NOT_INITIALIZED, "warn", False)


class NotIdentifiedError(AppssError):
    def __init__(self, message: str = "User not identified. Call identify() first.") -> None:
        super().__init__(message, ErrorCode.NOT_IDENTIFIED, "warn", False)


class InvalidApiKeyError(AppssError):
    def __init__(self, message: str = "Invalid or missing API key.") -> None:
        super().__init__(message, ErrorCode.INVALID_API_KEY, "error", False)


class NetworkError(AppssError):
    def __init__(self, message: str = "Network request failed.") -> None:
        super().__init__(message, ErrorCode.NETWORK_ERROR, "warn", True)


class RateLimitError(AppssError):
    def __init__(
        self,
        message: str = "Rate limited by server.",
        retry_after_ms: int | None = None,
    ) -> None:
        super().__init__(message, ErrorCode.RATE_LIMITED, "warn", True)
        self._retry_after_ms = retry_after_ms

    @property
    def retry_after_ms(self) -> int | None:
        return self._retry_after_ms


class ApiKeyRevokedError(AppssError):
    def __init__(self, message: str = "API key has been revoked.") -> None:
        super().__init__(message, ErrorCode.API_KEY_REVOKED, "error", False)


class ProtocolError(AppssError):
    def __init__(self, message: str = "Protocol error: server rejected the request.") -> None:
        super().__init__(message, ErrorCode.PROTOCOL_ERROR, "error", False)


class QueueOverflowError(AppssError):
    def __init__(self, dropped_count: int) -> None:
        message = f"Queue overflow: dropped {dropped_count} oldest events."
        super().__init__(message, ErrorCode.QUEUE_OVERFLOW, "warn", False)
        self._dropped_count = dropped_count

    @property
    def dropped_count(self) -> int:
        return self._dropped_count


class MaxRetriesExceededError(AppssError):
    def __init__(self, message: str = "Max retries exceeded. Batch dropped.") -> None:
        super().__init__(message, ErrorCode.MAX_RETRIES_EXCEEDED, "error", False)
