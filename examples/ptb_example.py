"""Minimal python-telegram-bot v20+ echo bot with APPSS analytics integration.

Run with::

    pip install appss-sdk[ptb]
    BOT_TOKEN=... APPSS_API_KEY=... python examples/ptb_example.py
"""

from __future__ import annotations

import os
import sys
from typing import Any


def main() -> None:
    # Imports are deferred so this module is importable without
    # python-telegram-bot installed and without env vars set.
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )

    from appss_sdk import create_appss
    from appss_sdk.telegram import from_ptb_update

    bot_token = os.environ.get("BOT_TOKEN")
    api_key = os.environ.get("APPSS_API_KEY")
    if not bot_token or not api_key:
        print("Set BOT_TOKEN and APPSS_API_KEY env vars", file=sys.stderr)
        sys.exit(1)

    async def post_init(application: Any) -> None:
        application.bot_data["appss"] = create_appss({"api_key": api_key, "debug": True})

    async def post_shutdown(application: Any) -> None:
        appss = application.bot_data.get("appss")
        if appss is not None:
            await appss.destroy()

    async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = from_ptb_update(update)
        appss = context.application.bot_data.get("appss")
        if ctx is not None and appss is not None:
            appss.set_user_properties(ctx.distinct_id, ctx.properties)
            appss.track(ctx.distinct_id, "bot_started")
        if update.message is not None:
            await update.message.reply_text("Hi! This is an echo bot with APPSS analytics.")

    async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = from_ptb_update(update)
        appss = context.application.bot_data.get("appss")
        if ctx is not None and appss is not None:
            appss.set_user_properties(ctx.distinct_id, ctx.properties)
            appss.track(
                ctx.distinct_id,
                "message_received",
                {"text_length": len((update.message and update.message.text) or "")},
            )
        if update.message is not None:
            await update.message.reply_text(update.message.text or "(no text)")

    app = (
        Application.builder()
        .token(bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.run_polling()


if __name__ == "__main__":
    main()
