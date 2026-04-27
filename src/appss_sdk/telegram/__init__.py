"""Telegram framework helpers.

Re-exports framework-agnostic context extractors:
- from_aiogram_message, from_aiogram_callback (aiogram v3)
- from_ptb_update (python-telegram-bot v20+)
- from_bot_api_update (raw Bot API dict, framework-independent)
"""

from appss_sdk.telegram._extract import ExtractedContext, TelegramUserProperties
from appss_sdk.telegram.aiogram import from_aiogram_callback, from_aiogram_message
from appss_sdk.telegram.bot_api import from_bot_api_update
from appss_sdk.telegram.ptb import from_ptb_update

__all__ = [
    "ExtractedContext",
    "TelegramUserProperties",
    "from_aiogram_callback",
    "from_aiogram_message",
    "from_bot_api_update",
    "from_ptb_update",
]
