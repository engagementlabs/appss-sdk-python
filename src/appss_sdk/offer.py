
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import time
from dataclasses import dataclass

_PREFIX = "of_"
_PAYLOAD_LEN = 21
_SIG_LEN = 16
_VERSION = 0x02


@dataclass(frozen=True)
class OfferResult:
    percent: int
    applies_to: int
    expires_at: int
    telegram_id: int
    template_id_hash: str


def _b64u_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def decode_and_verify_offer(
    token: str,
    secret: str | bytes,
    authed_user_id: int | str,
    now: int | None = None,
) -> OfferResult | None:
    """Verify an offer token entirely offline.

    Returns an :class:`OfferResult` on success, or ``None`` when the token is
    malformed, tampered, expired, or minted for a different user.

    :param token: the ``of_...`` string (e.g. from ``initDataUnsafe.start_param``)
    :param secret: per-app offer secret (Developer Settings -> Push secret)
    :param authed_user_id: telegram id from *verified* initData
    :param now: unix seconds; defaults to current time
    """
    if now is None:
        now = int(time.time())
    if not isinstance(token, str) or not token.startswith(_PREFIX):
        return None

    try:
        raw = _b64u_decode(token[len(_PREFIX):])
    except (ValueError, binascii.Error):
        return None
    if len(raw) < _PAYLOAD_LEN + _SIG_LEN:
        return None

    payload = raw[:_PAYLOAD_LEN]
    sig = raw[_PAYLOAD_LEN:_PAYLOAD_LEN + _SIG_LEN]

    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    expected = hmac.new(key, payload, hashlib.sha256).digest()[:_SIG_LEN]
    if not hmac.compare_digest(sig, expected):
        return None

    if payload[0] != _VERSION:
        return None

    expires_at = int.from_bytes(payload[3:7], "big")
    if expires_at < now:
        return None

    telegram_id = int.from_bytes(payload[7:15], "big")
    try:
        authed = int(authed_user_id)
    except (TypeError, ValueError):
        return None
    if telegram_id != authed:
        return None

    return OfferResult(
        percent=payload[1],
        applies_to=payload[2],
        expires_at=expires_at,
        telegram_id=telegram_id,
        template_id_hash=payload[15:21].hex(),
    )
