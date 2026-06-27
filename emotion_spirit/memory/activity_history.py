"""Activity history tracking with novelty decay mechanism.

Based on Thompson & Spencer (1966) habituation: repeated exposure reduces
response amplitude. Uses exponential decay for novelty scoring.

Used by LifeSimulator v2 (5.1) to bias activity selection away from
over-used categories (boredom avoidance).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

from ..core.registry import register
from ..core.utils import clamp

__all__ = ["ActivityHistory", "ActivityRecord"]


@dataclass
class ActivityRecord:
    """One occurrence of an activity."""

    activity: str
    category: str
    timestamp: float
    enjoyment: float = 0.5


@register(
    name="activity_history",
    provides=["ActivityHistory"],
    depends_on=[],
)
class ActivityHistory:
    """Track activity history with novelty decay.

    When the same category of activity is repeated frequently, novelty
    drops. This biases future selections toward fresh activities.

    Novelty formula:
        base = 0.5 + 0.5 * exp(-days_since_last / decay_days)
        penalty = max(0, 1.0 - len(recent_records) * 0.1)
        novelty = clamp(base * penalty, 0.0, 1.0)
    """

    def __init__(
        self,
        max_records: int = 100,
        novelty_decay_days: float = 3.0,
        boredom_threshold: float = 0.2,
        frequency_penalty: float = 0.3,
    ) -> None:
        self._records: list[ActivityRecord] = []
        self._max_records = max_records
        self._novelty_decay_days = novelty_decay_days
        self._boredom_threshold = boredom_threshold
        self._frequency_penalty = frequency_penalty

    @property
    def records(self) -> list[ActivityRecord]:
        """Read-only-ish access to the activity records list."""
        return self._records

    def record(self, activity: str, category: str, enjoyment: float = 0.5) -> None:
        """Record an activity occurrence.

        Args:
            activity: Free-form name (e.g. "做饭").
            category: Grouping key (e.g. "physical", "creative").
            enjoyment: Subjective enjoyment score in [0, 1].
        """
        self._records.append(
            ActivityRecord(
                activity=activity,
                category=category,
                timestamp=time.time(),
                enjoyment=enjoyment,
            )
        )
        # Trim oldest if over capacity
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]

    def get_novelty(self, category: str) -> float:
        """Get current novelty score for *category* in [0, 1].

        Uses exponential decay on recency, then a linear frequency penalty:
            novelty = 0.5 + 0.5 * exp(-days_since_last / decay_days)
            novelty *= max(0, 1.0 - count * 0.1)
        """
        recent = [r for r in self._records if r.category == category]
        if not recent:
            return 1.0  # Never done = fully novel

        now = time.time()
        last = max(r.timestamp for r in recent)
        days_since = (now - last) / 86400.0
        base = 0.5 + 0.5 * math.exp(-days_since / self._novelty_decay_days)
        # Frequency penalty applies from the 2nd repeat onward (first occurrence
        # keeps novelty > 0.9 so a brand-new activity is clearly fresh).
        penalty = max(0.0, 1.0 - max(0, len(recent) - 1) * self._frequency_penalty)
        return clamp(base * penalty, 0.0, 1.0)

    def is_bored(self, category: str) -> bool:
        """True if novelty for *category* is below the boredom threshold."""
        return self.get_novelty(category) < self._boredom_threshold

    def apply_novelty_bias(self, category_weights: dict[str, float]) -> dict[str, float]:
        """Multiply each category weight by its novelty score.

        Categories never recorded get novelty=1.0 (no bias applied).
        Returns a new dict; input is not mutated.
        """
        return {
            cat: w * self.get_novelty(cat)
            for cat, w in category_weights.items()
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize for persistence (keep last 50 records)."""
        return {
            "records": [
                {
                    "activity": r.activity,
                    "category": r.category,
                    "timestamp": r.timestamp,
                    "enjoyment": r.enjoyment,
                }
                for r in self._records[-50:]
            ],
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """Restore from serialized form."""
        self._records = [
            ActivityRecord(**r) for r in data.get("records", [])
        ]