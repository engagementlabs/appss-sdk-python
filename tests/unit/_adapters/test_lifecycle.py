"""Tests for ShutdownHandler."""

from __future__ import annotations

import asyncio
import signal
import warnings

import pytest

from appss_sdk._adapters.lifecycle import ShutdownHandler


@pytest.mark.asyncio
async def test_register_adds_signal_handlers(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    added: list[int] = []
    removed: list[int] = []

    loop = asyncio.get_running_loop()

    def fake_add(sig, *_args, **_kwargs):
        added.append(sig)

    def fake_remove(sig):
        removed.append(sig)
        return True

    monkeypatch.setattr(loop, "add_signal_handler", fake_add)
    monkeypatch.setattr(loop, "remove_signal_handler", fake_remove)

    async def flush() -> None:
        return None

    h = ShutdownHandler(flush)
    h.register()
    assert h._registered is True
    assert signal.SIGTERM in added
    assert signal.SIGINT in added

    h.unregister()
    assert h._registered is False
    assert signal.SIGTERM in removed
    assert signal.SIGINT in removed


@pytest.mark.asyncio
async def test_register_is_idempotent(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    add_count = 0

    loop = asyncio.get_running_loop()

    def fake_add(_sig, *_args, **_kwargs):
        nonlocal add_count
        add_count += 1

    monkeypatch.setattr(loop, "add_signal_handler", fake_add)
    monkeypatch.setattr(loop, "remove_signal_handler", lambda _sig: True)

    async def flush() -> None:
        return None

    h = ShutdownHandler(flush)
    h.register()
    h.register()  # second call is no-op
    assert add_count == 2  # SIGTERM + SIGINT, only on first register


@pytest.mark.asyncio
async def test_register_on_windows_warns_and_skips(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")

    async def flush() -> None:
        return None

    h = ShutdownHandler(flush)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        h.register()
        assert any("Windows" in str(w.message) for w in caught)
    assert h._registered is False


@pytest.mark.asyncio
async def test_unregister_without_register_is_noop():
    async def flush() -> None:
        return None

    h = ShutdownHandler(flush)
    # Should not raise.
    h.unregister()
    assert h._registered is False
