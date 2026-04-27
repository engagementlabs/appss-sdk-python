"""Periodic flush policy with in-flight deduplication.

Drives a callback at a fixed interval and dedups concurrent ``flush()`` calls so
the underlying transport is never invoked twice in parallel.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable


class FlushPolicy:
    """Schedule a callback at a fixed interval with in-flight dedup.

    The callback is supplied to :meth:`start` (not the constructor), and the
    policy holds no reference to a queue or transport — only the callback.
    """

    def __init__(self, interval_ms: int) -> None:
        self._interval_ms = interval_ms
        self._flush_fn: Callable[[], Awaitable[None]] | None = None
        self._loop_task: asyncio.Task[None] | None = None
        self._flush_task: asyncio.Task[None] | None = None
        self._wakeup: asyncio.Event | None = None
        self._stopped: bool = False

    def start(self, flush_fn: Callable[[], Awaitable[None]]) -> None:
        """Begin the periodic loop. No-op if already started."""
        if self._loop_task is not None and not self._loop_task.done():
            return
        self._flush_fn = flush_fn
        self._stopped = False
        self._wakeup = asyncio.Event()
        self._loop_task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        """Stop the loop. Safe to call multiple times."""
        self._stopped = True
        if self._loop_task is not None and not self._loop_task.done():
            self._loop_task.cancel()
        self._loop_task = None
        if self._wakeup is not None:
            self._wakeup.set()

    def reset(self) -> None:
        """Wake the loop so the next interval starts fresh from "now".

        Called after a successful flush so that the next periodic tick is
        measured from the flush time, not from the previous tick.
        """
        if self._wakeup is not None:
            self._wakeup.set()

    async def flush(self) -> None:
        """Invoke the callback once, deduplicating concurrent calls.

        If a flush is already in flight, await its completion instead of
        starting a second concurrent invocation.
        """
        if self._flush_fn is None:
            return

        existing = self._flush_task
        if existing is not None and not existing.done():
            await asyncio.shield(existing)
            return

        fn = self._flush_fn

        async def _run() -> None:
            await fn()

        task: asyncio.Task[None] = asyncio.create_task(_run())
        self._flush_task = task
        try:
            await task
        finally:
            if self._flush_task is task:
                self._flush_task = None

    async def _loop(self) -> None:
        assert self._wakeup is not None
        interval_s = self._interval_ms / 1000
        while True:
            if self._stopped:
                return
            self._wakeup.clear()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._wakeup.wait(), timeout=interval_s)
            # Periodic ticks must never crash the loop; surfacing errors is the
            # dispatcher's responsibility via the user on_error callback.
            with contextlib.suppress(Exception):
                if not self._stopped:
                    await self.flush()
