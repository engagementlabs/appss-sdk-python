"""Unit tests for EventEnricher."""

from __future__ import annotations

from appss_sdk._composition.enricher import EventEnricher


def test_enrich_passthrough_when_no_super_properties() -> None:
    enricher = EventEnricher()
    assert enricher.enrich({"a": 1}) == {"a": 1}


def test_enrich_returns_none_when_both_empty() -> None:
    enricher = EventEnricher()
    assert enricher.enrich(None) is None


def test_set_single_super_property() -> None:
    enricher = EventEnricher()
    enricher.set("k", "v")
    assert enricher.enrich({}) == {"k": "v"}
    assert enricher.enrich(None) == {"k": "v"}


def test_set_all_merges_super_properties() -> None:
    enricher = EventEnricher()
    enricher.set_all({"a": 1, "b": 2})
    enricher.set_all({"b": 3, "c": 4})
    assert enricher.enrich(None) == {"a": 1, "b": 3, "c": 4}


def test_super_properties_win_on_collision() -> None:
    enricher = EventEnricher()
    enricher.set_all({"a": 1, "b": 2})
    assert enricher.enrich({"a": 99, "z": 0}) == {"a": 1, "b": 2, "z": 0}


def test_remove_drops_property() -> None:
    enricher = EventEnricher()
    enricher.set("a", "x")
    enricher.set("b", "y")
    enricher.remove("a")
    assert enricher.enrich(None) == {"b": "y"}


def test_remove_missing_key_is_noop() -> None:
    enricher = EventEnricher()
    enricher.remove("nonexistent")
    assert enricher.enrich(None) is None


def test_reset_clears_super_properties() -> None:
    enricher = EventEnricher()
    enricher.set("a", "x")
    enricher.reset()
    assert enricher.enrich(None) is None
    assert enricher.enrich({"a": 1}) == {"a": 1}
