"""Unit tests for appss_sdk._domain.flush."""

from __future__ import annotations

import asyncio

from appss_sdk._domain.flush import FlushPolicy


async def test_start_then_immediate_stop_does_not_invoke_fn() -> None:
    calls = 0

    async def fn() -> None:
        nonlocal calls
        calls += 1

    p = FlushPolicy(interval_ms=50)
    p.start(fn)
    p.stop()
    await asyncio.sleep(0.08)
    assert calls == 0


async def test_loop_invokes_fn_after_one_interval() -> None:
    calls = 0

    async def fn() -> None:
        nonlocal calls
        calls += 1

    p = FlushPolicy(interval_ms=50)
    p.start(fn)
    try:
        await asyncio.sleep(0.08)
        assert calls >= 1
    finally:
        p.stop()


async def test_loop_invokes_fn_multiple_times() -> None:
    calls = 0

    async def fn() -> None:
        nonlocal calls
        calls += 1

    p = FlushPolicy(interval_ms=50)
    p.start(fn)
    try:
        await asyncio.sleep(0.13)
        assert calls >= 2
    finally:
        p.stop()


async def test_double_start_does_not_duplicate_loop() -> None:
    calls = 0

    async def fn() -> None:
        nonlocal calls
        calls += 1

    p = FlushPolicy(interval_ms=50)
    p.start(fn)
    p.start(fn)  # second start is a no-op
    try:
        await asyncio.sleep(0.13)
        # If two loops were running we'd see ~4+ calls; one loop yields ~2.
        assert calls <= 3
        assert calls >= 2
    finally:
        p.stop()


async def test_flush_invokes_fn_once() -> None:
    calls = 0

    async def fn() -> None:
        nonlocal calls
        calls += 1

    p = FlushPolicy(interval_ms=10_000)
    p.start(fn)
    try:
        await p.flush()
        assert calls == 1
    finally:
        p.stop()


async def test_concurrent_flush_dedup() -> None:
    calls = 0

    async def fn() -> None:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)

    p = FlushPolicy(interval_ms=10_000)
    p.start(fn)
    try:
        await asyncio.gather(p.flush(), p.flush(), p.flush())
        assert calls == 1
    finally:
        p.stop()


async def test_sequential_flush_invokes_fn_each_time() -> None:
    calls = 0

    async def fn() -> None:
        nonlocal calls
        calls += 1

    p = FlushPolicy(interval_ms=10_000)
    p.start(fn)
    try:
        await p.flush()
        await p.flush()
        await p.flush()
        assert calls == 3
    finally:
        p.stop()


async def test_reset_wakes_loop_early() -> None:
    calls = 0

    async def fn() -> None:
        nonlocal calls
        calls += 1

    p = FlushPolicy(interval_ms=200)
    p.start(fn)
    try:
        await asyncio.sleep(0.05)
        assert calls == 0
        p.reset()
        await asyncio.sleep(0.05)
        assert calls >= 1
    finally:
        p.stop()


async def test_stop_halts_subsequent_invocations() -> None:
    calls = 0

    async def fn() -> None:
        nonlocal calls
        calls += 1

    p = FlushPolicy(interval_ms=30)
    p.start(fn)
    await asyncio.sleep(0.05)
    p.stop()
    snapshot = calls
    await asyncio.sleep(0.1)
    assert calls == snapshot
