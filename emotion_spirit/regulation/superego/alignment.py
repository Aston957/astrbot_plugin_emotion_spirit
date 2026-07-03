"""ValueAlignment — 追踪行为与价值观的对齐关系。

P0 重写: 不再 early-return，每个涉及的价值观都会被记录。
misaligned 路径也计入 _total_count，分数不再虚高。
支持人格区分。
"""
from __future__ import annotations

from collections import deque
from typing import Any

from ...utils import get_value_behaviors


class ValueAlignment:
    """价值对齐追踪 — 记录行为与价值观的关系。"""

    def __init__(self, persona: str) -> None:
        self._persona = persona
        self._action_history: deque[str] = deque(maxlen=200)
        self._aligned_count = 0
        self._misaligned_count = 0
        self._neutral_count = 0
        self._value_aligned: dict[str, int] = {}
        self._value_conflict: dict[str, int] = {}

    def record(self, action: str) -> tuple[list[str], list[str]]:
        """记录一次行为，返回 (conflict_values, aligned_values)。

        不再 early-return，每个涉及的价值观都会被记录。
        """
        self._action_history.append(action)
        value_behaviors = get_value_behaviors()

        conflict_values: list[str] = []
        aligned_values: list[str] = []

        for value_name, mapping in value_behaviors.items():
            if action in mapping.get("aligned", []):
                aligned_values.append(value_name)
                self._aligned_count += 1
                self._value_aligned[value_name] = self._value_aligned.get(value_name, 0) + 1
            elif action in mapping.get("misaligned", []):
                conflict_values.append(value_name)
                self._misaligned_count += 1
                self._value_conflict[value_name] = self._value_conflict.get(value_name, 0) + 1

        if not conflict_values and not aligned_values:
            self._neutral_count += 1

        return conflict_values, aligned_values

    def get_score(self) -> float:
        """对齐分数 [0, 1]。"""
        total = self._aligned_count + self._misaligned_count + self._neutral_count
        if total == 0:
            return 0.5
        return self._aligned_count / total

    def get_trend(self, window: int = 20) -> float:
        """近期趋势 (-1 到 1)。正 = 越来越对齐。"""
        recent = list(self._action_history)[-window:]
        if len(recent) < 5:
            return 0.0

        value_behaviors = get_value_behaviors()
        aligned = 0
        misaligned = 0
        for action in recent:
            for mapping in value_behaviors.values():
                if action in mapping.get("aligned", []):
                    aligned += 1
                    break
                elif action in mapping.get("misaligned", []):
                    misaligned += 1
                    break

        total = aligned + misaligned
        if total == 0:
            return 0.0
        return (aligned / total) * 2 - 1

    def get_value_detail(self, value_name: str) -> dict:
        """获取某个价值观的对齐详情。"""
        aligned = self._value_aligned.get(value_name, 0)
        conflict = self._value_conflict.get(value_name, 0)
        total = aligned + conflict
        return {
            "value": value_name,
            "aligned": aligned,
            "conflict": conflict,
            "total": total,
            "alignment_rate": aligned / total if total > 0 else 0.5,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona": self._persona,
            "aligned_count": self._aligned_count,
            "misaligned_count": self._misaligned_count,
            "neutral_count": self._neutral_count,
            "value_aligned": dict(self._value_aligned),
            "value_conflict": dict(self._value_conflict),
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self._aligned_count = data.get("aligned_count", 0)
        self._misaligned_count = data.get("misaligned_count", 0)
        self._neutral_count = data.get("neutral_count", 0)
        self._value_aligned = data.get("value_aligned", {})
        self._value_conflict = data.get("value_conflict", {})
