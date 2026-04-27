"""Tests for AppssConfig, RetryConfig, validate_config, and resolve_config."""

import dataclasses
import math

import pytest
from pydantic import ValidationError

from appss_sdk import (
    AppssConfig,
    InvalidApiKeyError,
    ResolvedConfig,
    RetryConfig,
)
from appss_sdk._config import resolve_config, validate_config
from appss_sdk._constants import (
    DEFAULT_BASE_BACKOFF_MS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_ENDPOINT,
    DEFAULT_FLUSH_INTERVAL_MS,
    DEFAULT_MAX_BACKOFF_MS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_TIMEOUT_MS,
    MAX_QUEUE_SIZE,
)

# ---------- api_key validation -------------------------------------------------


def test_validate_config_rejects_empty_api_key():
    with pytest.raises(InvalidApiKeyError):
        validate_config({"api_key": ""})


def test_validate_config_rejects_whitespace_only_api_key():
    with pytest.raises(InvalidApiKeyError):
        validate_config({"api_key": "   "})


def test_validate_config_rejects_missing_api_key():
    with pytest.raises(InvalidApiKeyError):
        validate_config({})


def test_validate_config_rejects_non_string_api_key():
    with pytest.raises(InvalidApiKeyError):
        validate_config({"api_key": 123})  # type: ignore[dict-item]


def test_validate_config_accepts_minimal_valid_dict():
    validate_config({"api_key": "k"})  # no exception


def test_validate_config_accepts_minimal_valid_model():
    validate_config(AppssConfig(api_key="k"))  # no exception


# ---------- numeric assertion helpers (positive number) ------------------------


@pytest.mark.parametrize("bad_value", [0, -1, float("nan"), float("inf"), -float("inf")])
def test_flush_interval_ms_rejects_invalid_numbers(bad_value):
    with pytest.raises(TypeError):
        validate_config({"api_key": "k", "flush_interval_ms": bad_value})


def test_flush_interval_ms_accepts_fractional_positive():
    validate_config({"api_key": "k", "flush_interval_ms": 0.5})  # no exception


def test_flush_interval_ms_accepts_int():
    validate_config({"api_key": "k", "flush_interval_ms": 100})


def test_request_timeout_ms_rejects_zero():
    with pytest.raises(TypeError):
        validate_config({"api_key": "k", "request_timeout_ms": 0})


def test_request_timeout_ms_rejects_nan():
    with pytest.raises(TypeError):
        validate_config({"api_key": "k", "request_timeout_ms": float("nan")})


# ---------- numeric assertion helpers (positive integer) -----------------------


@pytest.mark.parametrize("bad_value", [0, -1, 2.5, float("nan"), float("inf")])
def test_batch_size_rejects_invalid_values(bad_value):
    with pytest.raises(TypeError):
        validate_config({"api_key": "k", "batch_size": bad_value})


def test_batch_size_rejects_bool():
    with pytest.raises(TypeError):
        validate_config({"api_key": "k", "batch_size": True})


def test_batch_size_accepts_positive_int():
    validate_config({"api_key": "k", "batch_size": 10})


@pytest.mark.parametrize("bad_value", [0, -1, 2.5, float("nan"), float("inf")])
def test_max_queue_size_rejects_invalid_values(bad_value):
    with pytest.raises(TypeError):
        validate_config({"api_key": "k", "max_queue_size": bad_value})


# ---------- numeric assertion helpers (non-negative integer) -------------------


@pytest.mark.parametrize("bad_value", [-1, 2.5, float("nan"), float("inf")])
def test_retry_max_retries_rejects_invalid_values(bad_value):
    with pytest.raises(TypeError):
        validate_config({"api_key": "k", "retry": {"max_retries": bad_value}})


def test_retry_max_retries_zero_is_valid():
    """max_retries=0 means 'do not retry' — must NOT throw."""
    validate_config({"api_key": "k", "retry": {"max_retries": 0}})


def test_retry_base_backoff_ms_rejects_zero():
    with pytest.raises(TypeError):
        validate_config({"api_key": "k", "retry": {"base_backoff_ms": 0}})


def test_retry_max_backoff_ms_rejects_negative():
    with pytest.raises(TypeError):
        validate_config({"api_key": "k", "retry": {"max_backoff_ms": -1}})


def test_validate_config_accepts_full_valid_retry():
    validate_config(
        {
            "api_key": "k",
            "retry": {"max_retries": 3, "base_backoff_ms": 500, "max_backoff_ms": 8000},
        }
    )


def test_validate_config_rejects_non_dict_non_retry_object_for_retry():
    with pytest.raises(TypeError):
        validate_config({"api_key": "k", "retry": "not-a-config"})  # type: ignore[dict-item]


# ---------- resolve_config defaults --------------------------------------------


