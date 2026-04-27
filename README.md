# appss-sdk

Async Python SDK for APPSS analytics — events, user properties, and super
properties — designed for Telegram bots and server-side workloads.

## Install

```bash
pip install appss-sdk
# or
uv add appss-sdk
```

Optional extras for Telegram framework integration:

```bash
pip install appss-sdk[aiogram]    # aiogram v3
pip install appss-sdk[ptb]        # python-telegram-bot v20+
```

## Quickstart

```python
import asyncio
from appss_sdk import create_appss


async def main() -> None:
    appss = create_appss({"api_key": "YOUR_API_KEY", "debug": True})

    appss.track(
        distinct_id="user_42",
        event="message_received",
        properties={"chat_type": "private", "text_length": 12},
    )

    appss.set_user_properties("user_42", {
        "platform": "telegram",
        "username": "alice",
    })

    await appss.flush()
    await appss.destroy()


asyncio.run(main())
```

`AppssClient` is async-only — it must be instantiated inside a running event
loop (`asyncio.run(...)`, aiogram polling, FastAPI lifespan, etc.). The
constructor starts a background flush loop, so creating it without an active
loop will fail.

## aiogram v3 integration

```python
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from appss_sdk import create_appss
from appss_sdk.telegram import from_aiogram_message

dp = Dispatcher()
appss = create_appss({"api_key": "YOUR_API_KEY"})


@dp.message()
async def on_message(message: Message) -> None:
    ctx = from_aiogram_message(message)
    if ctx is None:
        return
    appss.set_user_properties(ctx.distinct_id, ctx.properties)
    appss.track(ctx.distinct_id, "message_received", {"length": len(message.text or "")})
    await message.answer("✓")


# Call await appss.destroy() when shutting the bot down.
```

## python-telegram-bot v20+ integration

```python
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from appss_sdk import create_appss
from appss_sdk.telegram import from_ptb_update

app = Application.builder().token("BOT_TOKEN").build()
appss = create_appss({"api_key": "YOUR_API_KEY"})


async def on_message(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    ctx = from_ptb_update(update)
    if ctx is not None:
        appss.set_user_properties(ctx.distinct_id, ctx.properties)
        appss.track(ctx.distinct_id, "message_received")


app.add_handler(MessageHandler(filters.TEXT, on_message))
app.run_polling()
```

## Configuration

| Field | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str` | — | **Required.** APPSS API key. |
| `endpoint` | `str` | `https://appss-event-tracker-back-p.engagelabs.org` | API endpoint. |
| `flush_interval_ms` | `int` | `10_000` | Automatic flush interval in milliseconds. |
| `batch_size` | `int` | `50` | Auto-flush threshold by event count. |
| `max_queue_size` | `int` | `10_000` | Maximum number of events buffered in memory. |
| `request_timeout_ms` | `int` | `30_000` | HTTP request timeout in milliseconds. |
| `retry` | `RetryConfig` | exp. backoff with jitter | Retry policy. |
| `debug` | `bool` | `False` | Log to stdout/stderr. |
| `on_error` | `Callable[[AppssError], None \| Awaitable[None]]` | `None` | SDK error callback. |
| `logger` | `ILogger` | `None` | Custom logger implementation. |
| `queue` | `IEventQueue` | `None` | Custom queue (e.g. persistent). |

`RetryConfig` accepts `max_retries`, `base_backoff_ms`, and `max_backoff_ms`.
Every field is optional; defaults are filled in field by field.

## Public API

```python
from appss_sdk import (
    AppssClient,
    create_appss,
    AppssConfig,
    ResolvedConfig,
    RetryConfig,
    AppssError,
    ErrorCode,
    # ... concrete errors: ApiKeyRevokedError, NetworkError, etc.
    MemoryQueue,
    IEventQueue,
    ILogger,
    ITransport,
)
from appss_sdk.telegram import (
    from_aiogram_message,
    from_aiogram_callback,
    from_ptb_update,
    from_bot_api_update,
    ExtractedContext,
)
```

Telegram helpers are intentionally **not** re-exported at the root, so
`import appss_sdk` does not pull aiogram/PTB into the import graph.

### Client methods

- `appss.track(distinct_id, event, properties=None)` — enqueue an event.
- `appss.set_user_property(distinct_id, key, value)` — update a single user property.
- `appss.set_user_properties(distinct_id, properties)` — update multiple user properties in a single POST.
- `appss.set_super_properties(properties)` — register properties that are automatically attached to every subsequent `track` event.
- `appss.reset_super_properties()` — clear all super properties.
- `await appss.flush()` — force-send the queue.
- `await appss.destroy()` — flush, stop background tasks, and close the HTTP client.

## Lifecycle

`AppssClient` automatically registers `SIGTERM` and `SIGINT` handlers that
invoke `flush()` before the process exits (Linux/macOS). On Windows
`add_signal_handler` is unavailable — registration is a no-op, and you must
call `await appss.destroy()` explicitly before exit.

## Custom queue

```python
from appss_sdk import create_appss, MemoryQueue


def on_overflow(dropped: int) -> None:
    print(f"appss: dropped {dropped} events")


appss = create_appss({
    "api_key": "...",
    "queue": MemoryQueue(max_size=5000, on_overflow=on_overflow),
})
```

You can also implement your own `IEventQueue` (e.g. backed by Redis); the
contract is `enqueue / drain / peek / size / is_empty / clear`.

## Wire protocol

POST `/api/v1/events` with body
`{"batch": [{"event", "distinct_id", "$insert_id", "timestamp", "properties"}]}`,
where `timestamp` is ISO 8601 in UTC and `$insert_id` is a UUID v4.

POST `/api/v1/user-properties` with body `{"distinct_id", "properties"}`.

Headers added automatically:

- `Authorization: Bearer <api_key>`
- `Content-Type: application/json`
- `X-Appss-Sdk: @appss-sdk/<version>`
- `X-Appss-Protocol-Version: 1`

## Retry and error semantics

| Status | Action |
|---|---|
| 2xx | Success — the batch is drained from the queue. |
| 400 | Drop + `ProtocolError` (batch is dropped, not retried). |
| 401 | Stop forever — `ApiKeyRevokedError`, subsequent sends are blocked. |
| 413 | Recursive binary split + retry (halves until it fits). |
| 429 | Wait `Retry-After` (or fall back to exponential backoff if the header is invalid). |
| 5xx | Exponential backoff with jitter, up to `retry.max_retries` attempts. |
| Network exception | Retry up to `retry.max_retries`, then `MaxRetriesExceededError`. |

All errors are delivered to the `on_error(error)` callback if one is configured.

## License

Apache-2.0. See [LICENSE](./LICENSE).
