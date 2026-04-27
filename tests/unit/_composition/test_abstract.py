"""Unit tests for BaseAppssClient."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from appss_sdk._composition.abstract import BaseAppssClient
from appss_sdk._config import AppssConfig, ResolvedConfig, RetryConfig
from appss_sdk._ports import IEventQueue, ILogger, ITransport
from appss_sdk._types import AppssEvent, TransportResponse
from appss_sdk.errors import AppssError, InvalidApiKeyError


class _TestQueue:
    def __init__(self) -> None:
        self._items: list[AppssEvent] = []

    def enqueue(self, event: AppssEvent) -> None:
        self._items.append(event)

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


class _TestTransport:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.calls: list[tuple[str, Any, dict[str, str]]] = []

    async def send(
        self,
        path: str,
        body: Any,
        headers: dict[str, str],
    ) -> TransportResponse:
        self.calls.append((path, body, headers))
        return TransportResponse(status_code=self.status, headers={}, body=None)


class _NoopLogger:
    def __init__(self) -> None:
        self.infos: list[tuple[str, dict[str, Any] | None]] = []
        self.warns: list[tuple[str, dict[str, Any] | None]] = []
        self.errors: list[tuple[str, dict[str, Any] | None]] = []

    def debug(self, message: str, context: dict[str, Any] | None = None) -> None:
        pass

    def info(self, message: str, context: dict[str, Any] | None = None) -> None:
        self.infos.append((message, context))

    def warn(self, message: str, context: dict[str, Any] | None = None) -> None:
        self.warns.append((message, context))

    def error(self, message: str, context: dict[str, Any] | None = None) -> None:
        self.errors.append((message, context))


class _TestClient(BaseAppssClient):
    def __init__(
        self,
        config: AppssConfig | dict[str, Any],
        *,
        transport: ITransport | None = None,
        queue: IEventQueue | None = None,
        logger: ILogger | None = None,
    ) -> None:
        self._test_transport: ITransport = transport or _TestTransport()
        self._test_queue: IEventQueue = queue or _TestQueue()
        self._test_logger: ILogger = logger or _NoopLogger()
        super().__init__(config)

    def _create_transport(self, config: ResolvedConfig) -> ITransport:
        return self._test_transport

    def _create_queue(self, config: ResolvedConfig) -> IEventQueue:
        return self._test_queue

    def _create_logger(self, config: ResolvedConfig) -> ILogger:
        return self._test_logger

    def _register_lifecycle_handlers(self) -> None:
        pass

    def _unregister_lifecycle_handlers(self) -> None:
        pass


def _config(
    *,
    api_key: str = "test-key",
    batch_size: int = 50,
    flush_interval_ms: int = 60_000,
    debug: bool = False,
    on_error: Any = None,
) -> AppssConfig:
    return AppssConfig(
        api_key=api_key,
        batch_size=batch_size,
        flush_interval_ms=flush_interval_ms,
        debug=debug,
        on_error=on_error,
        retry=RetryConfig(max_retries=2, base_backoff_ms=1, max_backoff_ms=2),
    )


@pytest.mark.asyncio
async def test_init_with_empty_api_key_raises() -> None:
    with pytest.raises(InvalidApiKeyError):
        _TestClient(AppssConfig(api_key=""))


@pytest.mark.asyncio
async def test_init_logs_and_sets_initialized() -> None:
    logger = _NoopLogger()
    client = _TestClient(_config(), logger=logger)
    try:
        assert client._initialized is True
        assert any("SDK initialized" in m for m, _ in logger.infos)
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_track_before_init_is_silent() -> None:
    logger = _NoopLogger()
    client = _TestClient(_config(), logger=logger)
    await client.destroy()
    # destroyed → not initialized; track should be silent (warns about NOT_INITIALIZED).
    client.track("user-1", "ev")
    # No exception raised; warning emitted via _handle_error.
    assert any("not initialized" in m.lower() for m, _ in logger.warns)


@pytest.mark.asyncio
async def test_track_then_flush_dispatches_batch() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    try:
        client.track("user-1", "ev1")
        client.track("user-2", "ev2")
        await client.flush()
        assert len(transport.calls) >= 1
        path, body, headers = transport.calls[0]
        assert path == "/api/v1/events"
        assert "batch" in body
        ids = [item["distinct_id"] for item in body["batch"]]
        assert "user-1" in ids and "user-2" in ids
        assert headers["Authorization"] == "Bearer test-key"
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_auto_flush_at_batch_size() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(batch_size=5), transport=transport)
    try:
        for i in range(5):
            client.track(f"user-{i}", "ev")
        # Yield so the auto-created task can run.
        for _ in range(20):
            if transport.calls:
                break
            await asyncio.sleep(0.005)
        assert len(transport.calls) >= 1
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_set_user_property_dispatches_to_user_properties_path() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    try:
        client.set_user_property("user-1", "plan", "pro")
        for _ in range(20):
            if transport.calls:
                break
            await asyncio.sleep(0.005)
        assert any(call[0] == "/api/v1/user-properties" for call in transport.calls)
        last = transport.calls[-1]
        assert last[1] == {"distinct_id": "user-1", "properties": {"plan": "pro"}}
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_super_properties_attached_to_tracked_event() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    try:
        client.set_super_properties({"app_version": "1.0", "env": "prod"})
        client.track("user-1", "click", {"button": "go"})
        await client.flush()
        assert transport.calls
        body = transport.calls[0][1]
        item = body["batch"][0]
        props = item["properties"]
        assert props["app_version"] == "1.0"
        assert props["env"] == "prod"
        assert props["button"] == "go"
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_reset_super_properties_clears_them() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    try:
        client.set_super_properties({"app_version": "1.0"})
        client.reset_super_properties()
        client.track("user-1", "click")
        await client.flush()
        body = transport.calls[0][1]
        item = body["batch"][0]
        # No app_version super-property should be carried.
        assert "properties" not in item or "app_version" not in item.get("properties", {})
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_destroy_flushes_then_marks_uninitialized() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    client.track("user-1", "ev")
    await client.destroy()
    assert client._initialized is False
    assert len(transport.calls) >= 1


@pytest.mark.asyncio
async def test_401_stops_subsequent_dispatches() -> None:
    transport = _TestTransport(status=401)
    on_error_calls: list[AppssError] = []

    def on_error(err: AppssError) -> None:
        on_error_calls.append(err)

    client = _TestClient(_config(on_error=on_error), transport=transport)
    try:
        client.track("user-1", "ev1")
        await client.flush()
        first_calls = len(transport.calls)
        assert first_calls == 1
        # 401 surfaced as ApiKeyRevokedError to on_error.
        assert any(e.code.value == "API_KEY_REVOKED" for e in on_error_calls)

        client.track("user-2", "ev2")
        await client.flush()
        # Dispatcher latched stopped — no new transport calls.
        assert len(transport.calls) == first_calls
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_track_with_blank_distinct_id_is_silent() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    try:
        client.track("   ", "ev")
        await client.flush()
        assert transport.calls == []
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_on_error_callback_can_be_async() -> None:
    transport = _TestTransport(status=400)
    received: list[AppssError] = []

    async def on_error(err: AppssError) -> None:
        received.append(err)

    client = _TestClient(_config(on_error=on_error), transport=transport)
    try:
        client.track("u", "ev")
        await client.flush()
        # Allow the spawned async callback to run.
        for _ in range(20):
            if received:
                break
            await asyncio.sleep(0.005)
        assert received
        assert received[0].code.value == "PROTOCOL_ERROR"
    finally:
        await client.destroy()