def test_resolve_config_applies_all_defaults_when_minimal():
    resolved = resolve_config(AppssConfig(api_key="k"))
    assert isinstance(resolved, ResolvedConfig)
    assert resolved.api_key == "k"
    assert resolved.endpoint == DEFAULT_ENDPOINT
    assert resolved.flush_interval_ms == DEFAULT_FLUSH_INTERVAL_MS
    assert resolved.batch_size == DEFAULT_BATCH_SIZE
    assert resolved.max_queue_size == MAX_QUEUE_SIZE
    assert resolved.request_timeout_ms == DEFAULT_REQUEST_TIMEOUT_MS
    assert resolved.debug is False
    assert resolved.logger is None
    assert resolved.queue is None
    assert resolved.on_error is None


def test_resolve_config_default_retry_has_full_defaults():
    resolved = resolve_config(AppssConfig(api_key="k"))
    assert resolved.retry.max_retries == DEFAULT_MAX_RETRIES
    assert resolved.retry.base_backoff_ms == DEFAULT_BASE_BACKOFF_MS
    assert resolved.retry.max_backoff_ms == DEFAULT_MAX_BACKOFF_MS


def test_resolve_config_strips_single_trailing_slash_from_endpoint():
    resolved = resolve_config(AppssConfig(api_key="k", endpoint="https://x.example.com/"))
    assert resolved.endpoint == "https://x.example.com"


def test_resolve_config_strips_multiple_trailing_slashes_from_endpoint():
    resolved = resolve_config(AppssConfig(api_key="k", endpoint="https://x.example.com//"))
    assert resolved.endpoint == "https://x.example.com"


def test_resolve_config_keeps_endpoint_without_trailing_slash():
    resolved = resolve_config(AppssConfig(api_key="k", endpoint="https://x.example.com"))
    assert resolved.endpoint == "https://x.example.com"


def test_resolve_config_overrides_numeric_fields_when_set():
    resolved = resolve_config(
        AppssConfig(
            api_key="k",
            flush_interval_ms=1234,
            batch_size=7,
            max_queue_size=42,
            request_timeout_ms=9999,
            debug=True,
        )
    )
    assert resolved.flush_interval_ms == 1234
    assert resolved.batch_size == 7
    assert resolved.max_queue_size == 42
    assert resolved.request_timeout_ms == 9999
    assert resolved.debug is True


def test_resolve_config_partial_retry_via_model_merges_with_defaults():
    config = AppssConfig(api_key="k", retry=RetryConfig(max_retries=2))
    resolved = resolve_config(config)
    assert resolved.retry.max_retries == 2
    assert resolved.retry.base_backoff_ms == DEFAULT_BASE_BACKOFF_MS
    assert resolved.retry.max_backoff_ms == DEFAULT_MAX_BACKOFF_MS


def test_resolve_config_partial_retry_via_dict_merges_with_defaults():
    config = AppssConfig.model_validate({"api_key": "k", "retry": {"base_backoff_ms": 250}})
    resolved = resolve_config(config)
    assert resolved.retry.max_retries == DEFAULT_MAX_RETRIES
    assert resolved.retry.base_backoff_ms == 250
    assert resolved.retry.max_backoff_ms == DEFAULT_MAX_BACKOFF_MS


def test_resolve_config_preserves_max_retries_zero():
    """max_retries=0 must not be overridden by default (?? semantics, not || )."""
    config = AppssConfig(api_key="k", retry=RetryConfig(max_retries=0))
    resolved = resolve_config(config)
    assert resolved.retry.max_retries == 0


def test_resolve_config_full_retry_override():
    config = AppssConfig(
        api_key="k",
        retry=RetryConfig(max_retries=10, base_backoff_ms=200, max_backoff_ms=20_000),
    )
    resolved = resolve_config(config)
    assert resolved.retry.max_retries == 10
    assert resolved.retry.base_backoff_ms == 200
    assert resolved.retry.max_backoff_ms == 20_000


# ---------- AppssConfig pydantic surface ---------------------------------------


def test_appss_config_requires_api_key():
    with pytest.raises(ValidationError):
        AppssConfig()  # type: ignore[call-arg]


def test_retry_config_is_frozen():
    rc = RetryConfig(max_retries=3)
    with pytest.raises(ValidationError):
        rc.max_retries = 9  # type: ignore[misc]


def test_resolved_config_is_frozen_dataclass():
    resolved = resolve_config(AppssConfig(api_key="k"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        resolved.api_key = "other"  # type: ignore[misc]


# ---------- assertion helper edge cases (sanity) -------------------------------


def test_nan_is_not_finite_sanity_check():
    """Sanity that math.isfinite agrees with our validator."""
    assert math.isfinite(0.5) is True
    assert math.isfinite(float("nan")) is False
    assert math.isfinite(float("inf")) is False
