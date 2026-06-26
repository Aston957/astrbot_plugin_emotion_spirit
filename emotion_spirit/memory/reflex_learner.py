"""ReflexLearner — behavior feedback loop (zero LLM).

Adjusts agent gate thresholds based on user response signals.
This is distinct from LifeSimulator v2's ``adapt_plan()`` —
ReflexLearner adjusts **agent gate thresholds**, not daily events.

Signals: +1.0 (strategy effective), 0.0 (uncertain), -1.0 (strategy failed).
"""

from __future__ import annotations

from typing import Any

from ..core.config import REFLEX_LEARNER_CONFIG

__all__ = ["ReflexLearner", "ReflexLearnerStore"]


class ReflexLearnerStore:
    """Persistent store for learned gate deltas.

    Each delta is clamped to [-0.2, +0.2] to prevent runaway drift.
    """

    def __init__(self) -> None:
        self._deltas: dict[str, dict[str, float]] = {}

    def get_delta(self, agent_name: str, key: str) -> float:
        """Return current delta for *agent_name*/*key* (0.0 if absent)."""
        return self._deltas.get(agent_name, {}).get(key, 0.0)

    def set_delta(self, agent_name: str, key: str, value: float) -> None:
        """Set delta, clamped to [-0.2, +0.2]."""
        self._deltas.setdefault(agent_name, {})[key] = max(-0.2, min(0.2, value))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict (for JSON persistence)."""
        return dict(self._deltas)

    def from_dict(self, data: dict[str, Any]) -> None:
        """Restore from plain dict."""
        self._deltas = {k: dict(v) for k, v in data.items() if isinstance(v, dict)}


class ReflexLearner:
    """Zero-LLM behavior feedback: adjust gate thresholds based on user response.

    Parameters
    ----------
    store:
        Backing store for persistent deltas.
    learning_rate:
        Step size per behavior signal (default 0.01).
    """

    LEARNABLE = [
        ("memory", "intimacy_recall_threshold"),
        ("personality", "superego_caution_threshold"),
        ("life", "life_sim_adapt_threshold"),
        ("relationship", "relationship_update_threshold"),
    ]

    def __init__(self, store: ReflexLearnerStore, learning_rate: float | None = None) -> None:
        self._store = store
        self._lr = learning_rate if learning_rate is not None else REFLEX_LEARNER_CONFIG.get("learning_rate", 0.01)

    @property
    def store(self) -> ReflexLearnerStore:
        """Expose the backing store (read-only intent)."""
        return self._store

    def learn(self, behavior: float) -> None:
        """Adjust all learnable parameters based on *behavior* signal.

        Args:
            behavior: +1.0 (strategy effective), 0.0 (uncertain), -1.0 (strategy failed).
        """
        for agent_name, key in self.LEARNABLE:
            delta = self._store.get_delta(agent_name, key)
            if behavior > 0:
                delta += self._lr
            elif behavior < 0:
                delta -= self._lr
            self._store.set_delta(agent_name, key, delta)


def compute_behavior(gap_seconds: float) -> float:
    """Compute behavior signal from user response gap.

    +1.0 = user replied within engaged threshold (strategy effective)
     0.0 = uncertain (between engaged and ignored)
    -1.0 = user ignored (beyond ignored threshold)
    """
    engaged = REFLEX_LEARNER_CONFIG.get("behavior_engaged_seconds", 300.0)
    ignored = REFLEX_LEARNER_CONFIG.get("behavior_ignored_seconds", 7200.0)
    if gap_seconds <= engaged:
        return 1.0
    if gap_seconds >= ignored:
        return -1.0
    return 0.0
