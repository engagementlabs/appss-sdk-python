"""HTTP header construction."""

from __future__ import annotations

from appss_sdk._constants import PROTOCOL_VERSION, SDK_NAME, SDK_VERSION


def build_headers(api_key: str) -> dict[str, str]:
    """Build the four-header set used by every transport request."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Appss-Sdk": f"{SDK_NAME}/{SDK_VERSION}",
        "X-Appss-Protocol-Version": PROTOCOL_VERSION,
    }
