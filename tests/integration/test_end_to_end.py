"""End-to-end integration tests via respx.

Drives ``AppssClient`` against a mocked HTTP layer so we exercise the entire
pipeline: enrichment → queue → batch → headers → transport → response handling →
retry/split logic, plus the public ``track`` / ``set_user_properties`` /
``flush`` / ``destroy`` lifecycle.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from appss_sdk import create_appss

BASE_URL = "https://api.example.test"
EVENTS_URL = f"{BASE_URL}/api/v1/events"
USER_PROPS_URL = f"{BASE_URL}/api/v1/user-properties"


def _config(**overrides: Any) -> dict[str, Any]:
    """Build a fast-default config for tests.

    ``base_backoff_ms=1`` keeps retry waits below the test timeout, and
    ``debug=False`` selects the NoopLogger so tests stay quiet.
    """
    cfg: dict[str, Any] = {
        "api_key": "k_test",
        "endpoint": BASE_URL,
        "debug": False,
        "retry": {"max_retries": 5, "base_backoff_ms": 1, "max_backoff_ms": 10},
    }
    cfg.update(overrides)
    return cfg


def _read_json(request: httpx.Request) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(request.read())
    return payload


@pytest.mark.asyncio
async def test_track_then_flush_posts_to_events_endpoint() -> None:
    async with respx.mock(assert_all_called=False) as mock:
        events = mock.post(EVENTS_URL).mock(return_value=httpx.Response(200, json={"ok": True}))

        appss = create_appss(_config())
        try:
            appss.track("u1", "test_event", {"a": 1})
            await appss.flush()
        finally:
            await appss.destroy()

        assert events.called
        assert events.call_count == 1
        body = _read_json(events.calls.last.request)
        assert "batch" in body
        assert len(body["batch"]) == 1
        evt = body["batch"][0]
        assert evt["event"] == "test_event"
        assert evt["distinct_id"] == "u1"
        assert "$insert_id" in evt
        assert "timestamp" in evt
        assert evt["properties"]["a"] == 1
        assert evt["properties"]["$lib"] == "python"

        request = events.calls.last.request
        assert request.headers["authorization"] == "Bearer k_test"
        assert request.headers["x-appss-protocol-version"] == "1"
        assert request.headers["x-appss-sdk"].startswith("@appss-sdk/")


@pytest.mark.asyncio
async def test_set_user_properties_posts_to_user_properties_endpoint() -> None:
    async with respx.mock(assert_all_called=False) as mock:
        events = mock.post(EVENTS_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
        user = mock.post(USER_PROPS_URL).mock(return_value=httpx.Response(200, json={"ok": True}))

        appss = create_appss(_config())
        try:
            appss.set_user_properties("u2", {"plan": "pro", "username": "alice"})
            # Give the spawned task a chance to run.
            await appss.flush()
        finally:
            await appss.destroy()

        assert user.called
        body = _read_json(user.calls.last.request)
        assert body == {"distinct_id": "u2", "properties": {"plan": "pro", "username": "alice"}}
        assert events.call_count == 0


@pytest.mark.asyncio
async def test_401_stops_subsequent_sends_forever() -> None:
    async with respx.mock(assert_all_called=False) as mock:
        events = mock.post(EVENTS_URL).mock(
            return_value=httpx.Response(401, json={"error": "revoked"})
        )

        captured: list[Exception] = []
        appss = create_appss(_config(on_error=lambda e: captured.append(e)))
        try:
            appss.track("u3", "first")
            await appss.flush()
            first_count = events.call_count
            assert first_count == 1

            appss.track("u3", "second")
            await appss.flush()
            # After 401 the dispatcher latches `stopped=True`; no second request.
            assert events.call_count == first_count
        finally:
            await appss.destroy()

        assert any(getattr(e, "code", None) and e.code.value == "API_KEY_REVOKED" for e in captured)


@pytest.mark.asyncio
async def test_413_triggers_recursive_split_and_retry() -> None:
    async with respx.mock(assert_all_called=False) as mock:
        events = mock.post(EVENTS_URL).mock(
            side_effect=[
                httpx.Response(413, json={"error": "payload too large"}),
                httpx.Response(200, json={"ok": True}),
                httpx.Response(200, json={"ok": True}),
            ]
        )

        appss = create_appss(_config())
        try:
            for i in range(4):
                appss.track("u4", f"e_{i}", {"i": i})
            await appss.flush()
        finally:
            await appss.destroy()

        assert events.call_count == 3
        first_batch = _read_json(events.calls[0].request)["batch"]
        second_batch = _read_json(events.calls[1].request)["batch"]
        third_batch = _read_json(events.calls[2].request)["batch"]
        assert len(first_batch) == 4
        assert len(second_batch) == 2
        assert len(third_batch) == 2


@pytest.mark.asyncio
async def test_429_retries_after_retry_after_header() -> None:
    async with respx.mock(assert_all_called=False) as mock:
        events = mock.post(EVENTS_URL).mock(
            side_effect=[
                httpx.Response(429, headers={"retry-after": "0.05"}, json={}),
                httpx.Response(200, json={"ok": True}),
            ]
        )

        appss = create_appss(_config())
        try:
            appss.track("u5", "rate_limited_event")
            await appss.flush()
        finally:
            await appss.destroy()

        assert events.call_count == 2


@pytest.mark.asyncio
async def test_5xx_retries_with_exponential_backoff() -> None:
    async with respx.mock(assert_all_called=False) as mock:
        events = mock.post(EVENTS_URL).mock(
            side_effect=[
                httpx.Response(503, json={}),
                httpx.Response(200, json={"ok": True}),
            ]
        )

        appss = create_appss(_config())
        try:
            appss.track("u6", "server_error_event")
            await appss.flush()
        finally:
            await appss.destroy()

        assert events.call_count == 2


@pytest.mark.asyncio
async def test_destroy_flushes_pending_events() -> None:
    async with respx.mock(assert_all_called=False) as mock:
        events = mock.post(EVENTS_URL).mock(return_value=httpx.Response(200, json={"ok": True}))

        appss = create_appss(_config())
        appss.track("u7", "pending_event", {"k": "v"})
        # No explicit flush: destroy() must drain the queue before tearing down.
        await appss.destroy()

        assert events.call_count == 1
        body = _read_json(events.calls.last.request)
        assert body["batch"][0]["event"] == "pending_event"


@pytest.mark.asyncio
async def test_batch_size_threshold_auto_flushes() -> None:
    async with respx.mock(assert_all_called=False) as mock:
        events = mock.post(EVENTS_URL).mock(return_value=httpx.Response(200, json={"ok": True}))

        appss = create_appss(_config(batch_size=3))
        try:
            for i in range(3):
                appss.track("u8", f"auto_{i}")
            # Auto-flush is triggered as a background task; flush() awaits it.
            await appss.flush()
        finally:
            await appss.destroy()

        assert events.called
        # Either the auto-flush or the explicit flush wins, but at least one
        # batch with all three events must have been dispatched.
        all_events = [
            evt for call in events.calls for evt in _read_json(call.request).get("batch", [])
        ]
        assert {e["event"] for e in all_events} == {"auto_0", "auto_1", "auto_2"}


@pytest.mark.asyncio
async def test_super_properties_attached_to_every_event() -> None:
    async with respx.mock(assert_all_called=False) as mock:
        events = mock.post(EVENTS_URL).mock(return_value=httpx.Response(200, json={"ok": True}))

        appss = create_appss(_config())
        try:
            appss.set_super_properties({"app_version": "1.2.3", "env": "test"})
            appss.track("u9", "with_super", {"local": True})
            await appss.flush()
        finally:
            await appss.destroy()

        body = _read_json(events.calls.last.request)
        props = body["batch"][0]["properties"]
        assert props["app_version"] == "1.2.3"
        assert props["env"] == "test"
        assert props["local"] is True
        assert props["$lib"] == "python"


@pytest.mark.asyncio
async def test_400_protocol_error_surfaces_to_on_error() -> None:
    async with respx.mock(assert_all_called=False) as mock:
        events = mock.post(EVENTS_URL).mock(
            return_value=httpx.Response(400, json={"error": "bad request"})
        )

        captured: list[Exception] = []
        appss = create_appss(_config(on_error=lambda e: captured.append(e)))
        try:
            appss.track("u10", "bad_event")
            await appss.flush()
            # Single flush → single attempt; 400 is DROP, not RETRY.
            assert events.call_count == 1
        finally:
            await appss.destroy()

        assert any(getattr(e, "code", None) and e.code.value == "PROTOCOL_ERROR" for e in captured)
