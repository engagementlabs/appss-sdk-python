"""Storage-key helper."""

from appss_sdk._constants import STORAGE_KEY_PREFIX


def storage_key(name: str) -> str:
    """Namespace a storage key with the SDK prefix."""
    return f"{STORAGE_KEY_PREFIX}{name}"
