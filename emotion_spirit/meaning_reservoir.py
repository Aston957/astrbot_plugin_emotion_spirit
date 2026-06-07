"""意义蓄水池 — 积累高 Φ 时刻的意义，供低 Φ 时的 Mode B 使用。

模拟"即使最近很混乱，之前积累的自我认知仍然支撑着你"。
"""

from __future__ import annotations

import math
import time
from typing import Any


from .registry import register


@register(name="meaning_reservoir", provides=["MeaningReservoir"], depends_on=[])
class MeaningReservoir:
    """Φ 意义蓄水池。"""

    def __init__(self) -> None:
        self.level: float = 0.0           # [0, 1]
        self.decay_rate: float = 0.01     # 每小时衰减
        self._last_tick: float = time.time()

    def accumulate(self, phi: float, emotional_weight: float) -> None:
        """高 Φ + 高情感 = 积累意义。"""
        self.tick()  # 先衰减
        contribution = phi * emotional_weight * 0.1
        self.level = min(1.0, self.level + contribution)

    def draw(self, amount: float) -> float:
        """Mode B 取用意义。返回实际取用量。"""
        available = min(amount, self.level)
        self.level -= available
        return available

    def tick(self) -> None:
        """自然衰减 (按经过时间)。"""
        now = time.time()
        elapsed_hours = (now - self._last_tick) / 3600
        if elapsed_hours > 0:
            self.level *= math.exp(-self.decay_rate * elapsed_hours)
            self._last_tick = now

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": round(self.level, 6),
            "decay_rate": self.decay_rate,
            "last_tick": self._last_tick,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self.level = data.get("level", 0.0)
        self.decay_rate = data.get("decay_rate", 0.01)
        self._last_tick = data.get("last_tick", time.time())
