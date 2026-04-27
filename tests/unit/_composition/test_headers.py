"""Unit tests for build_headers."""

from __future__ import annotations

from appss_sdk._composition.headers import build_headers
from appss_sdk._constants import PROTOCOL_VERSION, SDK_NAME, SDK_VERSION


def test_build_headers_contains_four_keys() -> None:
    headers = build_headers("secret-key")
    assert set(headers.keys()) == {
        "Authorization",
        "Content-Type",
        "X-Appss-Sdk",
        "X-Appss-Protocol-Version",
    }


def test_authorization_header_uses_bearer_scheme() -> None:
    assert build_headers("abc123")["Authorization"] == "Bearer abc123"


def test_content_type_is_json() -> None:
    assert build_headers("k")["Content-Type"] == "application/json"


def test_sdk_header_uses_constants() -> None:
    assert build_headers("k")["X-Appss-Sdk"] == f"{SDK_NAME}/{SDK_VERSION}"


def test_protocol_version_header() -> None:
    assert build_headers("k")["X-Appss-Protocol-Version"] == PROTOCOL_VERSION


def test_api_key_with_special_chars_passed_through() -> None:
    api_key = "abc def/+="
    assert build_headers(api_key)["Authorization"] == f"Bearer {api_key}"
