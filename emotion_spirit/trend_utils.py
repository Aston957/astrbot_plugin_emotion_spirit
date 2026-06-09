"""EMA 趋势工具 — 供 drift / sentinel / buffer_signals 共享使用。"""

from __future__ import annotations

from typing import Any



__all__ = [
    "EMASmoother",
    "TrendDetector",
]

class EMASmoother:
    """单 EMA 平滑器。"""

    def __init__(self, alpha: float) -> None:
        self._alpha = alpha
        self._value: float = 0.0
        self._initialized = False

    def update(self, raw: float) -> float:
        """更新并返回平滑后的值。"""
        if not self._initialized:
            self._value = raw
            self._initialized = True
        else:
            self._value = self._value * (1 - self._alpha) + raw * self._alpha
        return self._value

    @property
    def value(self) -> float:
        return self._value

    def to_dict(self) -> dict[str, Any]:
        return {"alpha": self._alpha, "value": self._value, "initialized": self._initialized}

    def from_dict(self, data: dict[str, Any]) -> None:
        self._alpha = data.get("alpha", self._alpha)
        self._value = data.get("value", 0.0)
        self._initialized = data.get("initialized", False)


class TrendDetector:
    """双 EMA 趋势检测器 (快/慢)。"""

    def __init__(self, alpha_fast: float = 0.1, alpha_slow: float = 0.01) -> None:
        self._ema_fast: float | None = None
        self._ema_slow: float | None = None
        self._alpha_fast = alpha_fast
        self._alpha_slow = alpha_slow
        self._history: list[float] = []

    def update(self, value: float) -> None:
        """更新快/慢 EMA。"""
        if self._ema_fast is None:
            self._ema_fast = value
            self._ema_slow = value
        else:
            self._ema_fast = self._ema_fast * (1 - self._alpha_fast) + value * self._alpha_fast
            self._ema_slow = self._ema_slow * (1 - self._alpha_slow) + value * self._alpha_slow
        self._history.append(value)
        if len(self._history) > 60:
            self._history = self._history[-60:]

    def trend(self) -> float:
        """趋势方向: 正=上升, 负=下降, 0=稳定。"""
        if self._ema_fast is None or self._ema_slow is None:
            return 0.0
        return self._ema_fast - self._ema_slow

    def slope(self, window: int = 7) -> float:
        """近 N 个数据点的斜率 (简单线性回归)。"""
        if len(self._history) < window:
            return 0.0
        recent = self._history[-window:]
        n = len(recent)
        x_mean = (n - 1) / 2
        y_mean = sum(recent) / n
        num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(recent))
        den = sum((i - x_mean) ** 2 for i in range(n))
        if den == 0:
            return 0.0
        return num / den

    def is_monotonic(self, window: int = 7, direction: str = "either") -> bool:
        """检查近 N 个数据点是否单调。"""
        if len(self._history) < window:
            return False
        recent = self._history[-window:]
        if direction == "increasing":
            return all(recent[i] <= recent[i + 1] for i in range(len(recent) - 1))
        elif direction == "decreasing":
            return all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1))
        else:
            inc = all(recent[i] <= recent[i + 1] for i in range(len(recent) - 1))
            dec = all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1))
            return inc or dec

    def to_dict(self) -> dict[str, Any]:
        return {
            "alpha_fast": self._alpha_fast,
            "alpha_slow": self._alpha_slow,
            "ema_fast": self._ema_fast,
            "ema_slow": self._ema_slow,
            "history": self._history[-30:],
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self._alpha_fast = data.get("alpha_fast", self._alpha_fast)
        self._alpha_slow = data.get("alpha_slow", self._alpha_slow)
        self._ema_fast = data.get("ema_fast")
        self._ema_slow = data.get("ema_slow")
        self._history = data.get("history", [])


from .registry import register


@register(name="trend_utils", provides=[], depends_on=[])
class _ModuleMarker:
    """纯函数模块标记 (供 ModuleRegistry 元数据用)。"""
    pass
