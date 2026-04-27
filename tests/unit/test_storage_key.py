"""Tests for the storage_key namespacing helper."""

from appss_sdk import storage_key


def test_storage_key_prefixes_with_underscore_appss():
    assert storage_key("foo") == "__appss_foo"


def test_storage_key_handles_empty_string():
    assert storage_key("") == "__appss_"


def test_storage_key_does_not_double_prefix():
    # No idempotency check — re-prefixing is the caller's responsibility.
    assert storage_key("__appss_x") == "__appss___appss_x"
