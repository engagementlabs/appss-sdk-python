from __future__ import annotations

import asyncio

import pytest

from appss_sdk._telegram import SendOutcome
from appss_sdk.push import PUSH_FAILED, PUSH_SENT
from tests.unit._composition.test_abstract import _config, _TestClient, _TestTransport


def _payload(**overrides) -> dict:
    payload = {
        "push_id": "pid-1",
        "template_id": "tmpl-1",
        "step_id": "step-1",
        "app_id": 7,
        "recipient": {"telegram_id": 12345, "distinct_id": "12345"},
        "message": {
            "text": "hello",
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": [[{"text": "x", "url": "https://a"}]]},
        },
    }
    payload.update(overrides)
    return payload


class _FakeSender:
    def __init__(self, outcomes: list[SendOutcome]) -> None:
        self._outcomes = outcomes
        self.calls: list[tuple] = []

    async def send_message(
        self, token, chat_id, text, parse_mode=None, reply_markup=None
    ) -> SendOutcome:
        self.calls.append((token, chat_id, text, parse_mode, reply_markup))
        idx = min(len(self.calls) - 1, len(self._outcomes) - 1)
        return self._outcomes[idx]


def _push_event_calls(transport: _TestTransport) -> list[dict]:
    out = []
    for path, body, _ in transport.calls:  # _ = headers
        if path == "/api/v1/push-events":
            out.extend(body["batch"])
    return out


@pytest.mark.asyncio
async def test_send_push_success_sends_and_emits_push_sent(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "tok-123")
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    sender = _FakeSender([SendOutcome(ok=True, tg_message_id=99)])
    client._telegram_sender = sender
    try:
        outcome = await client.send_push(_payload())

        assert outcome.ok is True
        assert outcome.tg_message_id == 99

        # Bot API was called with the parsed message fields.
        assert sender.calls == [
            ("tok-123", 12345, "hello", "HTML", _payload()["message"]["reply_markup"])
        ]

        events = _push_event_calls(transport)
        assert len(events) == 1
        evt = events[0]
        assert evt["event"] == PUSH_SENT
        assert evt["distinct_id"] == "12345"
        assert evt["$insert_id"] == "pid-1"  # = push_id for dedup
        props = evt["properties"]
        assert props["push_id"] == "pid-1"
        assert props["template_id"] == "tmpl-1"
        assert props["step_id"] == "step-1"
        assert props["transport"] == "telegram"
        assert props["source"] == "sdk"
        assert props["tg_message_id"] == "99"
        assert "reason" not in props
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_send_push_without_token_emits_failed_no_send(monkeypatch) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    sender = _FakeSender([SendOutcome(ok=True, tg_message_id=1)])
    client._telegram_sender = sender
    try:
        outcome = await client.send_push(_payload())

        assert outcome.ok is False
        assert outcome.reason == "no_token"
        assert sender.calls == []  # never attempted the send

        events = _push_event_calls(transport)
        assert len(events) == 1
        assert events[0]["event"] == PUSH_FAILED
        assert events[0]["properties"]["reason"] == "no_token"
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_send_push_terminal_failure_emits_failed(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "tok-123")
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    sender = _FakeSender([SendOutcome(ok=False, reason="blocked")])
    client._telegram_sender = sender
    try:
        outcome = await client.send_push(_payload())

        assert outcome.ok is False
        assert outcome.reason == "blocked"
        assert len(sender.calls) == 1  # terminal reason → not retried

        events = _push_event_calls(transport)
        assert events[0]["event"] == PUSH_FAILED
        assert events[0]["properties"]["reason"] == "blocked"
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_send_push_retries_transient_then_fails(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "tok-123")
    async def _no_sleep(_delay):
        return
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    sender = _FakeSender([SendOutcome(ok=False, reason="network")])
    client._telegram_sender = sender
    try:
        outcome = await client.send_push(_payload())

        assert outcome.ok is False
        assert outcome.reason == "network"
        # initial attempt + PUSH_SEND_MAX_RETRIES (3) retries = 4 calls
        assert len(sender.calls) == 4

        assert _push_event_calls(transport)[0]["event"] == PUSH_FAILED
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_send_push_retries_transient_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "tok-123")
    async def _no_sleep(_delay):
        return
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    sender = _FakeSender(
        [SendOutcome(ok=False, reason="throttled", retry_after=1), SendOutcome(ok=True, tg_message_id=7)]
    )
    client._telegram_sender = sender
    try:
        outcome = await client.send_push(_payload())

        assert outcome.ok is True
        assert len(sender.calls) == 2
        assert _push_event_calls(transport)[0]["event"] == PUSH_SENT
    finally:
        await client.destroy()


@pytest.mark.asyncio
async def test_track_purchase_emits_purchase_with_offer_token() -> None:
    transport = _TestTransport(status=200)
    client = _TestClient(_config(), transport=transport)
    try:
        client.track_purchase(
            "user-1",
            currency="USD",
            amount=9.99,
            transaction_id="tx-1",
            offer_token="of_abc",
        )
        await client.flush()

        path, body, _ = transport.calls[0]  # _ = headers
        assert path == "/api/v1/events"
        item = body["batch"][0]
        assert item["event"] == "$purchase"
        props = item["properties"]
        assert props["currency"] == "USD"
        assert props["amount"] == 9.99
        assert props["transaction_id"] == "tx-1"
        assert props["offer_token"] == "of_abc"
    finally:
        await client.destroy()
