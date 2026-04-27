"""Tests for HttpxTransport."""

from __future__ import annotations

import httpx
import pytest
import respx

from appss_sdk._adapters.transport import HttpxTransport


@pytest.mark.asyncio
async def test_post_returns_status_200_with_json():
    async with respx.mock:
        respx.post("https://api.example.com/v1/x").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        t = HttpxTransport("https://api.example.com", request_timeout_ms=5000)
        r = await t.send("/v1/x", {"a": 1}, {"Authorization": "Bearer K"})
        assert r.status_code == 200
        assert r.body == {"ok": True}
        assert "content-type" in r.headers
        await t.aclose()


@pytest.mark.asyncio
async def test_plain_text_body_is_none():
    async with respx.mock:
        respx.post("https://api.example.com/v1/x").mock(
            return_value=httpx.Response(
                200,
                content=b"hello world",
                headers={"content-type": "text/plain; charset=utf-8"},
            )
        )
        t = HttpxTransport("https://api.example.com", request_timeout_ms=5000)
        r = await t.send("/v1/x", {}, {})
        assert r.status_code == 200
        assert r.body is None
        await t.aclose()


@pytest.mark.asyncio
async def test_401_status_propagated_without_raising():
    async with respx.mock:
        respx.post("https://api.example.com/v1/x").mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )
        t = HttpxTransport("https://api.example.com", request_timeout_ms=5000)
        r = await t.send("/v1/x", {}, {})
        assert r.status_code == 401
        assert r.body == {"error": "unauthorized"}
        await t.aclose()


@pytest.mark.asyncio
async def test_headers_are_forwarded():
    async with respx.mock:
        route = respx.post("https://api.example.com/v1/x").mock(return_value=httpx.Response(204))
        t = HttpxTransport("https://api.example.com", request_timeout_ms=5000)
        await t.send("/v1/x", {"a": 1}, {"X-Custom": "yes", "Authorization": "Bearer ABC"})
        assert route.called
        sent_headers = route.calls.last.request.headers
        assert sent_headers.get("x-custom") == "yes"
        assert sent_headers.get("authorization") == "Bearer ABC"
        await t.aclose()


@pytest.mark.asyncio
async def test_path_concatenation_no_double_slash():
    # endpoint already has no trailing slash (resolve_config rstrips it).
    async with respx.mock:
        route = respx.post("https://api.example.com/api/v1/events").mock(
            return_value=httpx.Response(200, json={})
        )
        t = HttpxTransport("https://api.example.com", request_timeout_ms=5000)
        await t.send("/api/v1/events", {}, {})
        assert route.called
        assert str(route.calls.last.request.url) == "https://api.example.com/api/v1/events"
        await t.aclose()


@pytest.mark.asyncio
async def test_timeout_exception_propagates():
    async with respx.mock:
        respx.post("https://api.example.com/v1/x").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        t = HttpxTransport("https://api.example.com", request_timeout_ms=5000)
        with pytest.raises(httpx.TimeoutException):
            await t.send("/v1/x", {}, {})
        await t.aclose()


@pytest.mark.asyncio
async def test_aclose_closes_client_and_is_idempotent():
    async with respx.mock:
        respx.post("https://api.example.com/v1/x").mock(return_value=httpx.Response(200, json={}))
        t = HttpxTransport("https://api.example.com", request_timeout_ms=5000)
        await t.send("/v1/x", {}, {})
        assert t._client is not None
        await t.aclose()
        assert t._client is None
        # Calling again is safe (no-op).
        await t.aclose()
        assert t._client is None
