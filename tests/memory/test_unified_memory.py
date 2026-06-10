"""Tests for unified_memory.py — the unified memory system."""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.memory.unified_memory import UnifiedMemory
from emotion_spirit.memory.unified_entry import UnifiedEntry


def test_add_creates_entry():
    """add() creates a UnifiedEntry in the buffer tier."""
    mem = UnifiedMemory()
    entry = mem.add(
        text="今天很开心", tags=["positive"], entities={},
        source_user="user1", arousal=0.7, raw_weight=0.6,
    )
    assert entry is not None
    assert entry.tier == "buffer"
    assert entry.temperature > 0
    assert len(mem.get_layer("buffer")) == 1


def test_add_temperature_formula():
    """Initial temperature = 0.5*arousal + 0.3*weight + 0.2*novelty."""
    mem = UnifiedMemory()
    entry = mem.add(
        text="test", tags=[], entities={}, source_user="user1",
        arousal=0.8, raw_weight=0.5,
    )
    # novelty is 0 for first entry (no recent memories to compare)
    expected = 0.5 * 0.8 + 0.3 * 0.5 + 0.2 * 0.0
    assert abs(entry.temperature - expected) < 0.05


def test_add_updates_indexes():
    """add() updates tier, tag, and entity indexes."""
    mem = UnifiedMemory()
    mem.add(text="test", tags=["conflict"], entities={"person": ["bob"]}, source_user="user1", arousal=0.5, raw_weight=0.5)
    assert "conflict" in mem._tag_index
    assert "person:bob" in mem._entity_index


def test_get_layer_returns_correct_tier():
    """get_layer() returns entries in the specified tier."""
    mem = UnifiedMemory()
    mem.add(text="a", tags=[], entities={}, source_user="u1", arousal=0.5, raw_weight=0.5)
    assert len(mem.get_layer("buffer")) == 1
    assert len(mem.get_layer("warm")) == 0


def test_mean_temperature():
    """mean_temperature() returns average temperature across all entries."""
    mem = UnifiedMemory()
    mem.add(text="a", tags=[], entities={}, source_user="u1", arousal=0.8, raw_weight=0.5)
    mem.add(text="b", tags=[], entities={}, source_user="u1", arousal=0.2, raw_weight=0.5)
    mean = mem.mean_temperature()
    assert 0.2 < mean < 0.8


def test_mean_temperature_empty():
    """mean_temperature() returns 0 for empty pool."""
    mem = UnifiedMemory()
    assert mem.mean_temperature() == 0.0


def test_tick_applies_decay():
    """tick() applies thermal and memory decay to all entries."""
    mem = UnifiedMemory()
    entry = mem.add(text="test", tags=[], entities={}, source_user="u1", arousal=0.9, raw_weight=0.9)
    initial_temp = entry.temperature
    # Simulate time passing by manipulating created_at and _last_tick
    entry.created_at = time.time() - 3600  # 1 hour ago
    mem._last_tick = time.time() - 3600  # Also move last_tick back
    mem.tick()
    assert entry.temperature < initial_temp


def test_tick_transitions_buffer_to_warm():
    """tick() promotes buffer entries to warm when conditions met."""
    mem = UnifiedMemory()
    entry = mem.add(text="test", tags=[], entities={}, source_user="u1", arousal=0.3, raw_weight=0.3)
    # Force conditions: temperature < 0.5, weight > noise
    entry.temperature = 0.3
    entry.emotional_weight = 0.5
    entry.created_at = time.time() - 3600
    mem._check_transitions()
    assert entry.tier == "warm"
    assert len(mem.get_layer("buffer")) == 0
    assert len(mem.get_layer("warm")) == 1


def test_ghost_formation():
    """tick() forms ghost when temperature > 0.9, weight > 0.8, sustained."""
    mem = UnifiedMemory()
    entry = mem.add(text="betrayal!", tags=["betrayal"], entities={}, source_user="u1", arousal=0.95, raw_weight=0.9)
    entry.temperature = 0.95
    entry.emotional_weight = 0.85
    entry._ticks_above_ghost_threshold = 15  # Above threshold
    mem._check_ghost_formation()
    assert entry.is_ghost is True
    assert entry.tier == "ghost"


def test_inject_signal():
    """inject_signal() finds entry by ID and calls on_inject."""
    mem = UnifiedMemory()
    entry = mem.add(text="test", tags=[], entities={}, source_user="u1", arousal=0.5, raw_weight=0.5)
    initial_temp = entry.temperature
    mem.inject_signal(entry.id, "contradiction", 1.0)
    assert entry.temperature > initial_temp


def test_recall_entry():
    """recall_entry() calls on_recall and opens reconsolidation window."""
    mem = UnifiedMemory()
    entry = mem.add(text="test", tags=[], entities={}, source_user="u1", arousal=0.5, raw_weight=0.5)
    personality = {"neuroticism": 0.5, "openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5}
    mem.recall_entry(entry.id, personality)
    assert entry.recall_count == 1
    assert entry._is_labile is True


def test_cascade_active():
    """cascade_active returns True when cascade is in progress."""
    mem = UnifiedMemory()
    assert mem.cascade_active() is False
    mem._cascade_active = True
    assert mem.cascade_active() is True


def test_count_hot():
    """count_hot() returns entries above temperature threshold."""
    mem = UnifiedMemory()
    mem.add(text="hot", tags=[], entities={}, source_user="u1", arousal=0.9, raw_weight=0.9)
    mem.add(text="cold", tags=[], entities={}, source_user="u1", arousal=0.1, raw_weight=0.1)
    # Manipulate temperatures directly
    entries = list(mem._entries.values())
    entries[0].temperature = 0.85
    entries[1].temperature = 0.15
    assert mem.count_hot(0.7) == 1


def test_serialization_roundtrip():
    """to_dict/from_dict preserves all entries and state."""
    mem = UnifiedMemory()
    mem.add(text="test", tags=["tag1"], entities={"person": ["bob"]}, source_user="u1", arousal=0.5, raw_weight=0.5)
    data = mem.to_dict()
    mem2 = UnifiedMemory.from_dict(data)
    assert len(mem2.get_layer("buffer")) == 1
    entries = mem2.get_layer("buffer")
    assert entries[0].text == "test"
    assert entries[0].tags == ["tag1"]
