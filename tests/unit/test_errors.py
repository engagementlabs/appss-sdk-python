"""Tests for the SDK error hierarchy."""

import pytest

from appss_sdk import (
    ApiKeyRevokedError,
    AppssError,
    ErrorCode,
    InvalidApiKeyError,
    MaxRetriesExceededError,
    NetworkError,
    NotIdentifiedError,
    NotInitializedError,
    ProtocolError,
    QueueOverflowError,
    RateLimitError,
)


def test_error_code_values_equal_their_names():
    assert ErrorCode.NOT_INITIALIZED == "NOT_INITIALIZED"
    assert ErrorCode.NOT_IDENTIFIED == "NOT_IDENTIFIED"
    assert ErrorCode.INVALID_API_KEY == "INVALID_API_KEY"
    assert ErrorCode.NETWORK_ERROR == "NETWORK_ERROR"
    assert ErrorCode.RATE_LIMITED == "RATE_LIMITED"
    assert ErrorCode.API_KEY_REVOKED == "API_KEY_REVOKED"
    assert ErrorCode.PROTOCOL_ERROR == "PROTOCOL_ERROR"
    assert ErrorCode.QUEUE_OVERFLOW == "QUEUE_OVERFLOW"
    assert ErrorCode.MAX_RETRIES_EXCEEDED == "MAX_RETRIES_EXCEEDED"


def test_error_code_has_exactly_nine_members():
    assert len(list(ErrorCode)) == 9


def test_appss_error_base_class_constructs_directly():
    err = AppssError("boom", ErrorCode.NETWORK_ERROR, "warn", True)
    assert isinstance(err, Exception)
    assert err.code == ErrorCode.NETWORK_ERROR
    assert err.severity == "warn"
    assert err.retryable is True
    assert str(err) == "boom"


def test_appss_error_attributes_are_read_only():
    err = AppssError("m", ErrorCode.NETWORK_ERROR, "warn", True)
    with pytest.raises(AttributeError):
        err.code = ErrorCode.PROTOCOL_ERROR  # type: ignore[misc]


def test_not_initialized_error_defaults():
    err = NotInitializedError()
    assert isinstance(err, AppssError)
    assert isinstance(err, Exception)
    assert err.code == ErrorCode.NOT_INITIALIZED
    assert err.severity == "warn"
    assert err.retryable is False
    assert "init()" in str(err)


def test_not_identified_error_defaults():
    err = NotIdentifiedError()
    assert err.code == ErrorCode.NOT_IDENTIFIED
    assert err.severity == "warn"
    assert err.retryable is False
    assert "identify()" in str(err)


def test_invalid_api_key_error_defaults():
    err = InvalidApiKeyError()
    assert err.code == ErrorCode.INVALID_API_KEY
    assert err.severity == "error"
    assert err.retryable is False


def test_network_error_is_retryable_warn():
    err = NetworkError()
    assert err.code == ErrorCode.NETWORK_ERROR
    assert err.severity == "warn"
    assert err.retryable is True


def test_rate_limit_error_default_retry_after_is_none():
    err = RateLimitError()
    assert err.code == ErrorCode.RATE_LIMITED
    assert err.severity == "warn"
    assert err.retryable is True
    assert err.retry_after_ms is None


def test_rate_limit_error_records_retry_after_ms():
    err = RateLimitError(retry_after_ms=5000)
    assert err.retry_after_ms == 5000


def test_rate_limit_error_custom_message_and_retry():
    err = RateLimitError("slow down", retry_after_ms=2500)
    assert str(err) == "slow down"
    assert err.retry_after_ms == 2500


def test_api_key_revoked_error_defaults():
    err = ApiKeyRevokedError()
    assert err.code == ErrorCode.API_KEY_REVOKED
    assert err.severity == "error"
    assert err.retryable is False


def test_protocol_error_defaults():
    err = ProtocolError()
    assert err.code == ErrorCode.PROTOCOL_ERROR
    assert err.severity == "error"
    assert err.retryable is False


def test_queue_overflow_error_records_dropped_count_in_message():
    err = QueueOverflowError(42)
    assert err.code == ErrorCode.QUEUE_OVERFLOW
    assert err.severity == "warn"
    assert err.retryable is False
    assert err.dropped_count == 42
    assert "42" in str(err)


def test_max_retries_exceeded_error_defaults():
    err = MaxRetriesExceededError()
    assert err.code == ErrorCode.MAX_RETRIES_EXCEEDED
    assert err.severity == "error"
    assert err.retryable is False


def test_subclasses_accept_custom_message():
    err = NotInitializedError("custom")
    assert str(err) == "custom"
    assert err.code == ErrorCode.NOT_INITIALIZED


def test_errors_can_be_raised_and_caught_as_appss_error():
    with pytest.raises(AppssError) as excinfo:
        raise NetworkError()
    assert excinfo.value.code == ErrorCode.NETWORK_ERROR


def test_errors_can_be_caught_by_specific_subclass():
    with pytest.raises(QueueOverflowError) as excinfo:
        raise QueueOverflowError(7)
    assert excinfo.value.dropped_count == 7


def test_all_subclasses_are_appss_error_subclasses():
    for cls in (
        NotInitializedError,
        NotIdentifiedError,
        InvalidApiKeyError,
        NetworkError,
        RateLimitError,
        ApiKeyRevokedError,
        ProtocolError,
        MaxRetriesExceededError,
    ):
        assert issubclass(cls, AppssError)
