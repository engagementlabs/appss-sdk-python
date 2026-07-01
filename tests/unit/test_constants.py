"""Smoke tests for SDK constants."""

from appss_sdk._constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_ENDPOINT,
    DEFAULT_FLUSH_INTERVAL_MS,
    DEFAULT_MAX_RETRIES,
    EVENTS_PATH,
    MAX_QUEUE_SIZE,
    PROTOCOL_VERSION,
    SDK_NAME,
    SDK_VERSION,
    STORAGE_KEY_PREFIX,
    USER_PROPERTIES_PATH,
)


def test_sdk_version_is_non_empty_string():
    assert isinstance(SDK_VERSION, str)
    assert SDK_VERSION
    assert SDK_VERSION[0].isdigit()


def test_sdk_name_is_appss_sdk():
    assert SDK_NAME == "@appss-sdk"


def test_protocol_version_is_string_one():
    assert PROTOCOL_VERSION == "1"


def test_events_path_is_versioned_route():
    assert EVENTS_PATH == "/api/v1/events"


def test_user_properties_path_is_versioned_route():
    assert USER_PROPERTIES_PATH == "/api/v1/user-properties"


def test_default_endpoint_uses_https():
    assert DEFAULT_ENDPOINT.startswith("https://")


def test_storage_key_prefix_is_double_underscore_appss():
    assert STORAGE_KEY_PREFIX == "__appss_"


def test_default_numeric_constants():
    assert DEFAULT_BATCH_SIZE == 50
    assert DEFAULT_FLUSH_INTERVAL_MS == 10_000
    assert MAX_QUEUE_SIZE == 10_000
    assert DEFAULT_MAX_RETRIES == 5
