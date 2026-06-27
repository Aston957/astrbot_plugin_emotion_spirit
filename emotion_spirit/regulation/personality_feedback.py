"""Activity → personality feedback mechanism.

Activities slowly shift personality over time. The feedback rate is
configurable to prevent rapid drift.
"""
from __future__ import annotations
from typing import Any

from ..core.registry import register
from ..core.utils import clamp


# Activity category → trait delta (per occurrence, scaled by feedback_rate)
ACTIVITY_PERSONALITY_FEEDBACK: dict[str, dict[str, float]] = {
    "creative":     {"openness": +0.003, "extraversion": -0.001},
    "social":       {"extraversion": +0.004, "agreeableness": +0.001},
    "intellectual": {"openness": +0.002, "conscientiousness": +0.001},
    "physical":     {"extraversion": +0.001, "neuroticism": -0.001},
    "rest":         {"neuroticism": -0.003, "extraversion": -0.001},
    "routine":      {"conscientiousness": +0.002, "openness": -0.001},
}


@register(
    name="personality_feedback",
    provides=["PersonalityFeedback"],
    depends_on=[],
)
class PersonalityFeedback:
    """Apply small personality shifts based on activity categories."""

    def __init__(self, feedback_rate: float = 0.002):
        self._rate = feedback_rate

    def apply_activity_effect(self, personality: dict, activity_category: str):
        """Apply feedback from an activity to personality traits."""
        effects = ACTIVITY_PERSONALITY_FEEDBACK.get(activity_category, {})
        for trait, delta in effects.items():
            current = personality.get(trait, 0.5)
            personality[trait] = clamp(current + delta * self._rate, 0.05, 0.95)