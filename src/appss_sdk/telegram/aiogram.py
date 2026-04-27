"""Helpers for aiogram v3 Message and CallbackQuery objects."""

from __future__ import annotations

from typing import Any

from appss_sdk.telegram._extract import ExtractedContext, extract


def from_aiogram_message(message: Any) -> ExtractedContext | None:
    """Extract distinct_id and properties from an aiogram v3 Message.

    Returns ``None`` if the message has no ``from_user`` with a numeric id.
    """
    return extract(message)


def from_aiogram_callback(callback_query: Any) -> ExtractedContext | None:
    """Extract distinct_id and properties from an aiogram v3 CallbackQuery.

    The CallbackQuery itself has ``from_user``; ``chat_type`` and ``$start_param``
    come from the underlying message if present.
    """
    return extract(callback_query)
