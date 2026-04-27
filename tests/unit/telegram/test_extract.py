"""Tests for the duck-typed Telegram extractor."""

from __future__ import annotations

from appss_sdk.telegram._extract import (
    ExtractedContext,
    TelegramUserProperties,
    extract,
)


def test_extract_from_simple_message():
    msg = {
        "message_id": 1,
        "from": {
            "id": 42,
            "is_bot": False,
            "username": "alice",
            "first_name": "Alice",
            "language_code": "en",
        },
        "chat": {"id": -1, "type": "private"},
        "text": "hello",
    }
    ctx = extract(msg)
    assert ctx is not None
    assert isinstance(ctx, ExtractedContext)
    assert ctx.distinct_id == "42"
    assert ctx.properties["username"] == "alice"
    assert ctx.properties["first_name"] == "Alice"
    assert ctx.properties["language_code"] == "en"
    assert ctx.properties["chat_type"] == "private"
    assert "$start_param" not in ctx.properties


def test_extract_returns_none_when_no_from():
    msg = {"message_id": 1, "chat": {"id": -1, "type": "private"}}
    assert extract(msg) is None


def test_extract_handles_callback_with_nested_message():
    callback = {
        "id": "cb1",
        "from": {"id": 99},
        "message": {"chat": {"type": "group"}},
    }
    ctx = extract(callback)
    assert ctx is not None
    assert ctx.distinct_id == "99"
    assert ctx.properties["chat_type"] == "group"


def test_extract_start_param_from_deep_link():
    msg = {"from": {"id": 1}, "chat": {"type": "private"}, "text": "/start ref_xyz"}
    ctx = extract(msg)
    assert ctx is not None
    assert ctx.properties.get("$start_param") == "ref_xyz"


def test_extract_no_start_param_for_normal_text():
    msg = {"from": {"id": 1}, "chat": {"type": "private"}, "text": "/help"}
    ctx = extract(msg)
    assert ctx is not None
    assert "$start_param" not in ctx.properties


def test_extract_id_must_be_numeric():
    msg = {"from": {"id": "not_a_number"}, "chat": {"type": "private"}}
    assert extract(msg) is None


def test_extract_id_must_not_be_bool():
    msg = {"from": {"id": True}, "chat": {"type": "private"}}
    assert extract(msg) is None


def test_extract_is_premium_flag():
    msg = {"from": {"id": 5, "is_premium": True}, "chat": {"type": "private"}}
    ctx = extract(msg)
    assert ctx is not None
    assert ctx.properties["is_premium"] is True


def test_extract_start_param_blank_after_prefix_returns_none():
    msg = {"from": {"id": 1}, "chat": {"type": "private"}, "text": "/start    "}
    ctx = extract(msg)
    assert ctx is not None
    assert "$start_param" not in ctx.properties


def test_telegram_user_properties_to_dict_only_includes_set_fields():
    p = TelegramUserProperties(username="bob", chat_type="private")
    d = p.to_dict()
    assert d == {"username": "bob", "chat_type": "private"}


def test_telegram_user_properties_renames_start_param():
    p = TelegramUserProperties(start_param="abc")
    assert p.to_dict() == {"$start_param": "abc"}


def test_extract_falls_back_to_message_from():
    # Outer ctx has no from/from_user; inner message does.
    ctx_dict = {"message": {"from": {"id": 100}, "chat": {"type": "private"}}}
    ctx = extract(ctx_dict)
    assert ctx is not None
    assert ctx.distinct_id == "100"
