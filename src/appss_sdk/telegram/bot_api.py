"""Universal helper for raw Telegram Bot API update dicts.

Use this when no framework wrapper is involved — the raw JSON dict from a
webhook or ``getUpdates`` call.
"""

from __future__ import annotations

from typing import Any

from appss_sdk.telegram._extract import ExtractedContext, extract


def from_bot_api_update(update: dict[str, Any]) -> ExtractedContext | None:
    """Extract distinct_id and properties from a raw Bot API Update dict.

    Walks the embedded message-like sub-objects and returns the first match.
    """
    for key in ("message", "callback_query", "inline_query", "edited_message", "channel_post"):
        sub = update.get(key)
        if isinstance(sub, dict):
            result = extract(sub)
            if result is not None:
                return result
    return extract(update)
