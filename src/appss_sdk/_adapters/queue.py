"""In-memory FIFO queue adapter."""

from __future__ import annotations

import contextlib
from collections.abc import Callable

from appss_sdk._types import AppssEvent


class MemoryQueue:
    """IEventQueue implementation backed by an in-process list.

    On overflow the oldest items are dropped (FIFO) and ``on_overflow`` is
    invoked with the dropped count. Exceptions raised by the callback are
    swallowed so a misbehaving callback cannot break ``enqueue``.
    """

    def __init__(
        self,
        max_size: int,
        on_overflow: Callable[[int], None] | None = None,
    ) -> None:
        self._items: list[AppssEvent] = []
        self._max_size = max_size
        self._on_overflow = on_overflow

    def enqueue(self, event: AppssEvent) -> None:
        self._items.append(event)
        if len(self._items) > self._max_size:
            dropped_count = len(self._items) - self._max_size
            self._items = self._items[dropped_count:]
            if self._on_overflow is not None:
                with contextlib.suppress(Exception):
                    self._on_overflow(dropped_count)

    def drain(self, max_count: int) -> list[AppssEvent]:
        out = self._items[:max_count]
        self._items = self._items[max_count:]
        return out

    def peek(self, max_count: int) -> list[AppssEvent]:
        return list(self._items[:max_count])

    def size(self) -> int:
        return len(self._items)

    def is_empty(self) -> bool:
        return not self._items

    def clear(self) -> None:
        self._items.clear()
