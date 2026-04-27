"""Concrete :class:`AppssClient` — public facade for server-side analytics.

Subclass of :class:`BaseAppssClient` that wires concrete adapters:
:class:`HttpxTransport`, :class:`MemoryQueue`, :class:`StdoutLogger` /
:class:`NoopLogger`, and a POSIX :class:`ShutdownHandler`.
"""

from __future__ import annotations

from typing import Any

from appss_sdk._adapters.lifecycle import ShutdownHandler
from appss_sdk._adapters.logger import NoopLogger, StdoutLogger
from appss_sdk._adapters.queue import MemoryQueue
from appss_sdk._adapters.transport import HttpxTransport
from appss_sdk._composition.abstract import BaseAppssClient
from appss_sdk._config import AppssConfig, ResolvedConfig
from appss_sdk._ports import IEventQueue, ILogger, ITransport

SDK_PLATFORM = "python"


class AppssClient(BaseAppssClient):
    """APPSS analytics client for Python (async).

    Stamps every outgoing event with a ``$lib`` super-property identifying the
    SDK platform, so the server can attribute traffic to the Python SDK.
    """

    def __init__(self, config: AppssConfig | dict[str, Any]) -> None:
        self._shutdown_handler: ShutdownHandler | None = None
        super().__init__(config)
        self.set_super_properties({"$lib": SDK_PLATFORM})

    def _create_transport(self, config: ResolvedConfig) -> ITransport:
        return HttpxTransport(config.endpoint, config.request_timeout_ms)

    def _create_queue(self, config: ResolvedConfig) -> IEventQueue:
        return MemoryQueue(max_size=config.max_queue_size)

    def _create_logger(self, config: ResolvedConfig) -> ILogger:
        return StdoutLogger() if config.debug else NoopLogger()

    def _register_lifecycle_handlers(self) -> None:
        self._shutdown_handler = ShutdownHandler(self.flush)
        self._shutdown_handler.register()

    def _unregister_lifecycle_handlers(self) -> None:
        if self._shutdown_handler is not None:
            self._shutdown_handler.unregister()
            self._shutdown_handler = None

    async def destroy(self) -> None:
        """Flush pending events, stop background loops, and close the HTTP client."""
        transport = self._transport
        await super().destroy()
        if isinstance(transport, HttpxTransport):
            await transport.aclose()


def create_appss(config: AppssConfig | dict[str, Any]) -> AppssClient:
    """Factory function — creates and initializes an :class:`AppssClient`.

    Equivalent to ``AppssClient(config)``; provided as a convenience for code
    that prefers a factory style over direct instantiation.
    """
    return AppssClient(config)
