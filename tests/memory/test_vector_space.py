"""Tests for PAD vector memory space.

Tests cover:
- UnifiedEntry.compute_vector() — PAD vector computation
- UnifiedEntry serialization — vector roundtrip
- UnifiedMemory.search_by_vector() — vector-based retrieval
- CascadeEngine.relevance() — 4-component relevance with vector
- MemorySampler — vector-enhanced mood-congruent recall
- Backward compatibility — old data without vector field
"""

from __future__ import annotations

import sys
import os
import math
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

import pytest

from emotion_spirit.memory.unified_entry import UnifiedEntry
from emotion_spirit.memory.memory_pool import MemoryPool
from emotion_spirit.memory.cascade_engine import CascadeEngine
from emotion_spirit.memory.memory_sampler import MemorySampler


# ═══ UnifiedEntry.compute_vector ═══


class TestComputeVector:
    """Test PAD vector computation from existing fields."""

    def test_positive_valence(self):
        """Positive valence → v > 0.5."""
        v, a, d = UnifiedEntry.compute_vector(
            valence=0.8, arousal=0.5, emotional_weight=0.5, mass=0.5, privacy="private",
        )
        assert v == pytest.approx(0.9, abs=0.01)
        assert a == pytest.approx(0.5)
        assert 0.0 <= d <= 1.0

    def test_negative_valence(self):
        """Negative valence → v < 0.5."""
        v, a, d = UnifiedEntry.compute_vector(
            valence=-0.8, arousal=0.5, emotional_weight=0.5, mass=0.5, privacy="private",
        )
        assert v == pytest.approx(0.1, abs=0.01)

    def test_neutral_valence(self):
        """Zero valence → v = 0.5."""
        v, a, d = UnifiedEntry.compute_vector(
            valence=0.0, arousal=0.5, emotional_weight=0.5, mass=0.5, privacy="private",
        )
        assert v == pytest.approx(0.5)

    def test_arousal_passthrough(self):
        """Arousal maps directly."""
        _, a, _ = UnifiedEntry.compute_vector(
            valence=0.0, arousal=0.7, emotional_weight=0.5, mass=0.5, privacy="private",
        )
        assert a == pytest.approx(0.7)

    def test_dominance_equals_weight(self):
        """Dominance = emotional_weight (simplified formula)."""
        _, _, d_high = UnifiedEntry.compute_vector(
            valence=0.0, arousal=0.5, emotional_weight=0.9, mass=0.5, privacy="private",
        )
        _, _, d_low = UnifiedEntry.compute_vector(
            valence=0.0, arousal=0.5, emotional_weight=0.3, mass=0.5, privacy="private",
        )
        assert d_high == pytest.approx(0.9)
        assert d_low == pytest.approx(0.3)

    def test_dominance_ignores_privacy(self):
        """Dominance is independent of privacy (simplified formula)."""
        _, _, d_private = UnifiedEntry.compute_vector(
            valence=0.0, arousal=0.5, emotional_weight=0.7, mass=0.5, privacy="private",
        )
        _, _, d_public = UnifiedEntry.compute_vector(
            valence=0.0, arousal=0.5, emotional_weight=0.7, mass=0.5, privacy="public",
        )
        assert d_private == d_public

    def test_clamp_extremes(self):
        """Extreme values clamped to [0, 1]."""
        v, a, d = UnifiedEntry.compute_vector(
            valence=99.0, arousal=-5.0, emotional_weight=99.0, mass=99.0, privacy="private",
        )
        assert 0.0 <= v <= 1.0
        assert 0.0 <= a <= 1.0
        assert 0.0 <= d <= 1.0


# ═══ Serialization ═══


class TestVectorSerialization:
    """Test vector field survives to_dict/from_dict roundtrip."""

    def test_roundtrip(self):
        entry = UnifiedEntry(
            id="test_0", text="hello", tags=[], entities={},
            source_user="u1", privacy="private", created_at=1000.0,
            temperature=0.5, emotional_weight=0.5, mass=0.5,
            tier="buffer", is_ghost=False, recall_count=0,
            last_recalled=0.0, peak_temperature=0.5,
            vector=(0.7, 0.3, 0.6),
        )
        d = entry.to_dict()
        assert d["vector"] == [0.7, 0.3, 0.6]

        restored = UnifiedEntry.from_dict(d)
        assert restored.vector == (0.7, 0.3, 0.6)

    def test_backward_compatibility(self):
        """Old data without vector field → default (0,0,0)."""
        old_data = {
            "id": "old_0", "text": "legacy", "tags": [], "entities": {},
            "source_user": "u1", "privacy": "private", "created_at": 1000.0,
            "temperature": 0.5, "emotional_weight": 0.5, "mass": 0.5,
            "tier": "buffer", "is_ghost": False, "recall_count": 0,
            "last_recalled": 0.0, "peak_temperature": 0.5,
            "cascade_generation": 0,
        }
        entry = UnifiedEntry.from_dict(old_data)
        assert entry.vector == (0.0, 0.0, 0.0)


# ═══ UnifiedMemory vector search ═══


