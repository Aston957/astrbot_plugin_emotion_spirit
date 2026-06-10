"""UnifiedEntry -- self-contained memory entity.

Each memory is a self-contained individual that manages its own
temperature, emotional weight, and reconsolidation state.

The pool (UnifiedMemory) manages collective state; the entry
manages "what happens to me."

Reference: docs/UNIFIED_MEMORY_LIFESIM_DESIGN_2026-06-10.md section 3.1.1
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .decay_model import DecayModel

_clamp = DecayModel.clamp

__all__ = ["UnifiedEntry"]


@dataclass
class UnifiedEntry:
    """Unified memory entry -- self-contained event entity.

    Identity fields (immutable): id, text, tags, entities, source_user, privacy, created_at
    Self-state (mutable, managed by self): temperature, emotional_weight, mass, tier, etc.
    """

    # -- Identity (immutable) --
    id: str
    text: str
    tags: list[str]
    entities: dict           # {"person": ["bob"], "place": [...]}
    source_user: str
    privacy: str             # "private" / "circle" / "public"
    created_at: float

    # -- Self-state (mutable) --
    temperature: float       # Current temperature [0, 1]
    emotional_weight: float  # Emotional weight [0, 1]
    mass: float              # Emotional mass (affects cooling speed) [0, 1]
    tier: str                # "buffer" / "warm" / "cold" / "ghost"
    is_ghost: bool
    recall_count: int
    last_recalled: float
    peak_temperature: float

    # -- Reconsolidation state --
    _is_labile: bool = field(default=False)
    _lability_deadline: float = field(default=0.0)

    # -- Cascade tracking --
    cascade_generation: int = field(default=0)

    # -- Ghost tracking --
    _ticks_above_ghost_threshold: int = field(default=0)

    def on_recall(self, personality: dict[str, float]) -> None:
        """Recall event: raise temperature + open reconsolidation window.

        Nader et al. (2000): recall makes memory labile.
        Schiller et al. (2010): window ~6h, personality-dependent.
        """
        self.temperature = _clamp(self.temperature + 0.3, 0, 1)
        self.emotional_weight = _clamp(self.emotional_weight + 0.1, 0, 1)
        self.last_recalled = time.time()
        self.recall_count += 1

        # Open reconsolidation window (personality-dependent duration)
        self._is_labile = True
        window_hours = 6 * (
            (1 + 0.5 * personality.get("neuroticism", 0.5))
            * (1 - 0.3 * personality.get("openness", 0.5))
            * (1 + 0.3 * personality.get("conscientiousness", 0.5))
            * (1 - 0.3 * personality.get("extraversion", 0.5))
        )
        self._lability_deadline = time.time() + _clamp(window_hours, 2, 16) * 3600

    def on_reconsolidation_update(self, signal_type: str, intensity: float) -> None:
        """During lability window, external signals can modify emotional content.

        Positive signals (validation) -> weight decreases (trauma repair)
        Negative signals (betrayal) -> weight increases (wound deepens)
        """
        if not self._is_labile or time.time() > self._lability_deadline:
            self._is_labile = False
            return

        valence_shifts = {
            "validation": -0.2,
            "reinforcement": 0.1,
            "contradiction": 0.2,
            "betrayal": 0.4,
            "revelation": 0.3,
        }
        shift = valence_shifts.get(signal_type, 0) * intensity
        self.emotional_weight = _clamp(self.emotional_weight + shift, 0, 1)
        self._is_labile = False  # Reconsolidated

    def on_inject(self, signal_type: str, intensity: float) -> None:
        """External signal: adjust temperature based on signal type."""
        effects = {
            "contradiction": 0.5,
            "reinforcement": 0.3,
            "revelation": 0.8,
            "betrayal": 1.0,
            "validation": -0.4,
        }
        delta = effects.get(signal_type, 0) * intensity
        self.temperature = _clamp(self.temperature + delta, 0, 1)
        self.peak_temperature = max(self.peak_temperature, self.temperature)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for persistence."""
        return {
            "id": self.id,
            "text": self.text,
            "tags": self.tags,
            "entities": self.entities,
            "source_user": self.source_user,
            "privacy": self.privacy,
            "created_at": self.created_at,
            "temperature": round(self.temperature, 6),
            "emotional_weight": round(self.emotional_weight, 6),
            "mass": round(self.mass, 6),
            "tier": self.tier,
            "is_ghost": self.is_ghost,
            "recall_count": self.recall_count,
            "last_recalled": self.last_recalled,
            "peak_temperature": round(self.peak_temperature, 6),
            "cascade_generation": self.cascade_generation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnifiedEntry:
        """Deserialize from dict."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
