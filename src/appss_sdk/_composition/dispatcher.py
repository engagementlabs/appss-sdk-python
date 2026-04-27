"""Batch dispatcher: drives the retry loop around ``ITransport``.

Two invariants matter:

* On a 401 response the dispatcher latches ``stopped=True`` and refuses every
  subsequent ``dispatch`` call — the SDK must not keep poking a revoked API key.
* When the retry policy is exhausted the dispatcher returns
  ``MaxRetriesExceededError`` rather than raising; the caller decides how to
  surface the error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from appss_sdk._composition.error_factory import create_transport_error
from appss_sdk._domain.response import TransportAction, handle_response
from appss_sdk._domain.retry import RetryPolicy
from appss_sdk._ports import ILogger, ITransport
from appss_sdk.errors import AppssError, MaxRetriesExceededError


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """Outcome of a single ``BatchDispatcher.dispatch`` call."""

    success: bool
    split_requested: bool = False
    error: AppssError | None = None


class BatchDispatcher:
    """Send a single body via ``ITransport`` with retries and 401 latching."""

    def __init__(
        self,
        transport: ITransport,
        retry_policy: RetryPolicy,
        logger: ILogger,
    ) -> None:
        self._transport = transport
        self._retry_policy = retry_policy
        self._logger = logger
        self._stopped = False

    @property
    def stopped(self) -> bool:
        return self._stopped

    async def dispatch(
        self,
        path: str,
        body: Any,
        headers: dict[str, str],
    ) -> DispatchResult:
        if self._stopped:
            self._logger.warn("Sends stopped (API key revoked)")
            return DispatchResult(success=False)

        attempt = 1
        while self._retry_policy.should_retry(attempt):
            try:
                response = await self._transport.send(path, body, headers)
            except Exception as exc:
                self._logger.warn(
                    "Transport threw",
                    {"error": str(exc), "attempt": attempt},
                )
                if not self._retry_policy.should_retry(attempt + 1):
                    return DispatchResult(success=False, error=MaxRetriesExceededError())
                await RetryPolicy.wait(self._retry_policy.get_delay_ms(attempt))
                attempt += 1
                continue

            result = handle_response(response)
            action = result.action

            if action is TransportAction.SUCCESS:
                self._logger.debug("Request sent", {"path": path})
                return DispatchResult(success=True)

            if action is TransportAction.SPLIT_AND_RETRY:
                return DispatchResult(success=False, split_requested=True)

            if action is TransportAction.STOP:
                self._stopped = True
                error: AppssError | None = (
                    create_transport_error(result.error_code, result.error_message)
                    if result.error_code is not None
                    else None
                )
                return DispatchResult(success=False, error=error)

            if action is TransportAction.DROP:
                drop_error: AppssError | None = (
                    create_transport_error(result.error_code, result.error_message)
                    if result.error_code is not None
                    else None
                )
                return DispatchResult(success=False, error=drop_error)

            if action is TransportAction.RATE_LIMIT:
                delay = (
                    result.retry_after_ms
                    if result.retry_after_ms is not None
                    else self._retry_policy.get_delay_ms(attempt)
                )
                self._logger.warn("Rate limited", {"retry_after_ms": delay})
                await RetryPolicy.wait(delay)
                attempt += 1
                continue

            if action is TransportAction.RETRY:
                self._logger.warn(
                    result.error_message or "Retrying",
                    {"attempt": attempt},
                )
                await RetryPolicy.wait(self._retry_policy.get_delay_ms(attempt))
                attempt += 1
                continue

        return DispatchResult(success=False, error=MaxRetriesExceededError())
