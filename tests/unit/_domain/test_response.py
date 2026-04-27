"""Unit tests for appss_sdk._domain.response."""

from __future__ import annotations

import pytest

from appss_sdk._domain.response import HandleResult, TransportAction, handle_response
from appss_sdk._types import TransportResponse
from appss_sdk.errors import ErrorCode


def _resp(status: int, headers: dict[str, str] | None = None) -> TransportResponse:
    return TransportResponse(status_code=status, headers=headers or {}, body=None)


@pytest.mark.parametrize("status", [200, 201, 204, 299])
def test_2xx_success(status: int) -> None:
    result = handle_response(_resp(status))
    assert result.action is TransportAction.SUCCESS
    assert result.error_code is None
    assert result.error_message is None
    assert result.retry_after_ms is None


def test_400_drop_protocol_error() -> None:
    result = handle_response(_resp(400))
    assert result == HandleResult(
        action=TransportAction.DROP,
        error_code=ErrorCode.PROTOCOL_ERROR,
        error_message="Bad request",
    )


def test_401_stop_api_key_revoked() -> None:
    result = handle_response(_resp(401))
    assert result.action is TransportAction.STOP
    assert result.error_code is ErrorCode.API_KEY_REVOKED
    assert result.error_message == "API key revoked"


@pytest.mark.parametrize("status", [403, 404])
def test_other_4xx_drop_protocol_error(status: int) -> None:
    result = handle_response(_resp(status))
    assert result.action is TransportAction.DROP
    assert result.error_code is ErrorCode.PROTOCOL_ERROR
    assert result.error_message is not None
    assert str(status) in result.error_message


def test_413_split_and_retry() -> None:
    result = handle_response(_resp(413))
    assert result.action is TransportAction.SPLIT_AND_RETRY


def test_429_no_header() -> None:
    result = handle_response(_resp(429))
    assert result.action is TransportAction.RATE_LIMIT
    assert result.retry_after_ms is None


def test_429_retry_after_integer_seconds() -> None:
    result = handle_response(_resp(429, {"Retry-After": "5"}))
    assert result.action is TransportAction.RATE_LIMIT
    assert result.retry_after_ms == 5000


def test_429_retry_after_fractional_seconds() -> None:
    result = handle_response(_resp(429, {"Retry-After": "0.5"}))
    assert result.action is TransportAction.RATE_LIMIT
    assert result.retry_after_ms == 500


def test_429_retry_after_garbage() -> None:
    result = handle_response(_resp(429, {"Retry-After": "garbage"}))
    assert result.action is TransportAction.RATE_LIMIT
    assert result.retry_after_ms is None


def test_429_retry_after_lowercase_header() -> None:
    result = handle_response(_resp(429, {"retry-after": "2"}))
    assert result.action is TransportAction.RATE_LIMIT
    assert result.retry_after_ms == 2000


def test_429_retry_after_negative_yields_none() -> None:
    result = handle_response(_resp(429, {"Retry-After": "-1"}))
    assert result.retry_after_ms is None


@pytest.mark.parametrize("status", [500, 503, 599])
def test_5xx_retry_network_error(status: int) -> None:
    result = handle_response(_resp(status))
    assert result.action is TransportAction.RETRY
    assert result.error_code is ErrorCode.NETWORK_ERROR
    assert result.error_message is not None
    assert str(status) in result.error_message


def test_600_drop_out_of_5xx() -> None:
    result = handle_response(_resp(600))
    assert result.action is TransportAction.DROP
    assert result.error_code is ErrorCode.PROTOCOL_ERROR


def test_100_drop() -> None:
    result = handle_response(_resp(100))
    assert result.action is TransportAction.DROP
    assert result.error_code is ErrorCode.PROTOCOL_ERROR
