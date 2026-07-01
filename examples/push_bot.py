"""
Run (token from @BotFather)::

    python examples/mock_tracker.py                  # terminal 1: captures telemetry
    BOT_TOKEN=123:abc \
    APPSS_ENDPOINT=http://localhost:8799 \
    APPSS_API_KEY=local-test-key \
    python examples/push_bot.py                      # terminal 2: the bot

Then in Telegram: open the bot, press Start, send /push. You should receive a
push message with button; terminal 1 should show a
``Push Sent`` event, and tapping the button should show a ``Push Clicked`` event.
"""

from __future__ import annotations

import asyncio
import os
import sys
from itertools import count


async def main() -> None:
    from aiogram import Bot, Dispatcher, F
    from aiogram.filters import Command, CommandStart
    from aiogram.types import CallbackQuery, Message

    from appss_sdk import create_appss

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

    push_seq = count(1)

    @dp.message(CommandStart())
    async def on_start(message: Message) -> None:
        await message.answer(
            "Push utils smoke test 👋\n"
            "Send /push and I'll deliver a Push Hub-style push to you via "
            "`send_push`, then track the button tap via `track_push_clicked`."
        )

    @dp.message(Command("push"))
    async def on_push(message: Message) -> None:
        user = message.from_user
        if user is None:
            return
        distinct_id = str(user.id)
        push_id = f"demo-push-{next(push_seq)}"
        action_id = "cta"

        payload = {
            "push_id": push_id,
            "template_id": "demo-template",
            "step_id": "demo-step-1",
            "recipient": {"telegram_id": user.id, "distinct_id": distinct_id},
            "message": {
                "text": "🎁 <b>Special offer just for you!</b>\nTap below to open it.",
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "Open offer", "callback_data": f"pc:{push_id}:{action_id}"}]
                    ]
                },
            },
        }

        outcome = await appss.send_push(payload)
        print(
            f"send_push -> ok={outcome.ok} reason={outcome.reason} "
            f"msg_id={outcome.tg_message_id}"
        )
        if outcome.ok:
            await message.answer(f"✅ Push delivered (tg_message_id={outcome.tg_message_id})")
        else:
            await message.answer(f"❌ Push failed: {outcome.reason}")

    @dp.callback_query(F.data.startswith("pc:"))
    async def on_push_click(cb: CallbackQuery) -> None:
        parts = (cb.data or "").split(":", maxsplit=2)
        push_id = parts[1] if len(parts) > 1 else ""
        action_id = parts[2] if len(parts) > 2 else ""
        appss.track_push_clicked(str(cb.from_user.id), push_id=push_id, action_id=action_id)
        print(f"track_push_clicked -> push_id={push_id} action_id={action_id}")
        await cb.answer("Tracked your click 🎯", show_alert=False)

    print("bot polling — open it in Telegram, press Start, then send /push")
    try:
        await dp.start_polling(bot)
    finally:
        await appss.destroy()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
