"""Unit tests for appss_sdk._domain.event."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from appss_sdk._domain.event import build_event, event_to_payload
from appss_sdk._types import AppssEvent


def test_build_event_minimal() -> None:
    before = datetime.now(tz=timezone.utc)
    event = build_event(event="page_view", distinct_id="u1")
    after = datetime.now(tz=timezone.utc)

    assert event.event == "page_view"
    assert event.distinct_id == "u1"
    assert event.properties is None
    # insert_id is a valid UUID string
    parsed = uuid.UUID(event.insert_id)
    assert str(parsed) == event.insert_id
    # timestamp falls between the two now() snapshots
    assert before <= event.timestamp <= after
    assert event.timestamp.tzinfo is not None


def test_build_event_with_properties_passes_through() -> None:
    props = {"a": 1, "b": "two"}
    event = build_event(event="x", distinct_id="u", properties=props)
    assert event.properties == {"a": 1, "b": "two"}


def test_build_event_empty_name_raises() -> None:
    with pytest.raises(ValueError, match="Event name is required"):
        build_event(event="", distinct_id="u")


def test_build_event_whitespace_name_raises() -> None:
    with pytest.raises(ValueError, match="Event name is required"):
        build_event(event="  ", distinct_id="u")


def test_build_event_insert_id_is_unique() -> None:
    e1 = build_event(event="x", distinct_id="u")
    e2 = build_event(event="x", distinct_id="u")
    assert e1.insert_id != e2.insert_id


def test_event_to_payload_omits_properties_when_none() -> None:
    event = AppssEvent(
        event="x",
        distinct_id="u",
        insert_id="00000000-0000-0000-0000-000000000000",
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        properties=None,
    )
    payload = event_to_payload(event)
    assert "properties" not in payload


def test_event_to_payload_omits_properties_when_empty() -> None:
    event = AppssEvent(
        event="x",
        distinct_id="u",
        insert_id="00000000-0000-0000-0000-000000000000",
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        properties={},
    )
    payload = event_to_payload(event)
    assert "properties" not in payload


def test_event_to_payload_includes_properties_when_present() -> None:
    event = AppssEvent(
        event="x",
        distinct_id="u",
        insert_id="00000000-0000-0000-0000-000000000000",
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        properties={"k": "v"},
    )
    payload = event_to_payload(event)
    assert payload["properties"] == {"k": "v"}


def test_event_to_payload_keys_and_dollar_insert_id() -> None:
    event = AppssEvent(
        event="page_view",
        distinct_id="u1",
        insert_id="abc-123",
        timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        properties=None,
    )
    payload = event_to_payload(event)
    assert payload["event"] == "page_view"
    assert payload["distinct_id"] == "u1"
    assert payload["$insert_id"] == "abc-123"
    assert "insert_id" not in payload  # only the $-prefixed form
    assert "timestamp" in payload


def test_event_to_payload_timestamp_is_iso8601_with_tz() -> None:
    event = build_event(event="x", distinct_id="u")
    payload = event_to_payload(event)
    ts = payload["timestamp"]
    assert isinstance(ts, str)
    assert "T" in ts
    assert ts.endswith("+00:00") or ts.endswith("Z")


def test_event_to_payload_roundtrip_via_build_event() -> None:
    event = build_event(event="signup", distinct_id="user-42", properties={"plan": "pro"})
    payload = event_to_payload(event)
    assert payload["event"] == "signup"
    assert payload["distinct_id"] == "user-42"
    assert payload["properties"] == {"plan": "pro"}
    # timestamp parses back to a datetime within ~1s of now
    parsed = datetime.fromisoformat(payload["timestamp"])
    assert parsed.tzinfo is not None
    assert datetime.now(tz=timezone.utc) - parsed < timedelta(seconds=2)
