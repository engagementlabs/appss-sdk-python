"""SDK-wide constants."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Final


def _detect_version() -> str:
    try:
        return _pkg_version("appss-sdk")
    except PackageNotFoundError:
        return "0.0.0+unknown"


SDK_NAME: Final[str] = "@appss-sdk"
SDK_VERSION: Final[str] = _detect_version()
PROTOCOL_VERSION: Final[str] = "1"

DEFAULT_ENDPOINT: Final[str] = "https://appss-event-tracker-back-p.engagelabs.org"

DEFAULT_BATCH_SIZE: Final[int] = 50
DEFAULT_FLUSH_INTERVAL_MS: Final[int] = 10_000

MAX_QUEUE_SIZE: Final[int] = 10_000
MAX_QUEUE_SIZE_BYTES: Final[int] = 4_194_304  # 4 MiB; reserved for future byte-based queue limits

DEFAULT_MAX_RETRIES: Final[int] = 5
DEFAULT_BASE_BACKOFF_MS: Final[int] = 1_000
DEFAULT_MAX_BACKOFF_MS: Final[int] = 16_000
DEFAULT_JITTER_FACTOR: Final[float] = 0.2

EVENTS_PATH: Final[str] = "/api/v1/events"
USER_PROPERTIES_PATH: Final[str] = "/api/v1/user-properties"
PUSH_EVENTS_PATH: Final[str] = "/api/v1/push-events"

PUSH_SEND_MAX_RETRIES: Final[int] = 3
PUSH_SEND_BACKOFF_MS: Final[int] = 1_000
PUSH_SEND_MAX_BACKOFF_MS: Final[int] = 8_000
BOT_TOKEN_ENV: Final[str] = "BOT_TOKEN"

DEFAULT_REQUEST_TIMEOUT_MS: Final[int] = 30_000
SHUTDOWN_TIMEOUT_MS: Final[int] = 5_000

STORAGE_KEY_PREFIX: Final[str] = "__appss_"
