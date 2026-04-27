"""Tests for python-telegram-bot Update helper via SimpleNamespace fakes."""

from __future__ import annotations

from types import SimpleNamespace

from appss_sdk.telegram.ptb import from_ptb_update


def make_user(**kw):
    base = {"id": 1}
    base.update(kw)
    return SimpleNamespace(**base)


def test_ptb_message_path():
    update = SimpleNamespace(
        message=SimpleNamespace(
            from_user=make_user(id=11, username="cat"),
            chat=SimpleNamespace(type="private"),
            text="/start hello",
        ),
        callback_query=None,
        inline_query=None,
        edited_message=None,
        channel_post=None,
    )
    ctx = from_ptb_update(update)
    assert ctx is not None
    assert ctx.distinct_id == "11"
    assert ctx.properties["username"] == "cat"
    assert ctx.properties["$start_param"] == "hello"


def test_ptb_callback_query_path():
    update = SimpleNamespace(
        message=None,
        callback_query=SimpleNamespace(
            from_user=make_user(id=22),
            message=SimpleNamespace(chat=SimpleNamespace(type="supergroup"), text=None),
        ),
        inline_query=None,
        edited_message=None,
        channel_post=None,
    )
    ctx = from_ptb_update(update)
    assert ctx is not None
    assert ctx.distinct_id == "22"
    assert ctx.properties["chat_type"] == "supergroup"


def test_ptb_no_subobjects_returns_none():
    update = SimpleNamespace(
        message=None,
        callback_query=None,
        inline_query=None,
        edited_message=None,
        channel_post=None,
    )
    assert from_ptb_update(update) is None


def test_ptb_inline_query_path():
    update = SimpleNamespace(
        message=None,
        callback_query=None,
        inline_query=SimpleNamespace(from_user=make_user(id=33)),
        edited_message=None,
        channel_post=None,
    )
    ctx = from_ptb_update(update)
    assert ctx is not None
    assert ctx.distinct_id == "33"
