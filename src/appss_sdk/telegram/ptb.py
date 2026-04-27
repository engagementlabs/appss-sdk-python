"""Helper for python-telegram-bot v20+ Update objects."""

from __future__ import annotations

from typing import Any

from appss_sdk.telegram._extract import ExtractedContext, _get, extract


def from_ptb_update(update: Any) -> ExtractedContext | None:
    """Extract distinct_id and properties from a python-telegram-bot Update.

    Walks ``update.message`` / ``callback_query`` / ``inline_query`` /
    ``edited_message`` / ``channel_post`` and returns the first match.
    """
    for attr in (
        "message",
        "callback_query",
        "inline_query",
        "edited_message",
        "channel_post",
    ):
        sub = _get(update, attr)
        if sub is not None:
            result = extract(sub)
            if result is not None:
                return result
    return extract(update)
