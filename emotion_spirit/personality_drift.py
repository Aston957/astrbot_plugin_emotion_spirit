"""人格漂移检测 — 追踪 Sylanne personality 11 维的长期趋势。

每 3 天运行 LabelDriftDetector:
  1. 比较 7 天 EMA vs 30 天 EMA
  2. 差异 > drift_threshold → 标记漂移
  3. in_recovery 或 body_criticality > 0.6 → drift_cap × 1.5~2
  4. body_integration 持续下降 → 漂移阈值降低
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .trend_utils import TrendDetector

if TYPE_CHECKING:
    from .surface_consumer import SurfaceConsumer, SemanticSignals
    from .meaning_reservoir import MeaningReservoir


_DEEP_DIMS = [
    "expression_drive", "perception_acuity", "boundary_permeability",
    "inner_coherence", "relational_gravity",
]

_SURFACE_DIMS = [
    "warmth_bias", "directness", "curiosity",
    "patience", "intimacy_pull", "autonomy_guard",
]


class PersonalityDrift:
    """11 维人格漂移检测器。"""

    def __init__(
        self,
        consumer: SurfaceConsumer,
        reservoir: MeaningReservoir,
    ) -> None:
        self._consumer = consumer
        self._reservoir = reservoir
        self._deep_trends: dict[str, TrendDetector] = {
            dim: TrendDetector(alpha_fast=0.039, alpha_slow=0.004) for dim in _DEEP_DIMS
        }
        self._surface_trends: dict[str, TrendDetector] = {
            dim: TrendDetector(alpha_fast=0.039, alpha_slow=0.004) for dim in _SURFACE_DIMS
        }
        self._drift_threshold: float = 0.1
        self._last_signals: SemanticSignals | None = None
        self._integration_trend = TrendDetector(alpha_fast=0.1, alpha_slow=0.01)
        self._drift_history: list[dict[str, Any]] = []

    def update(self, signals: SemanticSignals) -> None:
        """每次 Surface 更新时调用。更新 11 维趋势。"""
        self._last_signals = signals

        for dim in _DEEP_DIMS:
            value = signals.personality_deep.get(dim, 0.5)
            self._deep_trends[dim].update(value)

        for dim in _SURFACE_DIMS:
            value = signals.personality_surface.get(dim, 0.5)
            self._surface_trends[dim].update(value)

        self._integration_trend.update(signals.body_integration)

    def check_drift(self) -> list[dict[str, Any]]:
        """每 3 天运行。返回漂移检测结果。"""
        drifts: list[dict[str, Any]] = []

        # 计算漂移容量
        cap = 0.05
        if self._last_signals:
            if self._last_signals.in_recovery:
                cap *= 2.0
            if self._last_signals.body_criticality > 0.6:
                cap *= 1.5
        if self._reservoir.level < 0.2:
            cap *= 1.3

        # 整合度持续下降 → 降低漂移阈值
        threshold = self._drift_threshold
        if self._integration_trend.slope(window=7) < -0.01:
            threshold *= 0.8

        # 深层漂移
        for dim in _DEEP_DIMS:
            trend = self._deep_trends[dim]
            slope = trend.slope(window=7)
            if abs(slope) > threshold:
                drifts.append({
                    "dimension": dim,
                    "direction": "increasing" if slope > 0 else "decreasing",
                    "slope": round(slope, 6),
                    "cap": round(cap, 6),
                    "source": "deep",
                })

        # 表层漂移 (阈值更低, 速率更快)
        surface_threshold = threshold * 0.7
        for dim in _SURFACE_DIMS:
            trend = self._surface_trends[dim]
            slope = trend.slope(window=7)
            if abs(slope) > surface_threshold:
                drifts.append({
                    "dimension": dim,
                    "direction": "increasing" if slope > 0 else "decreasing",
                    "slope": round(slope, 6),
                    "cap": round(cap * 1.5, 6),  # 表层漂移更快
                    "source": "surface",
                })

        if drifts:
            self._drift_history.append({
                "timestamp": __import__("time").time(),
                "drifts": drifts,
                "threshold": threshold,
                "cap": cap,
            })

        return drifts

    def get_drift_status(self) -> dict[str, Any]:
        """获取当前漂移状态。"""
        return {
            "deep_trends": {dim: t.trend() for dim, t in self._deep_trends.items()},
            "surface_trends": {dim: t.trend() for dim, t in self._surface_trends.items()},
            "integration_slope": self._integration_trend.slope(window=7),
            "reservoir_level": self._reservoir.level,
            "drift_count": len(self._drift_history),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "deep_trends": {dim: t.to_dict() for dim, t in self._deep_trends.items()},
            "surface_trends": {dim: t.to_dict() for dim, t in self._surface_trends.items()},
            "integration_trend": self._integration_trend.to_dict(),
            "drift_threshold": self._drift_threshold,
            "drift_history": self._drift_history[-20:],
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        for dim, d in data.get("deep_trends", {}).items():
            if dim in self._deep_trends:
                self._deep_trends[dim].from_dict(d)
        for dim, d in data.get("surface_trends", {}).items():
            if dim in self._surface_trends:
                self._surface_trends[dim].from_dict(d)
        self._integration_trend.from_dict(data.get("integration_trend", {}))
        self._drift_threshold = data.get("drift_threshold", 0.1)
        self._drift_history = data.get("drift_history", [])
