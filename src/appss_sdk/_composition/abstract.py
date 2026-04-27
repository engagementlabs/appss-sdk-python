"""Abstract async client.

Subclasses provide the I/O bindings (transport / queue / logger / lifecycle); this
class owns orchestration: enrichment, queueing, batch flushing, retry, and error
fan-out to the user-supplied ``on_error`` callback.
"""

from __future__ import annotations

import abc
import asyncio
import contextlib
import inspect
from collections.abc import Awaitable
from typing import Any

from appss_sdk._composition.dispatcher import BatchDispatcher
from appss_sdk._composition.enricher import EventEnricher
from appss_sdk._composition.headers import build_headers
from appss_sdk._config import AppssConfig, ResolvedConfig, resolve_config, validate_config
from appss_sdk._constants import EVENTS_PATH, USER_PROPERTIES_PATH
from appss_sdk._domain.event import build_event, event_to_payload
from appss_sdk._domain.flush import FlushPolicy
from appss_sdk._domain.retry import RetryPolicy
from appss_sdk._ports import IEventQueue, ILogger, ITransport
from appss_sdk.errors import AppssError, ErrorCode, NotInitializedError


class BaseAppssClient(abc.ABC):
    """Async-only base client. Subclasses bind concrete adapters."""

    def __init__(self, config: AppssConfig | dict[str, Any]) -> None:
        self._config: ResolvedConfig | None = None
        self._logger: ILogger | None = None
        self._transport: ITransport | None = None
        self._queue: IEventQueue | None = None
        self._dispatcher: BatchDispatcher | None = None
        self._flush_policy: FlushPolicy | None = None
        self._initialized: bool = False
        self._enricher: EventEnricher = EventEnricher()
        self._pending_tasks: set[asyncio.Task[None]] = set()
        self.init(config)

    # ------------------------------------------------------------------
    # Abstract DI hooks
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def _create_transport(self, config: ResolvedConfig) -> ITransport: ...

    @abc.abstractmethod
    def _create_queue(self, config: ResolvedConfig) -> IEventQueue: ...

    @abc.abstractmethod
    def _create_logger(self, config: ResolvedConfig) -> ILogger: ...

    @abc.abstractmethod
    def _register_lifecycle_handlers(self) -> None: ...

    @abc.abstractmethod
    def _unregister_lifecycle_handlers(self) -> None: ...

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init(self, config: AppssConfig | dict[str, Any]) -> None:
        if self._initialized:
            self._destroy_sync()

        validate_config(config)
        appss_config = config if isinstance(config, AppssConfig) else AppssConfig(**config)
        resolved = resolve_config(appss_config)
        self._config = resolved
        self._logger = resolved.logger or self._create_logger(resolved)
        self._transport = self._create_transport(resolved)
        self._queue = resolved.queue or self._create_queue(resolved)
        self._dispatcher = BatchDispatcher(
            self._transport,
            RetryPolicy(resolved.retry),
            self._logger,
        )
        self._flush_policy = FlushPolicy(resolved.flush_interval_ms)
        self._flush_policy.start(self._do_flush)
        self._register_lifecycle_handlers()
        self._initialized = True

        self._logger.info("SDK initialized", {"endpoint": resolved.endpoint})

    async def destroy(self) -> None:
        if not self._initialized:
            return
        await self.flush()
        self._destroy_sync()
        if self._logger is not None:
            self._logger.info("SDK destroyed")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def track(
        self,
        distinct_id: str,
        event: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        if not self._guard_initialized():
            return
        if not distinct_id or not distinct_id.strip():
            return

        assert self._config is not None
        assert self._queue is not None

        enriched = self._enricher.enrich(properties)
        try:
            appss_event = build_event(event=event, distinct_id=distinct_id, properties=enriched)
        except ValueError as exc:
            if self._logger is not None:
                self._logger.warn("Invalid event", {"error": str(exc)})
            return

        self._queue.enqueue(appss_event)
        if self._logger is not None:
            self._logger.debug(
                "Event enqueued",
                {"event": event, "distinct_id": distinct_id, "queue_size": self._queue.size()},
            )

        if self._queue.size() >= self._config.batch_size:
            self._spawn_task(self.flush())

    def set_user_property(self, distinct_id: str, key: str, value: Any) -> None:
        self.set_user_properties(distinct_id, {key: value})

    def set_user_properties(self, distinct_id: str, properties: dict[str, Any]) -> None:
        if not self._guard_initialized():
            return
        if not distinct_id:
            return
        self._spawn_task(self._send_user_properties(distinct_id, properties))

    def set_super_properties(self, properties: dict[str, Any]) -> None:
        self._enricher.set_all(properties)

    def reset_super_properties(self) -> None:
        self._enricher.reset()

    async def flush(self) -> None:
        if not self._guard_initialized():
            return
        assert self._flush_policy is not None
        await self._flush_policy.flush()

    # ------------------------------------------------------------------
    # Protected
    # ------------------------------------------------------------------

    def _handle_error(self, error: AppssError) -> None:
        if (
            self._config is not None
            and self._config.debug
            and error.code is ErrorCode.NOT_INITIALIZED
        ):
            raise error

        if self._logger is not None:
            payload = {"code": error.code.value}
            if error.severity == "warn":
                self._logger.warn(str(error), payload)
            else:
                self._logger.error(str(error), payload)

        if self._config is not None and self._config.on_error is not None:
            try:
                result = self._config.on_error(error)
            except Exception:
                return
            if inspect.isawaitable(result):
                self._spawn_task(self._await_silently(result))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _guard_initialized(self) -> bool:
        if self._initialized:
            return True
        self._handle_error(NotInitializedError())
        return False

    def _destroy_sync(self) -> None:
        if self._flush_policy is not None:
            self._flush_policy.stop()
        self._unregister_lifecycle_handlers()
        self._initialized = False

    def _spawn_task(self, coro: Awaitable[None]) -> None:
        task: asyncio.Task[None] = asyncio.create_task(self._await_silently(coro))
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    @staticmethod
    async def _await_silently(awaitable: Awaitable[None]) -> None:
        with contextlib.suppress(Exception):
            await awaitable

    async def _do_flush(self) -> None:
        if not self._initialized:
            return
        assert self._config is not None
        assert self._queue is not None
        if self._queue.is_empty():
            return

        events = self._queue.peek(self._config.batch_size)
        payloads = [event_to_payload(e) for e in events]
        headers = build_headers(self._config.api_key)
        await self._send_batch_with_split(payloads, headers)

    async def _send_batch_with_split(
        self,
        batch: list[dict[str, Any]],
        headers: dict[str, str],
    ) -> None:
        if not batch:
            return
        assert self._dispatcher is not None
        assert self._queue is not None
        assert self._flush_policy is not None

        body = {"batch": batch}
        result = await self._dispatcher.dispatch(EVENTS_PATH, body, headers)

        if result.split_requested and len(batch) > 1:
            mid = (len(batch) + 1) // 2
            await self._send_batch_with_split(batch[:mid], headers)
            await self._send_batch_with_split(batch[mid:], headers)
            return

        if result.success:
            self._queue.drain(len(batch))
            self._flush_policy.reset()

        if result.error is not None:
            self._handle_error(result.error)

    async def _send_user_properties(
        self,
        distinct_id: str,
        properties: dict[str, Any],
    ) -> None:
        assert self._config is not None
        assert self._dispatcher is not None
        body = {"distinct_id": distinct_id, "properties": properties}
        headers = build_headers(self._config.api_key)
        result = await self._dispatcher.dispatch(USER_PROPERTIES_PATH, body, headers)
        if result.error is not None:
            self._handle_error(result.error)
