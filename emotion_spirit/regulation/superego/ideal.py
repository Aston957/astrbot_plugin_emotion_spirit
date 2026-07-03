"""IdealSelf — 随经验漂移的目标人格。

v1: 从 persona 标签固定推导。
P0: ideal_self 会随 value_reinforcement 动态调整。
"""
from __future__ import annotations

import math
from typing import Any

from ...core.config import SUPEREGO_CONFIG
from ...utils import get_personality_params


class IdealSelf:
    """理想自我 — 随经验漂移的目标人格。"""

    def __init__(self, persona: str, labels: dict[str, str] | None = None) -> None:
        self._persona = persona
        self._labels = labels or {}
        self._ideal = get_personality_params(self._labels) if self._labels else {}
        self._baseline_ideal = dict(self._ideal) if isinstance(self._ideal, dict) else {}
        if isinstance(self._ideal, dict):
            for layer in self._ideal:
                self._baseline_ideal[layer] = dict(self._ideal[layer])
        self._reinforcement: dict[str, dict[str, float]] = {}

    def compute_gap(self, current: dict[str, dict[str, float]]) -> float:
        """当前人格与理想自我的欧氏距离。"""
        total_sq = 0.0
        count = 0
        for layer in ["deep", "surface"]:
            ideal_layer = self._ideal.get(layer, {})
            current_layer = current.get(layer, {})
            for key, ideal_val in ideal_layer.items():
                current_val = current_layer.get(key, ideal_val)
                total_sq += (ideal_val - current_val) ** 2
                count += 1
        if count == 0:
            return 0.0
        return math.sqrt(total_sq / count)

    def get_direction(self, current: dict[str, dict[str, float]]) -> dict[str, float]:
        """返回需要调整的方向。"""
        direction = {}
        for layer in ["deep", "surface"]:
            ideal_layer = self._ideal.get(layer, {})
            current_layer = current.get(layer, {})
            for key, ideal_val in ideal_layer.items():
                current_val = current_layer.get(key, ideal_val)
                direction[f"{layer}.{key}"] = ideal_val - current_val
        return direction

    def update_reinforcement(self, dimension: str, delta: float) -> None:
        """经验强化 → 理想自我漂移。"""
        rate = SUPEREGO_CONFIG["reinforcement_rate"]
        max_shift = SUPEREGO_CONFIG["reinforcement_max"]
        for layer in ["deep", "surface"]:
            if dimension in self._ideal.get(layer, {}):
                if layer not in self._reinforcement:
                    self._reinforcement[layer] = {}
                current_shift = self._reinforcement[layer].get(dimension, 0.0)
                new_shift = max(-max_shift, min(max_shift, current_shift + delta * rate))
                self._reinforcement[layer][dimension] = new_shift

                baseline_val = self._baseline_ideal.get(layer, {}).get(dimension, 0.5)
                self._ideal[layer][dimension] = max(0.0, min(1.0,
                    baseline_val + new_shift))
                break

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona": self._persona,
            "ideal": self._ideal,
            "baseline_ideal": self._baseline_ideal,
            "reinforcement": self._reinforcement,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self._ideal = data.get("ideal", self._ideal)
        saved_baseline = data.get("baseline_ideal", {})
        if saved_baseline:
            self._baseline_ideal = saved_baseline
        elif isinstance(self._ideal, dict):
            self._baseline_ideal = {}
            for layer in self._ideal:
                self._baseline_ideal[layer] = dict(self._ideal[layer])
        self._reinforcement = data.get("reinforcement", {})
