"""Minimal aiogram v3 echo bot with APPSS analytics integration.

Run with::

    pip install appss-sdk[aiogram]
    BOT_TOKEN=... APPSS_API_KEY=... python examples/aiogram_example.py
"""

from __future__ import annotations

import asyncio
import os
import sys


async def main() -> None:
    # Imports are deferred so this module is importable without aiogram installed
    # and without env vars set (CI smoke check just verifies that import works).
    from aiogram import Bot, Dispatcher
    from aiogram.filters import CommandStart
    from aiogram.types import Message

    from appss_sdk import create_appss
    from appss_sdk.telegram import from_aiogram_message

    bot_token = os.environ.get("BOT_TOKEN")
    api_key = os.environ.get("APPSS_API_KEY")
    if not bot_token or not api_key:
        print("Set BOT_TOKEN and APPSS_API_KEY env vars", file=sys.stderr)
        sys.exit(1)

    appss = create_appss({"api_key": api_key, "debug": True})
    bot = Bot(token=bot_token)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def on_start(message: Message) -> None:
        ctx = from_aiogram_message(message)
        if ctx is not None:
            appss.set_user_properties(ctx.distinct_id, ctx.properties)
            appss.track(
                ctx.distinct_id,
                "bot_started",
                {"is_deep_link": "$start_param" in ctx.properties},
            )
        await message.answer("Hi! This is an echo bot with APPSS analytics.")

    @dp.message()
    async def on_message(message: Message) -> None:
        ctx = from_aiogram_message(message)
        if ctx is not None:
            appss.set_user_properties(ctx.distinct_id, ctx.properties)
            appss.track(
                ctx.distinct_id,
                "message_received",
                {"text_length": len(message.text or "")},
            )
        await message.answer(message.text or "(no text)")

    try:
        await dp.start_polling(bot)
    finally:
        await appss.destroy()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
