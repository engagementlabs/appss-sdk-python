from __future__ import annotations

import pytest

from appss_sdk.push import PUSH_CLICKED
from tests.unit._composition.test_abstract import _config, _TestClient, _TestTransport


def test_event_name_is_canonical() -> None:
    assert PUSH_CLICKED == "Push Clicked"


@pytest.mark.asyncio
async def test_track_push_clicked_emits_stable_schema_to_events_path() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    try:
        client.track_push_clicked("user-1", push_id="p1", action_id="a1")
        await client.flush()

        assert transport.calls
        path, body, headers = transport.calls[0]
        assert path == "/api/v1/events"
        assert headers["Authorization"] == "Bearer test-key"

        item = body["batch"][0]
        assert item["event"] == "Push Clicked"
        assert item["distinct_id"] == "user-1"
        props = item["properties"]
        assert props["push_id"] == "p1"
        assert props["action_id"] == "a1"
        assert props["source"] == "push_hub"
        assert "template_id" not in props
        assert "step_id" not in props
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_track_push_clicked_action_id_defaults_to_empty() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    try:
        client.track_push_clicked("user-1", push_id="p1")
        await client.flush()
        props = transport.calls[0][1]["batch"][0]["properties"]
        assert props["push_id"] == "p1"
        assert props["action_id"] == ""
        assert props["source"] == "push_hub"
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_track_push_clicked_includes_offer_token_when_given() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    try:
        client.track_push_clicked("user-1", push_id="p1", action_id="a1", offer_token="of_abc")
        await client.flush()
        props = transport.calls[0][1]["batch"][0]["properties"]
        assert props["offer_token"] == "of_abc"
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_track_push_clicked_omits_offer_token_when_absent() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    try:
        client.track_push_clicked("user-1", push_id="p1")
        await client.flush()
        props = transport.calls[0][1]["batch"][0]["properties"]
        assert "offer_token" not in props
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_track_push_clicked_carries_super_properties() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    try:
        client.set_super_properties({"$lib": "python"})
        client.track_push_clicked("user-1", push_id="p1")
        await client.flush()
        props = transport.calls[0][1]["batch"][0]["properties"]
        assert props["$lib"] == "python"
        assert props["push_id"] == "p1"
    finally:
        await client.destroy()
