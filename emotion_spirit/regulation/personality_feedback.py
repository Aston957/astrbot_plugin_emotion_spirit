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
    """Apply small personality shifts based on activity categories.

    v1.2.7: 新增 compute_feedback 只读方法 (回避与 personality_drift 双写).
    apply_activity_effect 标 deprecated (仅保留供旧调用方过渡).
    """

    def __init__(self, feedback_rate: float = 0.002):
        self._rate = feedback_rate

    def compute_feedback(self, personality: dict, activity_category: str) -> dict[str, float]:
        """只读计算活动 category 对 traits 的 delta, 不修改原 dict.

        Args:
            personality: 人格 dict (只读, 不改).
            activity_category: 活动分类 (creative/social/intellectual/physical/rest/routine).

        Returns:
            dict[str, float]: trait → delta (0.0 若无影响).
        """
        effects = ACTIVITY_PERSONALITY_FEEDBACK.get(activity_category, {})
        delta = {}
        for trait, base_delta in effects.items():
            current = personality.get(trait, 0.5)
            adjusted = base_delta * self._rate
            # 钳制后返回实际 delta (非绝对值)
            clamped_new = max(0.05, min(0.95, current + adjusted))
            delta[trait] = clamped_new - current
        return delta

    def apply_activity_effect(self, personality: dict, activity_category: str):
        """[deprecated] 直接改传入 dict 的旧方法. 请改用 compute_feedback (只读)."""
        effects = ACTIVITY_PERSONALITY_FEEDBACK.get(activity_category, {})
        for trait, delta in effects.items():
            current = personality.get(trait, 0.5)
            personality[trait] = clamp(current + delta * self._rate, 0.05, 0.95)