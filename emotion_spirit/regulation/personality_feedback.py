"""Activity → personality feedback mechanism.

Activities slowly shift personality over time. The feedback rate is
configurable to prevent rapid drift.
"""
from __future__ import annotations
from typing import Any

from ..core.registry import register
from ..core.utils import clamp


# Activity category → trait delta (per occurrence, scaled by feedback_rate)
# v1.3.0 Y-0b (§1.8): drift 表迁 13 维 (权威模型), Big Five delta 按派生权重
# 反向分配. 公式: docs/v1.3.0-y0-derivation-backing.md §1 (to_big_five 权重反向).
# 反向 N 注意: (1−ic) / (1−pat) 反向 → ic / pat 减 (drift 表内 N 为负时, ic/pat 加).
ACTIVITY_PERSONALITY_FEEDBACK: dict[str, dict[str, float]] = {
    # creative: 旧 {openness: +0.003, extraversion: -0.001}
    #   openness → {curiosity: +0.40×0.003, exploration_openness: +0.35×0.003, perception_acuity: +0.25×0.003}
    #   extraversion → {warmth: -0.25×0.001, expression_drive: -0.25×0.001, gossip: -0.20×0.001, intimacy_pull: -0.15×0.001, relational_gravity: -0.15×0.001}
    "creative": {
        "curiosity": +0.0012,
        "exploration_openness": +0.00105,
        "perception_acuity": +0.00075,
        "warmth_bias": -0.00025,
        "expression_drive": -0.00025,
        "gossip_tendency": -0.0002,
        "intimacy_pull": -0.00015,
        "relational_gravity": -0.00015,
    },
    # social: 旧 {extraversion: +0.004, agreeableness: +0.001}
    #   extraversion → {warmth: +0.001, expression_drive: +0.001, gossip: +0.0008, intimacy_pull: +0.0006, relational_gravity: +0.0006}
    #   agreeableness → {warmth: +0.0004, directness: +0.0003, relational_gravity: +0.0003}
    #   累加: warmth +0.0014, relational_gravity +0.0009
    "social": {
        "warmth_bias": +0.0014,
        "expression_drive": +0.001,
        "gossip_tendency": +0.0008,
        "intimacy_pull": +0.0006,
        "relational_gravity": +0.0009,
        "directness": +0.0003,
    },
    # intellectual: 旧 {openness: +0.002, conscientiousness: +0.001}
    #   openness → {curiosity: +0.0008, exploration_openness: +0.0007, perception_acuity: +0.0005}
    #   conscientiousness → {inner_coherence: +0.00065, patience: +0.00035}
    "intellectual": {
        "curiosity": +0.0008,
        "exploration_openness": +0.0007,
        "perception_acuity": +0.0005,
        "inner_coherence": +0.00065,
        "patience": +0.00035,
    },
    # physical: 旧 {extraversion: +0.001, neuroticism: -0.001}
    #   extraversion → {warmth: +0.00025, expression_drive: +0.00025, gossip: +0.0002, intimacy_pull: +0.00015, relational_gravity: +0.00015}
    #   neuroticism -0.001 → bp -0.0004, ic +0.00035 (反向), pat +0.00025 (反向)
    "physical": {
        "warmth_bias": +0.00025,
        "expression_drive": +0.00025,
        "gossip_tendency": +0.0002,
        "intimacy_pull": +0.00015,
        "relational_gravity": +0.00015,
        "boundary_permeability": -0.0004,
        "inner_coherence": +0.00035,
        "patience": +0.00025,
    },
    # rest: 旧 {neuroticism: -0.003, extraversion: -0.001}
    #   neuroticism -0.003 → bp -0.0012, ic +0.00105 (反向), pat +0.00075 (反向)
    #   extraversion -0.001 → {warmth: -0.00025, expression_drive: -0.00025, gossip: -0.0002, intimacy_pull: -0.00015, relational_gravity: -0.00015}
    "rest": {
        "boundary_permeability": -0.0012,
        "inner_coherence": +0.00105,
        "patience": +0.00075,
        "warmth_bias": -0.00025,
        "expression_drive": -0.00025,
        "gossip_tendency": -0.0002,
        "intimacy_pull": -0.00015,
        "relational_gravity": -0.00015,
    },
    # routine: 旧 {conscientiousness: +0.002, openness: -0.001}
    #   conscientiousness → {inner_coherence: +0.0013, patience: +0.0007}
    #   openness → {curiosity: -0.0004, exploration_openness: -0.00035, perception_acuity: -0.00025}
    "routine": {
        "inner_coherence": +0.0013,
        "patience": +0.0007,
        "curiosity": -0.0004,
        "exploration_openness": -0.00035,
        "perception_acuity": -0.00025,
    },
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