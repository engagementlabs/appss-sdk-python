"""Configuration models, validation, and resolution.

Validation raises :class:`TypeError` for malformed numeric inputs (non-finite,
wrong type, out of range). Only an empty or missing ``api_key`` raises
:class:`InvalidApiKeyError` so it can be caught distinctly from generic input errors.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

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
from appss_sdk._ports import IEventQueue, ILogger
from appss_sdk._types import OnErrorCallback
from appss_sdk.errors import InvalidApiKeyError


class RetryConfig(BaseModel):
    """Retry policy.

    All fields are optional so a user can override one knob and inherit the rest.
    ``resolve_config`` produces an instance with every field populated.
    """

    model_config = ConfigDict(frozen=True)

    max_retries: int | None = None
    base_backoff_ms: float | None = None
    max_backoff_ms: float | None = None


class AppssConfig(BaseModel):
    """User-facing configuration.

    Only ``api_key`` is required. Numeric fields are validated by
    :func:`validate_config` (not by pydantic) so the error type matches the JS
    contract (``TypeError`` for malformed numbers).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    api_key: str
    endpoint: str | None = None
    flush_interval_ms: float | None = None
    batch_size: int | None = None
    max_queue_size: int | None = None
    retry: RetryConfig | None = None
    debug: bool = False
    logger: ILogger | None = None
    queue: IEventQueue | None = None
    on_error: OnErrorCallback | None = None
    request_timeout_ms: float | None = None


@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    """Fully-resolved configuration. All defaults applied."""

    api_key: str
    endpoint: str
    flush_interval_ms: int
    batch_size: int
    max_queue_size: int
    retry: RetryConfig
    debug: bool
    request_timeout_ms: int
    logger: ILogger | None = None
    queue: IEventQueue | None = None
    on_error: OnErrorCallback | None = None


def _assert_positive_number(value: object | None, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a positive number, got {value!r}")
    if not math.isfinite(float(value)) or float(value) <= 0:
        raise TypeError(f"{name} must be a positive number, got {value!r}")


def _assert_positive_integer(value: object | None, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TypeError(f"{name} must be a positive integer, got {value!r}")


def _assert_non_negative_integer(value: object | None, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TypeError(f"{name} must be a non-negative integer, got {value!r}")


def _coerce_to_dict(config: AppssConfig | dict[str, Any]) -> dict[str, Any]:
    if isinstance(config, AppssConfig):
        return config.model_dump()
    return dict(config)


def _coerce_retry_to_dict(retry: object) -> dict[str, Any] | None:
    if retry is None:
        return None
    if isinstance(retry, RetryConfig):
        return retry.model_dump()
    if isinstance(retry, dict):
        return dict(retry)
    raise TypeError(f"retry must be a RetryConfig or dict, got {type(retry).__name__}")


def validate_config(config: AppssConfig | dict[str, Any]) -> None:
    """Validate a config object or dict.

    Raises:
        InvalidApiKeyError: ``api_key`` is missing, not a string, or empty after strip.
        TypeError: any numeric field is not a finite positive (or non-negative) number.
    """
    raw = _coerce_to_dict(config)

    api_key = raw.get("api_key")
    if not isinstance(api_key, str) or api_key.strip() == "":
        raise InvalidApiKeyError("API key is required and cannot be empty.")

    _assert_positive_number(raw.get("flush_interval_ms"), "flush_interval_ms")
    _assert_positive_integer(raw.get("batch_size"), "batch_size")
    _assert_positive_integer(raw.get("max_queue_size"), "max_queue_size")
    _assert_positive_number(raw.get("request_timeout_ms"), "request_timeout_ms")

    retry = _coerce_retry_to_dict(raw.get("retry"))
    if retry is not None:
        _assert_non_negative_integer(retry.get("max_retries"), "retry.max_retries")
        _assert_positive_number(retry.get("base_backoff_ms"), "retry.base_backoff_ms")
        _assert_positive_number(retry.get("max_backoff_ms"), "retry.max_backoff_ms")


def _resolved_retry(user: RetryConfig | None) -> RetryConfig:
    return RetryConfig(
        max_retries=(
            user.max_retries
            if user is not None and user.max_retries is not None
            else DEFAULT_MAX_RETRIES
        ),
        base_backoff_ms=(
            user.base_backoff_ms
            if user is not None and user.base_backoff_ms is not None
            else DEFAULT_BASE_BACKOFF_MS
        ),
        max_backoff_ms=(
            user.max_backoff_ms
            if user is not None and user.max_backoff_ms is not None
            else DEFAULT_MAX_BACKOFF_MS
        ),
    )


def resolve_config(config: AppssConfig) -> ResolvedConfig:
    """Apply SDK defaults and produce an immutable :class:`ResolvedConfig`.

    Mirrors the JS ``resolveConfig`` contract:
    - trailing slashes stripped from ``endpoint`` (``rstrip('/')``)
    - ``None``-fallback (``??``) semantics so falsy-but-valid values like ``0`` survive
    """
    endpoint_raw = config.endpoint if config.endpoint is not None else DEFAULT_ENDPOINT
    endpoint = endpoint_raw.rstrip("/")

    flush_interval_ms = (
        int(config.flush_interval_ms)
        if config.flush_interval_ms is not None
        else DEFAULT_FLUSH_INTERVAL_MS
    )
    request_timeout_ms = (
        int(config.request_timeout_ms)
        if config.request_timeout_ms is not None
        else DEFAULT_REQUEST_TIMEOUT_MS
    )

    return ResolvedConfig(
        api_key=config.api_key,
        endpoint=endpoint,
        flush_interval_ms=flush_interval_ms,
        batch_size=config.batch_size if config.batch_size is not None else DEFAULT_BATCH_SIZE,
        max_queue_size=(
            config.max_queue_size if config.max_queue_size is not None else MAX_QUEUE_SIZE
        ),
        retry=_resolved_retry(config.retry),
        debug=config.debug,
        request_timeout_ms=request_timeout_ms,
        logger=config.logger,
        queue=config.queue,
        on_error=config.on_error,
    )
