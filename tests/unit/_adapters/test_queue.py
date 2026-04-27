"""Tests for MemoryQueue."""

from __future__ import annotations

from datetime import datetime, timezone

from appss_sdk._adapters.queue import MemoryQueue
from appss_sdk._types import AppssEvent


def _ev(name: str) -> AppssEvent:
    return AppssEvent(
        event=name,
        distinct_id="user-1",
        insert_id=name,
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        properties=None,
    )


def test_new_queue_is_empty():
    q = MemoryQueue(max_size=3)
    assert q.size() == 0
    assert q.is_empty() is True
    assert q.peek(10) == []


def test_enqueue_then_peek_non_destructive():
    q = MemoryQueue(max_size=3)
    e = _ev("a")
    q.enqueue(e)
    assert q.size() == 1
    assert q.is_empty() is False
    peeked = q.peek(1)
    assert peeked == [e]
    # peek doesn't mutate
    assert q.size() == 1
    assert q.peek(5) == [e]


def test_drain_destructive():
    q = MemoryQueue(max_size=10)
    a, b, c = _ev("a"), _ev("b"), _ev("c")
    q.enqueue(a)
    q.enqueue(b)
    q.enqueue(c)
    drained = q.drain(1)
    assert drained == [a]
    assert q.size() == 2
    assert q.peek(5) == [b, c]


def test_drain_more_than_size_returns_all():
    q = MemoryQueue(max_size=10)
    q.enqueue(_ev("a"))
    q.enqueue(_ev("b"))
    drained = q.drain(50)
    assert len(drained) == 2
    assert q.is_empty() is True
    assert q.size() == 0


def test_overflow_drops_oldest_and_calls_callback():
    captured: list[int] = []

    def on_overflow(n: int) -> None:
        captured.append(n)

    q = MemoryQueue(max_size=3, on_overflow=on_overflow)
    events = [_ev(name) for name in ("a", "b", "c", "d", "e")]
    for e in events:
        q.enqueue(e)

    assert q.size() == 3
    # oldest two ("a", "b") were dropped — last 3 remain.
    remaining = q.peek(10)
    assert [e.insert_id for e in remaining] == ["c", "d", "e"]
    # Callback fired twice: once when overflowing past 3 (drop 1) twice.
    assert captured == [1, 1]


def test_overflow_callback_exception_is_swallowed():
    def boom(_n: int) -> None:
        raise RuntimeError("nope")

    q = MemoryQueue(max_size=1, on_overflow=boom)
    q.enqueue(_ev("a"))
    # Must not raise even though callback throws.
    q.enqueue(_ev("b"))
    assert q.size() == 1
    assert q.peek(1)[0].insert_id == "b"


def test_clear_empties_queue():
    q = MemoryQueue(max_size=3)
    q.enqueue(_ev("a"))
    q.enqueue(_ev("b"))
    q.clear()
    assert q.is_empty() is True
    assert q.size() == 0
    assert q.peek(10) == []
