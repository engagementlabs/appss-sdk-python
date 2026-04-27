"""Tests for aiogram helpers via SimpleNamespace fakes."""

from __future__ import annotations

from types import SimpleNamespace

from appss_sdk.telegram.aiogram import from_aiogram_callback, from_aiogram_message


def make_user(**kw):
    base = {"id": 1, "username": None, "first_name": None, "last_name": None}
    base.update(kw)
    return SimpleNamespace(**base)


def make_chat(type_="private"):
    return SimpleNamespace(type=type_)


def test_aiogram_message_basic():
    msg = SimpleNamespace(
        from_user=make_user(id=42, username="bob", first_name="Bob"),
        chat=make_chat("private"),
        text="hello",
    )
    ctx = from_aiogram_message(msg)
    assert ctx is not None
    assert ctx.distinct_id == "42"
    assert ctx.properties["username"] == "bob"
    assert ctx.properties["first_name"] == "Bob"
    assert ctx.properties["chat_type"] == "private"


def test_aiogram_message_with_start_param():
    msg = SimpleNamespace(
        from_user=make_user(id=42),
        chat=make_chat("private"),
        text="/start campaign42",
    )
    ctx = from_aiogram_message(msg)
    assert ctx is not None
    assert ctx.properties["$start_param"] == "campaign42"


def test_aiogram_callback_basic():
    cb = SimpleNamespace(
        from_user=make_user(id=7),
        message=SimpleNamespace(chat=make_chat("group"), text=None),
    )
    ctx = from_aiogram_callback(cb)
    assert ctx is not None
    assert ctx.distinct_id == "7"
    assert ctx.properties["chat_type"] == "group"


def test_aiogram_message_no_from_returns_none():
    msg = SimpleNamespace(from_user=None, chat=make_chat())
    assert from_aiogram_message(msg) is None


def test_aiogram_message_non_int_id_returns_none():
    msg = SimpleNamespace(
        from_user=make_user(id="oops"),
        chat=make_chat("private"),
        text=None,
    )
    assert from_aiogram_message(msg) is None
