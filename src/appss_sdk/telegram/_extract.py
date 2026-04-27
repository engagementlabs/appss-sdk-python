"""Duck-typed Telegram context extraction.

Works against any object or dict that exposes Telegram-shaped fields
(``from`` / ``from_user``, ``chat``, ``text``, ``message``) — no aiogram or
python-telegram-bot import required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TelegramUserProperties:
    """Optional user properties extracted from a Telegram update."""

    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    is_premium: bool | None = None
    chat_type: str | None = None
    start_param: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.username is not None:
            out["username"] = self.username
        if self.first_name is not None:
            out["first_name"] = self.first_name
        if self.last_name is not None:
            out["last_name"] = self.last_name
        if self.language_code is not None:
            out["language_code"] = self.language_code
        if self.is_premium is not None:
            out["is_premium"] = self.is_premium
        if self.chat_type is not None:
            out["chat_type"] = self.chat_type
        if self.start_param is not None:
            out["$start_param"] = self.start_param
        return out


@dataclass(frozen=True, slots=True)
class ExtractedContext:
    """Result of ``extract``: distinct_id plus a properties dict (already in wire format)."""

    distinct_id: str
    properties: dict[str, Any]


def _get(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _extract_from(ctx: Any) -> Any | None:
    from_obj = _get(ctx, "from_user")
    if from_obj is None:
        from_obj = _get(ctx, "from")
    if from_obj is None:
        message = _get(ctx, "message")
        if message is not None:
            from_obj = _get(message, "from_user") or _get(message, "from")
    if from_obj is None:
        return None
    candidate_id = _get(from_obj, "id")
    if not isinstance(candidate_id, int) or isinstance(candidate_id, bool):
        return None
    return from_obj


def _extract_chat_type(ctx: Any) -> str | None:
    chat = _get(ctx, "chat")
    if chat is not None:
        chat_type = _get(chat, "type")
        if isinstance(chat_type, str):
            return chat_type
    message = _get(ctx, "message")
    if message is not None:
        message_chat = _get(message, "chat")
        if message_chat is not None:
            chat_type = _get(message_chat, "type")
            if isinstance(chat_type, str):
                return chat_type
    return None


def _extract_start_param(ctx: Any) -> str | None:
    text = _get(ctx, "text")
    if text is None:
        message = _get(ctx, "message")
        if message is not None:
            text = _get(message, "text")
    if not isinstance(text, str):
        return None
    prefix = "/start "
    if text.startswith(prefix):
        param = text[len(prefix) :].strip()
        return param or None
    return None


def _coerce_optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _coerce_optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _build_properties(from_obj: Any, ctx: Any) -> TelegramUserProperties:
    return TelegramUserProperties(
        username=_coerce_optional_str(_get(from_obj, "username")),
        first_name=_coerce_optional_str(_get(from_obj, "first_name")),
        last_name=_coerce_optional_str(_get(from_obj, "last_name")),
        language_code=_coerce_optional_str(_get(from_obj, "language_code")),
        is_premium=_coerce_optional_bool(_get(from_obj, "is_premium")),
        chat_type=_extract_chat_type(ctx),
        start_param=_extract_start_param(ctx),
    )


def extract(ctx: Any) -> ExtractedContext | None:
    """Extract a Telegram user identity and user properties from any context-like object.

    Returns ``None`` when no usable ``from``/``from_user`` with a numeric id is
    present.
    """
    from_obj = _extract_from(ctx)
    if from_obj is None:
        return None
    user_id = _get(from_obj, "id")
    if not isinstance(user_id, int) or isinstance(user_id, bool):
        return None
    properties = _build_properties(from_obj, ctx).to_dict()
    return ExtractedContext(distinct_id=str(user_id), properties=properties)
