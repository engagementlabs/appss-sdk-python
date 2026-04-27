"""Process-lifecycle adapter: SIGTERM/SIGINT shutdown handler."""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import warnings
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any


class ShutdownHandler:
    """Registers OS signal handlers that flush a queue before process exit.

    On Windows, ``loop.add_signal_handler`` is unavailable; ``register`` emits a
    warning and becomes a no-op rather than failing. A watchdog forces a hard
    ``os._exit`` if the flush doesn't complete within ``timeout_ms``.
    """

    def __init__(
        self,
        flush_fn: Callable[[], Awaitable[None]],
        *,
        timeout_ms: int = 5000,
    ) -> None:
        self._flush_fn = flush_fn
        self._timeout_ms = timeout_ms
        self._registered: bool = False
        self._in_progress: bool = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: set[asyncio.Task[None]] = set()

    def register(self) -> None:
        if self._registered:
            return

        if sys.platform == "win32":
            warnings.warn(
                "ShutdownHandler: signal handlers are not supported on Windows; "
                "skipping registration.",
                stacklevel=2,
            )
            return

        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, self._on_signal)
        loop.add_signal_handler(signal.SIGINT, self._on_signal)
        self._loop = loop
        self._registered = True

    def unregister(self) -> None:
        if self._loop is None or not self._registered:
            return
        if sys.platform != "win32":
            self._loop.remove_signal_handler(signal.SIGTERM)
            self._loop.remove_signal_handler(signal.SIGINT)
        self._registered = False

    def _on_signal(self) -> None:
        if self._in_progress:
            return
        self._in_progress = True
        self._spawn(self._handle_shutdown())

    async def _handle_shutdown(self) -> None:
        self._spawn(self._force_exit_after(self._timeout_ms))
        try:
            await self._flush_fn()
            sys.exit(0)
        except Exception:
            sys.exit(1)

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _force_exit_after(self, ms: int) -> None:
        await asyncio.sleep(ms / 1000)
        os._exit(1)
