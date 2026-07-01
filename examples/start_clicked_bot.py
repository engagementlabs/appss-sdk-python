"""
Run (token from @BotFather)::

    python examples/mock_tracker.py                  # terminal 1
    BOT_TOKEN=123:abc \
    APPSS_ENDPOINT=http://localhost:8799 \
    APPSS_API_KEY=local-test-key \
    python examples/start_clicked_bot.py             # terminal 2
"""

from __future__ import annotations

import asyncio
import os
import sys


async def main() -> None:
    from aiogram import Bot, Dispatcher
    from aiogram.filters import CommandStart
    from aiogram.types import Message

    from appss_sdk import create_appss
    from appss_sdk.telegram import from_aiogram_message

    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        print("Set BOT_TOKEN (from @BotFather)", file=sys.stderr)
        sys.exit(1)

    appss = create_appss(
        {
            "api_key": os.environ.get("APPSS_API_KEY", "local-test-key"),
            "endpoint": os.environ.get("APPSS_ENDPOINT", "http://localhost:8799"),
            "batch_size": 1,
            "debug": True,
        }
    )
    bot = Bot(token=bot_token)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def on_start(message: Message) -> None:
        ctx = from_aiogram_message(message)
        if ctx is not None:
            appss.set_user_properties(ctx.distinct_id, ctx.properties)
            appss.track(
                ctx.distinct_id,
                "start clicked",
                {"is_deep_link": "$start_param" in ctx.properties},
            )
            print(f"tracked 'start clicked' for {ctx.distinct_id}")
        await message.answer("Hi! Tracked your start 👋")

    print("bot polling — open it in Telegram and press Start")
    try:
        await dp.start_polling(bot)
    finally:
        await appss.destroy()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
