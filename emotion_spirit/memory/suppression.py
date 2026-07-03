"""Suppression system — dynamic suppression level computation.

Based on Gross & John (2003) process model, Wegner (1987) ironic process theory,
Pennebaker (1997) inhibition-confrontation paradigm, and Jack (1991) self-silencing.

Reference: docs/UNIFIED_MEMORY_LIFESIM_DESIGN_2026-06-10.md §7
"""

from __future__ import annotations
import math
from typing import Optional
from ..core.registry import register

from ..core.utils import clamp as _clamp

__all__ = ["SuppressionState"]


@register(
    name="suppression",
    provides=["SuppressionState"],
    depends_on=[],
)
class SuppressionState:
    """Dynamic suppression level computation."""

    def compute(
        self,
        personality: dict[str, float],
        context: dict,
        conscience_pressure: float,
        relationship_intimacy: float,
        force_state: Optional[dict] = None,  # v1.2.5 PR2 §4.3 L1 新增
    ) -> float:
        """Compute suppression level ∈ [0, 1].

        0 = completely open, 1 = completely suppressed.

        v1.2.5 PR2: 加 force_state 可选参数 (L1 输入调制)
        向后兼容: 不传 force_state → 输出跟 v1.2.4 完全一致
        """
        # Personality baseline (Gross & John 2003: neuroticism is strongest predictor)
        baseline = (
            0.35 * personality.get("neuroticism", 0.5)
            + 0.25 * personality.get("agreeableness", 0.5)
            + 0.15 * (1 - personality.get("openness", 0.5))
            + 0.20 * (1 - personality.get("extraversion", 0.5))
            + 0.05 * personality.get("conscientiousness", 0.5)
        )

        # Context modulation
        intimacy_factor = 1 - 0.4 * relationship_intimacy
        authority_factor = context.get("authority_present", 0) * 0.2
        social_audience = context.get("social_audience", 0) * 0.15

        base_suppression = (
            baseline * intimacy_factor + authority_factor + social_audience
            + 0.2 * conscience_pressure
        )

        # L1: 力加权 (社会力 + 个体力 → 压抑↑)
        if force_state is not None:
            force_modifier = (
                1.0
                + 0.3 * force_state.get("social", 0.5)
                + 0.2 * force_state.get("individual", 0.5)
            )
            base_suppression *= force_modifier

        return _clamp(base_suppression, 0, 1)

    def check_rebound(self, suppression_level: float, duration_hours: float) -> float:
        """Wegner 1987: rebound effect when suppression is lifted.

        Longer and stronger suppression -> larger rebound.
        """
        rebound = suppression_level * math.log(1 + duration_hours / 24)
        return _clamp(rebound, 0, 1)

    def compute_cost(self, suppression_level: float, duration_hours: float) -> float:
        """Pennebaker 1997: cumulative physiological cost of suppression.

        Short-term suppression is cheap; long-term cost grows exponentially.
        """
        return suppression_level * (1 + 0.05 * duration_hours ** 1.3)
