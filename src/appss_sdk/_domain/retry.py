"""Retry policy: exponential backoff with jitter."""

from __future__ import annotations

import asyncio
import random

from appss_sdk._config import RetryConfig
from appss_sdk._constants import (
    DEFAULT_BASE_BACKOFF_MS,
    DEFAULT_JITTER_FACTOR,
    DEFAULT_MAX_BACKOFF_MS,
    DEFAULT_MAX_RETRIES,
)


class RetryPolicy:
    """Exponential-backoff retry policy with optional uniform jitter.

    ``attempt`` is 1-indexed: the first retry is attempt=1.
    """

    def __init__(
        self,
        config: RetryConfig,
        *,
        jitter_factor: float = DEFAULT_JITTER_FACTOR,
    ) -> None:
        self._max_retries: int = (
            config.max_retries if config.max_retries is not None else DEFAULT_MAX_RETRIES
        )
        self._base_backoff_ms: float = (
            config.base_backoff_ms
            if config.base_backoff_ms is not None
            else DEFAULT_BASE_BACKOFF_MS
        )
        self._max_backoff_ms: float = (
            config.max_backoff_ms if config.max_backoff_ms is not None else DEFAULT_MAX_BACKOFF_MS
        )
        self._jitter_factor: float = jitter_factor

    def should_retry(self, attempt: int) -> bool:
        """Return ``True`` while ``attempt`` does not exceed ``max_retries``."""
        return attempt <= self._max_retries

    def get_delay_ms(self, attempt: int) -> int:
        """Compute the delay in milliseconds for the given 1-indexed attempt."""
        base = min(self._base_backoff_ms * (2 ** (attempt - 1)), self._max_backoff_ms)
        jitter = random.uniform(-self._jitter_factor, self._jitter_factor)
        delay: int = round(base * (1 + jitter))
        if delay < 0:
            return 0
        return delay

    @staticmethod
    async def wait(ms: int) -> None:
        """Sleep for ``ms`` milliseconds; non-positive values yield control immediately."""
        if ms <= 0:
            await asyncio.sleep(0)
            return
        await asyncio.sleep(ms / 1000)
