from __future__ import annotations

from dataclasses import dataclass

import httpx

TELEGRAM_API_BASE = "https://api.telegram.org"

RETRYABLE_REASONS = frozenset({"throttled", "network", "server_error"})


@dataclass(slots=True)
class SendOutcome:
    ok: bool
    tg_message_id: int | None = None
    reason: str | None = None
    retry_after: int | None = None


def _classify(status_code: int, description: str) -> str:
    desc = description.lower()
    if status_code == 429:
        return "throttled"
    if 500 <= status_code < 600:
        return "server_error"
    if status_code == 401:
        return "token_revoked"
    if status_code == 403:
        return "blocked" if "blocked" in desc else "forbidden"
    return "bad_request"


class TelegramSender:
    def __init__(self, base_url: str = TELEGRAM_API_BASE, timeout_ms: int = 15_000) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_ms / 1000)

    async def send_message(
        self,
        token: str,
        chat_id: int,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> SendOutcome:
        url = f"{self._base_url}/bot{token}/sendMessage"
        body: dict = {"chat_id": chat_id, "text": text}
        if parse_mode:
            body["parse_mode"] = parse_mode
        if reply_markup:
            body["reply_markup"] = reply_markup

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=body)
        except httpx.HTTPError:
            return SendOutcome(ok=False, reason="network")

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        if response.status_code == 200 and payload.get("ok"):
            result = payload.get("result") or {}
            return SendOutcome(ok=True, tg_message_id=result.get("message_id"))

        reason = _classify(response.status_code, payload.get("description", ""))
        parameters = payload.get("parameters")
        retry_after = (
            parameters.get("retry_after") if isinstance(parameters, dict) else None
        )
        return SendOutcome(ok=False, reason=reason, retry_after=retry_after)
