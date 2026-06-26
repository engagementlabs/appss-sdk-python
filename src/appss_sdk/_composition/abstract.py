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
import os
from collections.abc import Awaitable, Mapping
from datetime import datetime, timezone
from typing import Any

from appss_sdk._composition.dispatcher import BatchDispatcher
from appss_sdk._composition.enricher import EventEnricher
from appss_sdk._composition.headers import build_headers
from appss_sdk._config import AppssConfig, ResolvedConfig, resolve_config, validate_config
from appss_sdk._constants import (
    BOT_TOKEN_ENV,
    EVENTS_PATH,
    PUSH_EVENTS_PATH,
    PUSH_SEND_BACKOFF_MS,
    PUSH_SEND_MAX_BACKOFF_MS,
    PUSH_SEND_MAX_RETRIES,
    USER_PROPERTIES_PATH,
)
from appss_sdk._domain.event import build_event, event_to_payload
from appss_sdk._domain.flush import FlushPolicy
from appss_sdk._telegram import RETRYABLE_REASONS, SendOutcome, TelegramSender
from appss_sdk.push import (
    PURCHASE,
    PUSH_CLICKED,
    PUSH_CLICKED_SOURCE,
    PUSH_FAILED,
    PUSH_SENT,
    PUSH_SOURCE_SDK,
    PUSH_TRANSPORT_TELEGRAM,
)
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
        self._telegram_sender: TelegramSender = TelegramSender()
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

    def track_push_clicked(
        self,
        distinct_id: str,
        *,
        push_id: str,
        action_id: str = "",
        offer_token: str | None = None,
    ) -> None:
        """Report that a user tapped a push button.

        Read ``push_id``/``action_id`` from the button the platform rendered:
        - callback button: ``callback_data`` is ``pc:{push_id}:{action_id}``
          (split with ``split(":", maxsplit=2)``; ``action_id`` may be absent
          if the data was truncated to fit Telegram's 64-byte limit).
        - url / web_app button: both arrive as ``push_id`` / ``action_id`` query
          params on the opened URL.

        ``offer_token`` is the signed ``of_...`` discount token carried in the
        button URL (the value substituted for ``{token}``). Pass it when the
        clicked button had an offer so the backend can attribute the discount;
        omit it otherwise.
        """
        properties = {
            "push_id": push_id,
            "action_id": action_id,
            "source": PUSH_CLICKED_SOURCE,
        }
        if offer_token:
            properties["offer_token"] = offer_token
        self.track(distinct_id, PUSH_CLICKED, properties)

    def track_purchase(
        self,
        distinct_id: str,
        *,
        currency: str,
        amount: float,
        transaction_id: str | None = None,
        transaction_status: str | None = None,
        product: str | None = None,
        offer_token: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Report a purchase as the reserved ``$purchase`` event.

        ``currency`` + ``amount`` are required (the backend normalizes revenue from
        them). Pass ``offer_token`` — the signed ``of_...`` token the user carried
        from a push offer button — so the purchase is attributed to that campaign;
        the tracker verifies it the same way it verifies offer clicks. Extra fields
        go through ``properties``.
        """
        props: dict[str, Any] = dict(properties or {})
        props["currency"] = currency
        props["amount"] = amount
        if transaction_id is not None:
            props["transaction_id"] = transaction_id
        if transaction_status is not None:
            props["transaction_status"] = transaction_status
        if product is not None:
            props["product"] = product
        if offer_token:
            props["offer_token"] = offer_token
        self.track(distinct_id, PURCHASE, props)

    async def send_push(self, payload: Mapping[str, Any]) -> SendOutcome:
        """Deliver one push from a Push Hub webhook payload via the Telegram Bot API.

        ``payload`` is the dict the platform POSTs to the app's webhook endpoint
        (``{push_id, template_id, step_id, app_id, recipient:{telegram_id,
        distinct_id}, message:{text, parse_mode, reply_markup}}``) — pass it through
        verbatim. The bot token is read from the ``BOT_TOKEN`` env var.

        The send is retried on transient failures (network / 429 / 5xx). Either way
        the SDK emits the system telemetry the platform relies on: ``Push Sent`` (with
        ``tg_message_id``) on success, ``Push Failed`` (with a ``reason``) otherwise —
        into the dedicated push_events table. Returns the final :class:`SendOutcome`.
        """
        if not self._guard_initialized():
            return SendOutcome(ok=False, reason="not_initialized")

        recipient = payload.get("recipient") or {}
        message = payload.get("message") or {}
        push_id = str(payload.get("push_id") or "")
        template_id = str(payload.get("template_id") or "")
        step_id = str(payload.get("step_id") or "")
        distinct_id = str(recipient.get("distinct_id") or "")
        text = message.get("text") or ""
        parse_mode = message.get("parse_mode")
        reply_markup = message.get("reply_markup")

        try:
            chat_id: int | None = int(recipient.get("telegram_id"))
        except (TypeError, ValueError):
            chat_id = None

        async def _fail(reason: str) -> SendOutcome:
            await self._emit_push_event(
                PUSH_FAILED, distinct_id, push_id, template_id, step_id, reason=reason
            )
            return SendOutcome(ok=False, reason=reason)

        token = os.environ.get(BOT_TOKEN_ENV, "").strip()
        if not token:
            return await _fail("no_token")
        if chat_id is None:
            return await _fail("no_telegram_id")
        if not text:
            return await _fail("empty_content")

        outcome = await self._send_with_retries(
            token, chat_id, text, parse_mode, reply_markup
        )
        if outcome.ok:
            await self._emit_push_event(
                PUSH_SENT,
                distinct_id,
                push_id,
                template_id,
                step_id,
                tg_message_id=outcome.tg_message_id,
            )
        else:
            await self._emit_push_event(
                PUSH_FAILED,
                distinct_id,
                push_id,
                template_id,
                step_id,
                reason=outcome.reason,
            )
        return outcome

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

    async def _send_with_retries(
        self,
        token: str,
        chat_id: int,
        text: str,
        parse_mode: str | None,
        reply_markup: dict | None,
    ) -> SendOutcome:
        attempt = 0
        while True:
            outcome = await self._telegram_sender.send_message(
                token, chat_id, text, parse_mode, reply_markup
            )
            if (
                outcome.ok
                or outcome.reason not in RETRYABLE_REASONS
                or attempt >= PUSH_SEND_MAX_RETRIES
            ):
                return outcome

            if outcome.reason == "throttled" and outcome.retry_after:
                delay_ms = outcome.retry_after * 1000
            else:
                delay_ms = min(
                    PUSH_SEND_BACKOFF_MS * (2**attempt), PUSH_SEND_MAX_BACKOFF_MS
                )
            if self._logger is not None:
                self._logger.warn(
                    "Push send retrying",
                    {"reason": outcome.reason, "attempt": attempt + 1},
                )
            await asyncio.sleep(delay_ms / 1000)
            attempt += 1

    async def _emit_push_event(
        self,
        event: str,
        distinct_id: str,
        push_id: str,
        template_id: str,
        step_id: str,
        *,
        tg_message_id: int | None = None,
        reason: str | None = None,
    ) -> None:
        if self._config is None or self._dispatcher is None:
            return
        properties: dict[str, Any] = {
            "push_id": push_id,
            "template_id": template_id,
            "step_id": step_id,
            "transport": PUSH_TRANSPORT_TELEGRAM,
            "source": PUSH_SOURCE_SDK,
        }
        if tg_message_id is not None:
            properties["tg_message_id"] = str(tg_message_id)
        if reason is not None:
            properties["reason"] = reason

        body = {
            "batch": [
                {
                    "event": event,
                    "distinct_id": distinct_id,
                    "$insert_id": push_id,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "properties": properties,
                }
            ]
        }
        headers = build_headers(self._config.api_key)
        result = await self._dispatcher.dispatch(PUSH_EVENTS_PATH, body, headers)
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
