"""Integration tests for MemoryPool (Phase D: unified architecture).

Tests:
- MemoryPool add + vector computation
- Decay: tick() updates weight and vectors
- Vector recall: MemorySampler.search_similar()
- Persistence: MemoryPool roundtrip through store
"""

from __future__ import annotations

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
astrbot_api_mock.logger.debug = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

import pytest
from emotion_spirit.memory.memory_pool import MemoryPool
from emotion_spirit.memory.unified_entry import UnifiedEntry


# ═══ MemoryPool add + vector ═══


class TestMemoryPoolAdd:
    """Test MemoryPool.add() creates entries with correct fields."""

    def test_add_creates_unified_entry(self):
        """MemoryPool.add() creates UnifiedEntry with correct emotional_weight."""
        pool = MemoryPool()
        entry = pool.add(
            text="今天很开心",
            raw_weight=0.7,
            phi=0.5,
            tags=["joy", "chat"],
            source_user="user1",
        )
        assert entry.emotional_weight == 0.7
        assert len(pool.buffer) == 1

    def test_add_backward_compat(self):
        """MemoryPool.add() without extra params still works."""
        pool = MemoryPool()
        entry = pool.add("test", 0.5, 0.5, ["test"], "user1")
        assert entry is not None


# ═══ Decay tick ═══


class TestDecayTick:
    """Test that tick() runs decay and updates vectors."""

    def test_tick_decays_weight_and_vector(self):
        """After tick() with time skip, weight and vector dominance decrease."""
        pool = MemoryPool()
        entry = pool.add("test", 0.9, 0.5, ["t"], "u1")
        entry.vector = UnifiedEntry.compute_vector(0.5, 0.5, 0.9)
        pool._vector_index[entry.id] = entry.vector
        old_weight = entry.emotional_weight
        old_dominance = entry.vector[2]
        # Force time skip
        entry.created_at = time.time() - 7200 * 100
        pool._last_tick = time.time() - 7200
        pool.tick()
        assert entry.emotional_weight < old_weight
        assert entry.vector[2] < old_dominance


# ═══ Vector recall in prompt ═══


class TestVectorRecall:
    """Test that MemorySampler can produce vector recall results."""

    def test_sampler_search_similar(self):
        """MemorySampler.search_similar() returns results."""
        pool = MemoryPool()
        e1 = pool.add("开心的一天", 0.7, 0.5, ["joy"], "u1")
        e1.vector = UnifiedEntry.compute_vector(0.9, 0.8, 0.7)
        pool._vector_index[e1.id] = e1.vector
        e1.tier = "warm"

        e2 = pool.add("难过的事情", 0.8, 0.5, ["sad"], "u1")
        e2.vector = UnifiedEntry.compute_vector(-0.7, 0.6, 0.8)
        pool._vector_index[e2.id] = e2.vector
        e2.tier = "warm"

        from emotion_spirit.memory.memory_sampler import MemorySampler
        sampler = MemorySampler(pool)
        results = sampler.search_similar((0.9, 0.8, 0.7), k=1)
        assert len(results) == 1
        assert results[0].entry.text == "开心的一天"


# ═══ Persistence roundtrip ═══


class TestPersistence:
    """Test MemoryPool serialization roundtrip."""

    def test_roundtrip_with_vectors(self):
        """Entries with vectors survive to_dict/from_dict."""
        pool = MemoryPool()
        pool.add("test1", 0.7, 0.5, ["t1"], "u1")
        pool.add("test2", 0.4, 0.5, ["t2"], "u2")

        data = pool.to_dict()
        restored = MemoryPool.from_dict(data)

        all_entries = restored.all_entries()
        assert len(all_entries) == 2
        for entry in all_entries:
            assert isinstance(entry.vector, tuple)
            assert len(entry.vector) == 3

    def test_roundtrip_preserves_vector_index(self):
        """Vector index is rebuilt after from_dict()."""
        pool = MemoryPool()
        e1 = pool.add("test1", 0.7, 0.5, ["t1"], "u1")
        e1.vector = UnifiedEntry.compute_vector(0.9, 0.8, 0.7)
        pool._vector_index[e1.id] = e1.vector

        data = pool.to_dict()
        restored = MemoryPool.from_dict(data)

        assert e1.id in restored._vector_index
        assert restored._vector_index[e1.id] == e1.vector