class TestVectorSearch:
    """Test MemoryPool.search_by_vector()."""

    def _make_memory(self) -> MemoryPool:
        pool = MemoryPool()
        # Add entries with specific vectors
        e1 = pool.add("开心的一天", 0.7, 0.5, ["positive"], "u1")
        e1.vector = UnifiedEntry.compute_vector(0.9, 0.8, 0.7)
        pool._vector_index[e1.id] = e1.vector

        e2 = pool.add("难过的事情", 0.8, 0.5, ["negative"], "u1")
        e2.vector = UnifiedEntry.compute_vector(-0.7, 0.6, 0.8)
        pool._vector_index[e2.id] = e2.vector

        e3 = pool.add("普通的一天", 0.3, 0.5, ["neutral"], "u1")
        e3.vector = UnifiedEntry.compute_vector(0.0, 0.3, 0.3)
        pool._vector_index[e3.id] = e3.vector

        return pool

    def test_search_returns_closest(self):
        pool = self._make_memory()
        results = pool.search_by_vector((0.9, 0.8, 0.7), top_k=1)
        assert len(results) == 1
        entry_id, dist = results[0]
        entry = pool._find_entry_by_id(entry_id)
        assert entry.text == "开心的一天"

    def test_search_top_k(self):
        pool = self._make_memory()
        results = pool.search_by_vector((0.5, 0.5, 0.5), top_k=2)
        assert len(results) == 2
        assert results[0][1] <= results[1][1]

    def test_search_with_tier_filter(self):
        pool = self._make_memory()
        for e in pool.all_entries():
            if e.text == "难过的事情":
                e.tier = "warm"
        results = pool.search_by_vector((0.0, 0.6, 0.8), top_k=5, tier="warm")
        assert len(results) == 1
        entry = pool._find_entry_by_id(results[0][0])
        assert entry.text == "难过的事情"

    def test_update_vector(self):
        pool = self._make_memory()
        entry_id = pool.all_entries()[0].id
        pool.update_vector(entry_id, (0.1, 0.2, 0.3))
        entry = pool._find_entry_by_id(entry_id)
        assert entry.vector == (0.1, 0.2, 0.3)
        assert pool._vector_index[entry_id] == (0.1, 0.2, 0.3)

    def test_vector_index_cleanup(self):
        """Vector index should be cleaned up when entry is removed."""
        pool = self._make_memory()
        entry = pool.all_entries()[0]
        entry_id = entry.id
        assert entry_id in pool._vector_index
        pool._remove_entry(entry)
        assert entry_id not in pool._vector_index


# ═══ CascadeEngine vector relevance ═══


