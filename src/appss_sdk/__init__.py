"""APPSS analytics SDK for Python (async, Telegram bots, servers)."""

from appss_sdk._adapters.queue import MemoryQueue
from appss_sdk._client import AppssClient, create_appss
from appss_sdk._config import AppssConfig, ResolvedConfig, RetryConfig
from appss_sdk._constants import SDK_NAME, SDK_VERSION
from appss_sdk._ports import IEventQueue, ILogger, ITransport
from appss_sdk._storage_key import storage_key
from appss_sdk._types import (
    AppssEvent,
    EventProperties,
    OnErrorCallback,
    TransportResponse,
    UserProperties,
)
from appss_sdk.errors import (
    ApiKeyRevokedError,
    AppssError,
    ErrorCode,
    ErrorSeverity,
    InvalidApiKeyError,
    MaxRetriesExceededError,
    NetworkError,
    NotIdentifiedError,
    NotInitializedError,
    ProtocolError,
    QueueOverflowError,
    RateLimitError,
)

__all__ = [
    "SDK_NAME",
    "SDK_VERSION",
    "ApiKeyRevokedError",
    "AppssClient",
    "AppssConfig",
    "AppssError",
    "AppssEvent",
    "ErrorCode",
    "ErrorSeverity",
    "EventProperties",
    "IEventQueue",
    "ILogger",
    "ITransport",
    "InvalidApiKeyError",
    "MaxRetriesExceededError",
    "MemoryQueue",
    "NetworkError",
    "NotIdentifiedError",
    "NotInitializedError",
    "OnErrorCallback",
    "ProtocolError",
    "QueueOverflowError",
    "RateLimitError",
    "ResolvedConfig",
    "RetryConfig",
    "TransportResponse",
    "UserProperties",
    "create_appss",
    "storage_key",
]
__version__ = "0.1.0"
