"""Tests for cascade_engine.py — inverted index + mixed relevance cascade."""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.memory.cascade_engine import CascadeEngine
from emotion_spirit.memory.unified_entry import UnifiedEntry


def _make_entry(id="e1", text="test", tags=None, entities=None, temperature=0.5, **kw):
    defaults = dict(
        id=id, text=text, tags=tags or [], entities=entities or {},
        source_user="user1", privacy="private", created_at=time.time(),
        temperature=temperature, emotional_weight=0.5, mass=0.5,
        tier="buffer", is_ghost=False, recall_count=0, last_recalled=0.0,
        peak_temperature=temperature,
    )
    defaults.update(kw)
    return UnifiedEntry(**defaults)


def test_index_add_and_find():
    """Adding an entry to the index makes it findable by tag."""
    engine = CascadeEngine()
    entry = _make_entry(tags=["conflict", "bob"])
    engine.index_entry(entry)
    related = engine.find_related(_make_entry(id="other", tags=["conflict"]))
    assert "e1" in related


def test_index_find_by_entity():
    """Entries sharing entities are found."""
    engine = CascadeEngine()
    entry = _make_entry(entities={"person": ["bob"]})
    engine.index_entry(entry)
    source = _make_entry(id="other", entities={"person": ["bob"]})
    related = engine.find_related(source)
    assert "e1" in related


def test_index_exclude_self():
    """find_related excludes the source entry itself."""
    engine = CascadeEngine()
    entry = _make_entry(tags=["test"])
    engine.index_entry(entry)
    related = engine.find_related(entry)
    assert "e1" not in related


def test_index_remove():
    """Removing an entry removes it from the index."""
    engine = CascadeEngine()
    entry = _make_entry(tags=["test"])
    engine.index_entry(entry)
    engine.remove_entry(entry)
    related = engine.find_related(_make_entry(id="other", tags=["test"]))
    assert "e1" not in related


def test_relevance_tag_overlap():
    """relevance() returns positive value for shared tags."""
    engine = CascadeEngine()
    a = _make_entry(id="a", tags=["conflict", "bob"])
    b = _make_entry(id="b", tags=["conflict", "work"])
    r = engine.relevance(a, b)
    assert r > 0


def test_relevance_no_overlap():
    """relevance() returns only vector similarity for completely different entries.

    With default vectors (0,0,0), vector_similarity = 1.0 → base relevance = 0.2.
    Different vectors reduce this contribution.
    """
    engine = CascadeEngine()
    a = _make_entry(id="a", tags=["conflict"], text="hello", entities={"person": ["bob"]})
    b = _make_entry(id="b", tags=["work"], text="goodbye", entities={"person": ["alice"]})
    r = engine.relevance(a, b)
    # Default vectors are identical (0,0,0) → vector_similarity=1.0 → 0.2*1.0=0.2
    assert r == pytest.approx(0.2, abs=0.01)


def test_relevance_entity_overlap():
    """relevance() accounts for shared entities."""
    engine = CascadeEngine()
    a = _make_entry(id="a", tags=[], entities={"person": ["bob"]})
    b = _make_entry(id="b", tags=[], entities={"person": ["bob"]})
    r = engine.relevance(a, b)
    assert r > 0


def test_propagate_transfers_heat():
    """propagate_cascade transfers heat from source to related entries."""
    engine = CascadeEngine()
    source = _make_entry(id="hot", tags=["conflict"], temperature=0.9)
    target = _make_entry(id="cold", tags=["conflict"], temperature=0.2)
    engine.index_entry(source)
    engine.index_entry(target)
    engine.propagate_cascade(source, sensitivity=0.5, entries_lookup={"hot": source, "cold": target})
    assert target.temperature > 0.2


def test_propagate_ignores_unrelated():
    """propagate_cascade does not heat unrelated entries."""
    engine = CascadeEngine()
    source = _make_entry(id="hot", tags=["conflict"], temperature=0.9)
    unrelated = _make_entry(id="cold", tags=["weather"], temperature=0.2)
    engine.index_entry(source)
    engine.index_entry(unrelated)
    engine.propagate_cascade(source, sensitivity=0.5, entries_lookup={"hot": source, "cold": unrelated})
    assert unrelated.temperature == 0.2  # unchanged


def test_propagate_respects_relevance_threshold():
    """propagate_cascade only affects entries with relevance > 0.2."""
    engine = CascadeEngine()
    # 1 shared tag out of many → low Jaccard tag overlap
    source = _make_entry(id="s", tags=["shared", "a", "b", "c", "d", "e", "f", "g"],
                         text="completely different content xyz", temperature=0.9)
    target = _make_entry(id="t", tags=["shared", "x", "y", "z", "w", "v", "u", "t2"],
                         text="another totally different thing", temperature=0.2)
    # Set opposite vectors so vector_similarity ≈ 0 → no vector boost
    source.vector = (0.0, 0.0, 0.0)
    target.vector = (1.0, 1.0, 1.0)
    engine.index_entry(source)
    engine.index_entry(target)
    engine.propagate_cascade(source, sensitivity=0.5, entries_lookup={"s": source, "t": target})
    # 1 shared tag out of 15 → Jaccard = 1/15 ≈ 0.067
    # relevance = 0.3*0.067 + 0 + 0 + 0.2*0.0 ≈ 0.02, below 0.2 threshold
    assert target.temperature == 0.2  # unchanged
