"""Tests for raw Bot API update extraction."""

from __future__ import annotations

from appss_sdk.telegram.bot_api import from_bot_api_update


def test_bot_api_message_update():
    update = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {"id": 1001, "username": "raw"},
            "chat": {"id": -1, "type": "private"},
            "text": "hi",
        },
    }
    ctx = from_bot_api_update(update)
    assert ctx is not None
    assert ctx.distinct_id == "1001"
    assert ctx.properties["username"] == "raw"
    assert ctx.properties["chat_type"] == "private"


def test_bot_api_callback_query_update():
    update = {
        "update_id": 2,
        "callback_query": {
            "id": "cb",
            "from": {"id": 2002},
            "message": {"chat": {"type": "group"}},
            "data": "x",
        },
    }
    ctx = from_bot_api_update(update)
    assert ctx is not None
    assert ctx.distinct_id == "2002"
    assert ctx.properties["chat_type"] == "group"


def test_bot_api_no_from_field_returns_none():
    update = {
        "update_id": 3,
        "message": {
            "message_id": 1,
            "chat": {"id": -1, "type": "private"},
            "text": "hi",
        },
    }
    assert from_bot_api_update(update) is None


def test_bot_api_start_param_extracted():
    update = {
        "update_id": 4,
        "message": {
            "from": {"id": 7},
            "chat": {"type": "private"},
            "text": "/start promo",
        },
    }
    ctx = from_bot_api_update(update)
    assert ctx is not None
    assert ctx.properties["$start_param"] == "promo"


def test_bot_api_empty_update_returns_none():
    assert from_bot_api_update({"update_id": 5}) is None
