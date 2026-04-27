"""Unit tests for BatchDispatcher."""

from __future__ import annotations

from typing import Any

import pytest

from appss_sdk._composition.dispatcher import BatchDispatcher
from appss_sdk._config import RetryConfig
from appss_sdk._domain.retry import RetryPolicy
from appss_sdk._types import TransportResponse
from appss_sdk.errors import (
    ApiKeyRevokedError,
    MaxRetriesExceededError,
    ProtocolError,
)


class MockTransport:
    def __init__(self, responses: list[TransportResponse | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, Any, dict[str, str]]] = []

    async def send(
        self,
        path: str,
        body: Any,
        headers: dict[str, str],
    ) -> TransportResponse:
        self.calls.append((path, body, headers))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class NoopLogger:
    def debug(self, message: str, context: dict[str, Any] | None = None) -> None: ...
    def info(self, message: str, context: dict[str, Any] | None = None) -> None: ...
    def warn(self, message: str, context: dict[str, Any] | None = None) -> None: ...
    def error(self, message: str, context: dict[str, Any] | None = None) -> None: ...


def _fast_policy(max_retries: int = 3) -> RetryPolicy:
    return RetryPolicy(
        RetryConfig(max_retries=max_retries, base_backoff_ms=1, max_backoff_ms=5),
        jitter_factor=0.0,
    )


def _resp(status: int, headers: dict[str, str] | None = None) -> TransportResponse:
    return TransportResponse(status_code=status, headers=headers or {}, body=None)


@pytest.mark.asyncio
async def test_success_first_try() -> None:
    transport = MockTransport([_resp(200)])
    dispatcher = BatchDispatcher(transport, _fast_policy(), NoopLogger())

    result = await dispatcher.dispatch("/api/v1/events", {"batch": []}, {"a": "b"})

    assert result.success is True
    assert result.error is None
    assert len(transport.calls) == 1
    assert transport.calls[0][0] == "/api/v1/events"


@pytest.mark.asyncio
async def test_500_then_200_retries_once() -> None:
    transport = MockTransport([_resp(500), _resp(200)])
    dispatcher = BatchDispatcher(transport, _fast_policy(), NoopLogger())

    result = await dispatcher.dispatch("/p", {}, {})

    assert result.success is True
    assert len(transport.calls) == 2


@pytest.mark.asyncio
async def test_repeated_500_exhausts_retries() -> None:
    transport = MockTransport([_resp(500), _resp(500), _resp(500), _resp(500)])
    dispatcher = BatchDispatcher(transport, _fast_policy(max_retries=3), NoopLogger())

    result = await dispatcher.dispatch("/p", {}, {})

    assert result.success is False
    assert isinstance(result.error, MaxRetriesExceededError)
    # max_retries=3 → should_retry true for attempts 1,2,3 → 3 calls.
    assert len(transport.calls) == 3


@pytest.mark.asyncio
async def test_401_returns_revoked_and_latches_stopped() -> None:
    transport = MockTransport([_resp(401)])
    dispatcher = BatchDispatcher(transport, _fast_policy(), NoopLogger())

    result = await dispatcher.dispatch("/p", {}, {})

    assert result.success is False
    assert isinstance(result.error, ApiKeyRevokedError)
    assert dispatcher.stopped is True
    assert len(transport.calls) == 1

    # Subsequent dispatch is a no-op: no new transport calls.
    result2 = await dispatcher.dispatch("/p", {}, {})
    assert result2.success is False
    assert result2.error is None
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_413_signals_split_request() -> None:
    transport = MockTransport([_resp(413)])
    dispatcher = BatchDispatcher(transport, _fast_policy(), NoopLogger())

    result = await dispatcher.dispatch("/p", {}, {})

    assert result.success is False
    assert result.split_requested is True
    assert result.error is None
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_429_then_success() -> None:
    transport = MockTransport(
        [
            _resp(429, {"Retry-After": "0"}),
            _resp(200),
        ]
    )
    dispatcher = BatchDispatcher(transport, _fast_policy(), NoopLogger())

    result = await dispatcher.dispatch("/p", {}, {})

    assert result.success is True
    assert len(transport.calls) == 2


@pytest.mark.asyncio
async def test_transport_exception_counts_as_retry() -> None:
    transport = MockTransport(
        [
            Exception("network gone"),
            Exception("network still gone"),
            Exception("network really gone"),
        ]
    )
    dispatcher = BatchDispatcher(transport, _fast_policy(max_retries=3), NoopLogger())

    result = await dispatcher.dispatch("/p", {}, {})

    assert result.success is False
    assert isinstance(result.error, MaxRetriesExceededError)
    assert len(transport.calls) == 3


@pytest.mark.asyncio
async def test_transport_exception_then_success() -> None:
    transport = MockTransport([Exception("blip"), _resp(200)])
    dispatcher = BatchDispatcher(transport, _fast_policy(), NoopLogger())

    result = await dispatcher.dispatch("/p", {}, {})

    assert result.success is True
    assert len(transport.calls) == 2


@pytest.mark.asyncio
async def test_400_returns_protocol_error() -> None:
    transport = MockTransport([_resp(400)])
    dispatcher = BatchDispatcher(transport, _fast_policy(), NoopLogger())

    result = await dispatcher.dispatch("/p", {}, {})

    assert result.success is False
    assert isinstance(result.error, ProtocolError)
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_zero_max_retries_returns_max_retries_error_immediately() -> None:
    transport = MockTransport([])
    dispatcher = BatchDispatcher(transport, _fast_policy(max_retries=0), NoopLogger())

    result = await dispatcher.dispatch("/p", {}, {})

    assert result.success is False
    assert isinstance(result.error, MaxRetriesExceededError)
    assert len(transport.calls) == 0
