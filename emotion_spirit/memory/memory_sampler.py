"""MemorySampler -- personality-weighted multi-layer memory sampling.

Reads from MemoryPool's 4 layers (buffer/warm/cold/ghost) using
personality-dependent weights and weighted random selection.

Reference: docs/UNIFIED_MEMORY_LIFESIM_DESIGN_2026-06-10.md section 5.2
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from .unified_entry import UnifiedEntry
from .cascade_engine import CascadeEngine
from ..core.registry import register

if TYPE_CHECKING:
    from .memory_pool import MemoryPool

from ..core.utils import clamp as _clamp

__all__ = ["MemorySampler", "SampledMemory"]


@dataclass
class SampledMemory:
    """A sampled memory with its layer and composite score."""
    entry: UnifiedEntry
    layer: str
    score: float


@register(
    name="memory_sampler",
    provides=["MemorySampler"],
    depends_on=["memory_pool"],
    param_wire={"memory_pool": "memory"},
)
class MemorySampler:
    """Personality-weighted multi-layer memory sampler."""

    def __init__(self, memory: "MemoryPool") -> None:
        """Phase D: memory is now MemoryPool (was UnifiedMemory)."""
        self._memory = memory

    def sample(
        self,
        personality: dict[str, float],
        k: int = 5,
        mood_vec: tuple[float, float, float] | None = None,
    ) -> list[SampledMemory]:
        """Sample k memories from 4 layers using personality-weighted random selection.

        Args:
            personality: Personality dimensions for layer weighting.
            k: Number of memories to sample.
            mood_vec: Optional mood vector for vector-based mood-congruent recall.
        """
        weights = self._compute_layer_weights(personality)
        hot_temp = self._memory.mean_temperature()

        # Thermal modulation: high temp -> increase ghost weight
        if hot_temp > 0.7:
            weights["ghost"] *= 1.5
            weights["buffer"] *= 0.8
            total = sum(weights.values())
            weights = {k: v / total for k, v in weights.items()}

        # Build candidates from all layers
        candidates: list[tuple[UnifiedEntry, str, float]] = []
        for layer, w in weights.items():
            entries = self._memory.get_layer(layer)
            for entry in entries:
                score = self._composite_score(entry, layer, w, hot_temp, mood_vec)
                candidates.append((entry, layer, score))

        if not candidates:
            return []

        # Weighted random sample
        return self._weighted_random_sample(candidates, k)

    def _compute_layer_weights(self, personality: dict[str, float]) -> dict[str, float]:
        """Personality -> 4-layer sampling weights (Gross & John 2003, Gray 2000)."""
        w_buffer = (0.3
                    + 0.2 * personality.get("openness", 0.5)
                    + 0.1 * personality.get("extraversion", 0.5))
        w_warm = (0.3
                  + 0.15 * personality.get("agreeableness", 0.5)
                  + 0.1 * abs(personality.get("neuroticism", 0.5) - 0.5))
        w_cold = (0.2
                  + 0.2 * personality.get("conscientiousness", 0.5)
                  + 0.1 * personality.get("openness", 0.5))
        w_ghost = (0.1
                   + 0.25 * personality.get("neuroticism", 0.5)
                   - 0.05 * personality.get("emotional_stability", 0.5))

        total = w_buffer + w_warm + w_cold + w_ghost
        return {
            "buffer": w_buffer / total,
            "warm": w_warm / total,
            "cold": w_cold / total,
            "ghost": max(0.01, w_ghost / total),
        }

    def _composite_score(
        self,
        entry: UnifiedEntry,
        layer: str,
        layer_weight: float,
        hot_temp: float,
        mood_vec: tuple[float, float, float] | None = None,
    ) -> float:
        """Composite recall score for a memory.

        Args:
            entry: The memory entry.
            layer: Layer name.
            layer_weight: Personality-derived layer weight.
            hot_temp: Mean temperature of the memory pool.
            mood_vec: Optional mood vector for vector-based mood-congruent recall.
        """
        age_hours = (time.time() - entry.created_at) / 3600
        tau = {"buffer": 0.5, "warm": 24, "cold": 168, "ghost": 8760}[layer]
        recency = math.exp(-age_hours / tau) if tau > 0 else 1.0
        emotional = entry.emotional_weight

        # Mood-congruent recall (Bower 1981) — vector-enhanced
        if mood_vec is not None:
            mood_match = CascadeEngine.vector_distance(entry.vector, mood_vec)
        else:
            mood_match = 1 - abs(entry.emotional_weight - hot_temp)
        resonance = 0.5 + 0.5 * mood_match

        return layer_weight * recency * emotional * resonance

    def search_similar(
        self,
        query_vec: tuple[float, float, float],
        k: int = 5,
    ) -> list[SampledMemory]:
        """Find k memories most similar to query_vec.

        Uses MemoryPool.search_by_vector for fast vector retrieval,
        then wraps results as SampledMemory.
        """
        raw = self._memory.search_by_vector(query_vec, top_k=k)
        results: list[SampledMemory] = []
        for entry_id, dist in raw:
            entry = self._memory._entries.get(entry_id)
            if entry is not None:
                results.append(SampledMemory(
                    entry=entry,
                    layer=entry.tier,
                    score=1.0 - dist / 1.732,  # normalize dist to similarity
                ))
        return results

    def _weighted_random_sample(
        self, candidates: list[tuple[UnifiedEntry, str, float]], k: int,
    ) -> list[SampledMemory]:
        """Weighted random selection from candidates."""
        total_score = sum(score for _, _, score in candidates)
        if total_score == 0:
            chosen = random.sample(candidates, min(k, len(candidates)))
            return [SampledMemory(entry=e, layer=l, score=s) for e, l, s in chosen]

        probabilities = [score / total_score for _, _, score in candidates]
        indices = list(range(len(candidates)))
        chosen_indices = random.choices(indices, weights=probabilities, k=min(k, len(candidates)))
        # Deduplicate
        seen = set()
        result = []
        for idx in chosen_indices:
            if idx not in seen:
                seen.add(idx)
                e, l, s = candidates[idx]
                result.append(SampledMemory(entry=e, layer=l, score=s))
        return result[:k]
