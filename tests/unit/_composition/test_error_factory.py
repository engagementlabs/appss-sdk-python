"""Unit tests for create_transport_error."""

from __future__ import annotations

from appss_sdk._composition.error_factory import create_transport_error
from appss_sdk.errors import (
    ApiKeyRevokedError,
    ErrorCode,
    InvalidApiKeyError,
    MaxRetriesExceededError,
    NetworkError,
    ProtocolError,
    RateLimitError,
)


def test_network_error_default_message() -> None:
    err = create_transport_error(ErrorCode.NETWORK_ERROR)
    assert isinstance(err, NetworkError)
    assert err.code is ErrorCode.NETWORK_ERROR


def test_network_error_with_custom_message() -> None:
    err = create_transport_error(ErrorCode.NETWORK_ERROR, "boom")
    assert isinstance(err, NetworkError)
    assert str(err) == "boom"


def test_rate_limited_carries_retry_after_ms() -> None:
    err = create_transport_error(ErrorCode.RATE_LIMITED, "slow down", retry_after_ms=5000)
    assert isinstance(err, RateLimitError)
    assert err.retry_after_ms == 5000


def test_rate_limited_without_retry_after_ms_defaults_to_none() -> None:
    err = create_transport_error(ErrorCode.RATE_LIMITED)
    assert isinstance(err, RateLimitError)
    assert err.retry_after_ms is None


def test_api_key_revoked() -> None:
    err = create_transport_error(ErrorCode.API_KEY_REVOKED)
    assert isinstance(err, ApiKeyRevokedError)


def test_protocol_error_explicit() -> None:
    err = create_transport_error(ErrorCode.PROTOCOL_ERROR, "bad request")
    assert isinstance(err, ProtocolError)
    assert str(err) == "bad request"


def test_invalid_api_key() -> None:
    err = create_transport_error(ErrorCode.INVALID_API_KEY)
    assert isinstance(err, InvalidApiKeyError)


def test_max_retries_exceeded() -> None:
    err = create_transport_error(ErrorCode.MAX_RETRIES_EXCEEDED)
    assert isinstance(err, MaxRetriesExceededError)


def test_unknown_code_falls_back_to_protocol_error() -> None:
    # NOT_INITIALIZED is not in the explicit mapping → fallback to ProtocolError.
    err = create_transport_error(ErrorCode.NOT_INITIALIZED)
    assert isinstance(err, ProtocolError)
    assert "NOT_INITIALIZED" in str(err)
