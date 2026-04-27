"""Super-property enrichment.

Super-properties win on key collisions with per-event properties.
"""

from __future__ import annotations

from typing import Any


class EventEnricher:
    """Holds a bag of super-properties that decorate every tracked event."""

    def __init__(self) -> None:
        self._properties: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._properties[key] = value

    def set_all(self, properties: dict[str, Any]) -> None:
        self._properties.update(properties)

    def remove(self, key: str) -> None:
        self._properties.pop(key, None)

    def reset(self) -> None:
        self._properties.clear()

    def enrich(self, event_properties: dict[str, Any] | None) -> dict[str, Any] | None:
        """Merge per-event properties with super-properties (super wins on collision)."""
        if not self._properties and event_properties is None:
            return None
        return {**(event_properties or {}), **self._properties}
