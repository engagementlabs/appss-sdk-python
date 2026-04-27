"""Port (interface) definitions for transport, queue, and logger.

Concrete adapters live in :mod:`appss_sdk._adapters`.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from appss_sdk._types import AppssEvent, TransportResponse


@runtime_checkable
class ITransport(Protocol):
    """HTTP transport contract. Implementations send a JSON POST and return the parsed response."""

    async def send(
        self,
        path: str,
        body: Any,
        headers: dict[str, str],
    ) -> TransportResponse: ...


@runtime_checkable
class IEventQueue(Protocol):
    """Event queue contract. FIFO with peek (non-destructive) and drain (destructive)."""

    def enqueue(self, event: AppssEvent) -> None: ...
    def drain(self, max_count: int) -> list[AppssEvent]: ...
    def peek(self, max_count: int) -> list[AppssEvent]: ...
    def size(self) -> int: ...
    def is_empty(self) -> bool: ...
    def clear(self) -> None: ...


@runtime_checkable
class ILogger(Protocol):
    """Structured 4-level logger."""

    def debug(self, message: str, context: dict[str, Any] | None = None) -> None: ...
    def info(self, message: str, context: dict[str, Any] | None = None) -> None: ...
    def warn(self, message: str, context: dict[str, Any] | None = None) -> None: ...
    def error(self, message: str, context: dict[str, Any] | None = None) -> None: ...
