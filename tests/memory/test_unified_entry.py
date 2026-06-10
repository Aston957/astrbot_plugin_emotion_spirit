"""Tests for unified_entry.py -- self-contained memory entity."""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.memory.unified_entry import UnifiedEntry


def _make_entry(**overrides) -> UnifiedEntry:
    defaults = dict(
        id="test_1", text="test memory", tags=["test"],
        entities={}, source_user="user1", privacy="private",
        created_at=time.time(), temperature=0.5, emotional_weight=0.5,
        mass=0.5, tier="buffer", is_ghost=False,
        recall_count=0, last_recalled=0.0, peak_temperature=0.5,
    )
    defaults.update(overrides)
    return UnifiedEntry(**defaults)


def test_entry_creation():
    """UnifiedEntry can be created with all fields."""
    entry = _make_entry()
    assert entry.id == "test_1"
    assert entry.text == "test memory"
    assert entry.temperature == 0.5
    assert entry.tier == "buffer"


def test_on_recall_increases_temperature():
    """on_recall raises temperature by 0.3."""
    entry = _make_entry(temperature=0.3)
    personality = {"neuroticism": 0.5, "openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5}
    entry.on_recall(personality)
    assert entry.temperature == 0.6


def test_on_recall_caps_temperature():
    """on_recall caps temperature at 1.0."""
    entry = _make_entry(temperature=0.9)
    personality = {"neuroticism": 0.5, "openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5}
    entry.on_recall(personality)
    assert entry.temperature == 1.0


def test_on_recall_increases_weight():
    """on_recall raises emotional_weight by 0.1."""
    entry = _make_entry(emotional_weight=0.5)
    personality = {"neuroticism": 0.5, "openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5}
    entry.on_recall(personality)
    assert abs(entry.emotional_weight - 0.6) < 0.01


def test_on_recall_increases_recall_count():
    """on_recall increments recall_count."""
    entry = _make_entry(recall_count=0)
    personality = {"neuroticism": 0.5, "openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5}
    entry.on_recall(personality)
    assert entry.recall_count == 1


def test_on_recall_opens_lability_window():
    """on_recall sets _is_labile = True and _lability_deadline in the future."""
    entry = _make_entry()
    personality = {"neuroticism": 0.5, "openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5}
    entry.on_recall(personality)
    assert entry._is_labile is True
    assert entry._lability_deadline > time.time()


def test_lability_window_personality_dependent():
    """High neuroticism -> longer lability window."""
    entry1 = _make_entry(id="e1")
    entry2 = _make_entry(id="e2")
    p_high_n = {"neuroticism": 0.9, "openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5}
    p_low_n = {"neuroticism": 0.1, "openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5}
    entry1.on_recall(p_high_n)
    entry2.on_recall(p_low_n)
    assert entry1._lability_deadline > entry2._lability_deadline


def test_reconsolidation_update_during_window():
    """on_reconsolidation_update modifies weight when labile."""
    entry = _make_entry(emotional_weight=0.7)
    personality = {"neuroticism": 0.5, "openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5}
    entry.on_recall(personality)
    entry.on_reconsolidation_update("validation", 1.0)
    assert entry.emotional_weight < 0.7  # validation reduces weight
    assert entry._is_labile is False  # reconsolidated


def test_reconsolidation_update_outside_window():
    """on_reconsolidation_update does nothing when not labile."""
    entry = _make_entry(emotional_weight=0.7)
    entry.on_reconsolidation_update("validation", 1.0)
    assert entry.emotional_weight == 0.7  # unchanged


def test_on_inject_contradiction():
    """on_inject with contradiction raises temperature."""
    entry = _make_entry(temperature=0.3)
    entry.on_inject("contradiction", 1.0)
    assert entry.temperature > 0.3


def test_on_inject_validation():
    """on_inject with validation lowers temperature."""
    entry = _make_entry(temperature=0.8)
    entry.on_inject("validation", 1.0)
    assert entry.temperature < 0.8


def test_on_inject_betrayal_spike():
    """on_inject with betrayal causes major heat spike."""
    entry = _make_entry(temperature=0.3)
    entry.on_inject("betrayal", 1.0)
    assert entry.temperature == 1.0  # 0.3 + 1.0 = 1.3, clamped to 1.0


def test_peak_temperature_updated():
    """on_inject updates peak_temperature."""
    entry = _make_entry(temperature=0.3, peak_temperature=0.3)
    entry.on_inject("betrayal", 1.0)
    assert entry.peak_temperature == 1.0


def test_serialization_roundtrip():
    """to_dict/from_dict preserves all fields."""
    entry = _make_entry(tags=["test", "memory"], entities={"person": ["bob"]})
    data = entry.to_dict()
    restored = UnifiedEntry.from_dict(data)
    assert restored.id == entry.id
    assert restored.text == entry.text
    assert restored.tags == entry.tags
    assert restored.entities == entry.entities
    assert restored.temperature == entry.temperature
    assert restored.emotional_weight == entry.emotional_weight
