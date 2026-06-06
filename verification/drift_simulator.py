"""12 维漂移模拟器 — 模拟 SylannEngine 持有的人格参数在长期对话中的演变。

v1.7: 12 维 (autonomy_guard 拆分为 relational_autonomy + exploration_openness)

漂移规则:
1. 每轮小漂移: ±0.005~0.03 (由场景和 MBTI+依恋风格约束方向)
2. EMA 回归: 每轮向基线拉回 0.1%~0.5% (深层维度回归力更强)
3. 大事件冲击: 级联/创伤事件可产生一次性大偏移 (±0.05~0.15)
4. Clamp 到 [0, 1]
5. 深层维度变化率为表层的 40% (基于 Roberts & DelVecchio, 2000)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from emotion_spirit.label_mapper import labels_to_personality, _BASELINE


DEEP_DIMS = [
    "expression_drive", "perception_acuity", "boundary_permeability",
    "inner_coherence", "relational_gravity",
]

SURFACE_DIMS = [
    "warmth_bias", "directness", "curiosity",
    "patience", "intimacy_pull",
    # v1.7: autonomy_guard 拆分为 2 维
    "relational_autonomy", "exploration_openness",
]

# 每轮的回归强度 (深层 vs 表层)
# v1.7.1: 0.001→0.005 (5x 增强) — 原 0.001 太弱, 1000 轮后 noise 累计 std=0.158 主导
# 新 0.005: 1000 轮后 baseline retention = exp(-5) ≈ 0.7%, half-life = 138 turn (合理)
DEEP_REGRESSION_RATE = 0.010   # 0.2%/轮 → 1.0%/轮 (5x)
SURFACE_REGRESSION_RATE = 0.005  # 0.1%/轮 → 0.5%/轮 (5x)


class DriftSimulator:
    """模拟 SylannEngine 12 维人格参数的长期漂移 (v1.7: 11→12)。"""

    def __init__(self, initial_labels: dict[str, str]) -> None:
        self._labels = initial_labels
        self._baseline = labels_to_personality(initial_labels)
        self._current = {
            "deep": dict(self._baseline["deep"]),
            "surface": dict(self._baseline["surface"]),
        }
        self._turn = 0

    @property
    def current(self) -> dict[str, dict[str, float]]:
        return {
            "deep": dict(self._current["deep"]),
            "surface": dict(self._current["surface"]),
        }

    @property
    def baseline(self) -> dict[str, dict[str, float]]:
        return {
            "deep": dict(self._baseline["deep"]),
            "surface": dict(self._baseline["surface"]),
        }

    @property
    def turn(self) -> int:
        return self._turn

    def step(
        self,
        scenario_drift: dict[str, float] | None = None,
        is_cascade: bool = False,
        is_trauma: bool = False,
    ) -> dict[str, dict[str, float]]:
        """推进一轮漂移。

        Args:
            scenario_drift: 场景驱动的方向性漂移 (dim → delta)
            is_cascade: 是否级联事件 (产生大偏移)
            is_trauma: 是否创伤事件 (产生大偏移)

        Returns:
            更新后的 personality
        """
        self._turn += 1

        for dim in DEEP_DIMS:
            baseline_val = self._baseline["deep"].get(dim, 0.5)
            current_val = self._current["deep"][dim]
            regression = (baseline_val - current_val) * DEEP_REGRESSION_RATE

            noise = random.gauss(0, 0.003)

            scenario_delta = 0.0
            if scenario_drift and dim in scenario_drift:
                scenario_delta = scenario_drift[dim] * 0.4  # 深层变化率 = 表层的 40%

            event_delta = 0.0
            if is_cascade:
                event_delta = random.gauss(0, 0.04)
            if is_trauma:
                event_delta = random.gauss(0, 0.08)

            self._current["deep"][dim] = max(0.0, min(1.0,
                current_val + regression + noise + scenario_delta + event_delta
            ))

        for dim in SURFACE_DIMS:
            baseline_val = self._baseline["surface"].get(dim, 0.5)
            current_val = self._current["surface"][dim]
            regression = (baseline_val - current_val) * SURFACE_REGRESSION_RATE

            noise = random.gauss(0, 0.005)

            scenario_delta = 0.0
            if scenario_drift and dim in scenario_drift:
                scenario_delta = scenario_drift[dim]

            event_delta = 0.0
            if is_cascade:
                event_delta = random.gauss(0, 0.06)
            if is_trauma:
                event_delta = random.gauss(0, 0.12)

            self._current["surface"][dim] = max(0.0, min(1.0,
                current_val + regression + noise + scenario_delta + event_delta
            ))

        return self.current

    def compute_gap_from_baseline(self) -> float:
        """当前人格与基线的欧氏距离。"""
        total_sq = 0.0
        count = 0
        for layer in ("deep", "surface"):
            for dim in self._baseline[layer]:
                current_val = self._current[layer][dim]
                baseline_val = self._baseline[layer][dim]
                total_sq += (current_val - baseline_val) ** 2
                count += 1
        return math.sqrt(total_sq / count) if count > 0 else 0.0
