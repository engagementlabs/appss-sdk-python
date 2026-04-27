"""Unit tests for appss_sdk._domain.retry."""

from __future__ import annotations

import asyncio

import pytest

from appss_sdk._config import RetryConfig
from appss_sdk._domain.retry import RetryPolicy


def _policy(
    *,
    max_retries: int = 3,
    base: float = 1000,
    cap: float = 16000,
    jitter: float = 0.0,
) -> RetryPolicy:
    return RetryPolicy(
        RetryConfig(max_retries=max_retries, base_backoff_ms=base, max_backoff_ms=cap),
        jitter_factor=jitter,
    )


def test_should_retry_within_limit() -> None:
    p = _policy(max_retries=3)
    assert p.should_retry(1) is True
    assert p.should_retry(3) is True


def test_should_retry_at_limit_plus_one_is_false() -> None:
    p = _policy(max_retries=3)
    assert p.should_retry(4) is False


def test_should_retry_attempt_zero_corner_case() -> None:
    # `attempt <= max_retries`, so attempt=0 is True for any non-negative limit.
    p = _policy(max_retries=3)
    assert p.should_retry(0) is True


def test_should_retry_max_zero_disables_retries() -> None:
    p = _policy(max_retries=0)
    assert p.should_retry(1) is False
    assert p.should_retry(2) is False


def test_get_delay_ms_exponential_no_jitter() -> None:
    p = _policy(max_retries=10, base=1000, cap=16000, jitter=0.0)
    assert p.get_delay_ms(1) == 1000
    assert p.get_delay_ms(2) == 2000
    assert p.get_delay_ms(3) == 4000
    assert p.get_delay_ms(4) == 8000
    assert p.get_delay_ms(5) == 16000


def test_get_delay_ms_clamped_to_max() -> None:
    p = _policy(max_retries=10, base=1000, cap=16000, jitter=0.0)
    assert p.get_delay_ms(6) == 16000
    assert p.get_delay_ms(20) == 16000


def test_get_delay_ms_with_jitter_in_range() -> None:
    p = _policy(max_retries=10, base=1000, cap=16000, jitter=0.2)
    for _ in range(50):
        delay = p.get_delay_ms(1)
        assert 800 <= delay <= 1200


def test_get_delay_ms_never_negative() -> None:
    p = _policy(max_retries=10, base=1000, cap=16000, jitter=0.2)
    for attempt in range(1, 8):
        assert p.get_delay_ms(attempt) >= 0


async def test_wait_zero_completes_immediately() -> None:
    loop = asyncio.get_event_loop()
    start = loop.time()
    await RetryPolicy.wait(0)
    elapsed_ms = (loop.time() - start) * 1000
    assert elapsed_ms < 20


async def test_wait_negative_completes_immediately() -> None:
    loop = asyncio.get_event_loop()
    start = loop.time()
    await RetryPolicy.wait(-100)
    elapsed_ms = (loop.time() - start) * 1000
    assert elapsed_ms < 20


@pytest.mark.asyncio
async def test_wait_50ms_takes_at_least_40ms() -> None:
    loop = asyncio.get_event_loop()
    start = loop.time()
    await RetryPolicy.wait(50)
    elapsed_ms = (loop.time() - start) * 1000
    assert elapsed_ms >= 40


def test_uses_defaults_when_config_fields_none() -> None:
    p = RetryPolicy(RetryConfig(), jitter_factor=0.0)
    # Default max_retries=5, base=1000, cap=16000
    assert p.should_retry(5) is True
    assert p.should_retry(6) is False
    assert p.get_delay_ms(1) == 1000
    assert p.get_delay_ms(5) == 16000