class TestCascadeRelevanceWithVector:
    """Test CascadeEngine.relevance() with vector component."""

    def test_identical_vectors_higher_relevance(self):
        """Same tags/entities/text but identical vectors → higher relevance."""
        a = UnifiedEntry(
            id="a", text="hello world", tags=["t1"], entities={"p": ["bob"]},
            source_user="u", privacy="private", created_at=0,
            temperature=0.5, emotional_weight=0.5, mass=0.5,
            tier="buffer", is_ghost=False, recall_count=0,
            last_recalled=0.0, peak_temperature=0.5,
            vector=(0.5, 0.5, 0.5),
        )
        b_same = UnifiedEntry(
            id="b", text="hello world", tags=["t1"], entities={"p": ["bob"]},
            source_user="u", privacy="private", created_at=0,
            temperature=0.5, emotional_weight=0.5, mass=0.5,
            tier="buffer", is_ghost=False, recall_count=0,
            last_recalled=0.0, peak_temperature=0.5,
            vector=(0.5, 0.5, 0.5),
        )
        b_diff = UnifiedEntry(
            id="b", text="hello world", tags=["t1"], entities={"p": ["bob"]},
            source_user="u", privacy="private", created_at=0,
            temperature=0.5, emotional_weight=0.5, mass=0.5,
            tier="buffer", is_ghost=False, recall_count=0,
            last_recalled=0.0, peak_temperature=0.5,
            vector=(0.0, 1.0, 0.0),
        )
        engine = CascadeEngine()
        r_same = engine.relevance(a, b_same)
        r_diff = engine.relevance(a, b_diff)
        assert r_same > r_diff

    def test_vector_distance_static(self):
        """vector_distance returns correct similarity."""
        # Same point → similarity = 1.0
        assert CascadeEngine.vector_distance((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)) == pytest.approx(1.0)
        # Opposite corners (one is zero) → euclidean only → 0.0
        sim = CascadeEngine.vector_distance((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
        assert sim == pytest.approx(0.0, abs=0.01)

    def test_vector_distance_hybrid_direction_vs_magnitude(self):
        """Cosine (direction) weighted 0.6, euclidean (magnitude) weighted 0.4."""
        # Same direction, different magnitude → cosine ≈ 1.0
        a = (0.9, 0.8, 0.7)
        b = (0.45, 0.4, 0.35)  # same direction, half magnitude
        sim = CascadeEngine.vector_distance(a, b)
        # cosine = 1.0, euclidean dist ≈ 0.62, magnitude_sim ≈ 0.64
        # result ≈ 0.6*1.0 + 0.4*0.64 ≈ 0.86
        assert sim > 0.8  # high — same direction

    def test_vector_distance_both_zero(self):
        """Both zero vectors → similarity = 1.0 (both unknown → match)."""
        assert CascadeEngine.vector_distance((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)) == pytest.approx(1.0)

    def test_vector_distance_one_zero(self):
        """One zero vector → euclidean only (direction meaningless)."""
        sim = CascadeEngine.vector_distance((0.0, 0.0, 0.0), (0.5, 0.5, 0.5))
        # euclidean dist = √0.75 ≈ 0.866, max = √3 ≈ 1.732 → magnitude_sim ≈ 0.5
        assert 0.4 < sim < 0.6


# ═══ MemorySampler vector integration ═══


class TestMemorySamplerVector:
    """Test MemorySampler with vector-enhanced mood-congruent recall."""

    def test_search_similar(self):
        pool = MemoryPool()
        e1 = pool.add("开心", 0.7, 0.5, ["positive"], "u1")
        e1.vector = UnifiedEntry.compute_vector(0.9, 0.8, 0.7)
        pool._vector_index[e1.id] = e1.vector

        e2 = pool.add("难过", 0.8, 0.5, ["negative"], "u1")
        e2.vector = UnifiedEntry.compute_vector(-0.7, 0.6, 0.8)
        pool._vector_index[e2.id] = e2.vector

        e3 = pool.add("中性", 0.3, 0.5, ["neutral"], "u1")
        e3.vector = UnifiedEntry.compute_vector(0.0, 0.3, 0.3)
        pool._vector_index[e3.id] = e3.vector

        sampler = MemorySampler(pool)
        results = sampler.search_similar((0.9, 0.8, 0.7), k=1)
        assert len(results) == 1
        assert results[0].entry.text == "开心"

    def test_sample_with_mood_vec(self):
        pool = MemoryPool()
        e1 = pool.add("开心", 0.7, 0.5, ["positive"], "u1")
        e1.vector = UnifiedEntry.compute_vector(0.9, 0.8, 0.7)
        pool._vector_index[e1.id] = e1.vector

        e2 = pool.add("难过", 0.8, 0.5, ["negative"], "u1")
        e2.vector = UnifiedEntry.compute_vector(-0.7, 0.6, 0.8)
        pool._vector_index[e2.id] = e2.vector

        sampler = MemorySampler(pool)
        personality = {"openness": 0.5, "extraversion": 0.5, "agreeableness": 0.5,
                       "conscientiousness": 0.5, "neuroticism": 0.5}
        results = sampler.sample(personality, k=1, mood_vec=(0.9, 0.8, 0.7))
        assert len(results) == 1


# ═══ Vector dynamic updates ═══


class TestVectorDynamicUpdate:
    """Test that vectors update on reconsolidation and decay."""

    def test_recompute_vector_updates_dominance(self):
        """recompute_vector() updates dominance from current emotional_weight."""
        entry = UnifiedEntry(
            id="t", text="test", tags=[], entities={},
            source_user="u", privacy="private", created_at=0,
            temperature=0.5, emotional_weight=0.7, mass=0.5,
            tier="buffer", is_ghost=False, recall_count=0,
            last_recalled=0.0, peak_temperature=0.5,
            vector=(0.5, 0.5, 0.7),
        )
        # Simulate weight change
        entry.emotional_weight = 0.3
        entry.recompute_vector()
        # Valence and arousal unchanged, dominance updated
        assert entry.vector[0] == pytest.approx(0.5)
        assert entry.vector[1] == pytest.approx(0.5)
        assert entry.vector[2] == pytest.approx(0.3)

    def test_reconsolidation_updates_vector(self):
        """on_reconsolidation_update() triggers vector recompute."""
        import time as _time
        entry = UnifiedEntry(
            id="t", text="test", tags=[], entities={},
            source_user="u", privacy="private", created_at=0,
            temperature=0.5, emotional_weight=0.5, mass=0.5,
            tier="buffer", is_ghost=False, recall_count=0,
            last_recalled=0.0, peak_temperature=0.5,
            vector=(0.5, 0.5, 0.5),
        )
        # Open reconsolidation window
        entry._is_labile = True
        entry._lability_deadline = _time.time() + 3600
        old_dominance = entry.vector[2]
        # Betrayal increases weight
        entry.on_reconsolidation_update("betrayal", 1.0)
        assert entry.vector[2] > old_dominance

    def test_decay_updates_vector_in_memory(self):
        """MemoryPool.tick() updates vector after weight decay."""
        pool = MemoryPool()
        entry = pool.add("test", 0.9, 0.5, ["t"], "u1")
        entry.vector = UnifiedEntry.compute_vector(0.5, 0.5, 0.9)
        pool._vector_index[entry.id] = entry.vector
        old_dominance = entry.vector[2]
        # Force time skip by manipulating created_at
        entry.created_at = time.time() - 7200 * 100  # very old
        pool._last_tick = time.time() - 7200  # force tick to process
        pool.tick()
        # Weight should have decayed → dominance should be lower
        assert entry.vector[2] < old_dominance
