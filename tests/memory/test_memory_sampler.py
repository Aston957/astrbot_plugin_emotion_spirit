"""Tests for memory_sampler.py -- personality-weighted multi-layer sampling (Phase D: MemoryPool)."""

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

from emotion_spirit.memory.memory_sampler import MemorySampler, SampledMemory
from emotion_spirit.memory.memory_pool import MemoryPool
from emotion_spirit.memory.unified_entry import UnifiedEntry


def _personality(**overrides):
    defaults = {"neuroticism": 0.5, "extraversion": 0.5, "openness": 0.5,
                "agreeableness": 0.5, "conscientiousness": 0.5, "emotional_stability": 0.5}
    defaults.update(overrides)
    return defaults


def _populate_memory(n=10):
    """Create a MemoryPool with entries in different tiers."""
    pool = MemoryPool()
    for i in range(n):
        pool.add(
            text=f"memory {i}", raw_weight=0.5, phi=0.5,
            tags=[f"tag{i}"], source_user="u1",
        )
    # Move some to warm
    moved = []
    for entry in list(pool.buffer)[:3]:
        entry.tier = "warm"
        moved.append(entry)
    pool.warm.extend(moved)
    pool.buffer = [e for e in pool.buffer if e.tier == "buffer"]
    return pool


def test_sample_returns_list():
    """sample() returns a list of SampledMemory."""
    pool = _populate_memory()
    sampler = MemorySampler(pool)
    results = sampler.sample(_personality(), k=3)
    assert isinstance(results, list)
    assert len(results) <= 3


def test_sample_respects_k():
    """sample() returns at most k entries."""
    pool = _populate_memory(20)
    sampler = MemorySampler(pool)
    results = sampler.sample(_personality(), k=5)
    assert len(results) <= 5


def test_sample_empty_pool():
    """sample() returns empty list for empty pool."""
    pool = MemoryPool()
    sampler = MemorySampler(pool)
    results = sampler.sample(_personality(), k=5)
    assert results == []


def test_sampled_memory_has_fields():
    """SampledMemory has entry, layer, score."""
    pool = _populate_memory()
    sampler = MemorySampler(pool)
    results = sampler.sample(_personality(), k=1)
    if results:
        s = results[0]
        assert hasattr(s, "entry")
        assert hasattr(s, "layer")
        assert hasattr(s, "score")
        assert s.layer in ("buffer", "warm", "cold", "ghost")


def test_layer_weights_sum_to_one():
    """_compute_layer_weights returns weights that sum to ~1."""
    sampler = MemorySampler(MemoryPool())
    weights = sampler._compute_layer_weights(_personality())
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01


def test_high_neuroticism_increases_ghost_weight():
    """High neuroticism -> higher ghost layer weight."""
    sampler = MemorySampler(MemoryPool())
    high_n = sampler._compute_layer_weights(_personality(neuroticism=0.9))
    low_n = sampler._compute_layer_weights(_personality(neuroticism=0.1))
    assert high_n["ghost"] > low_n["ghost"]


def test_high_extraversion_increases_buffer_weight():
    """High extraversion -> higher buffer layer weight."""
    sampler = MemorySampler(MemoryPool())
    high_e = sampler._compute_layer_weights(_personality(extraversion=0.9))
    low_e = sampler._compute_layer_weights(_personality(extraversion=0.1))
    assert high_e["buffer"] > low_e["buffer"]
