"""预测性预警 — 从 body state + 共振场信号 + 超我数据检测早期预警。

13 信号: 7 body + 3 共振场 + 3 缓冲池
5 超我信号: conscience/alignment/ideal (可选，需传入引用)
3+ 触发 → warning, 5+ → critical
"""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

from .config import SENTINEL_CONFIG, SAFETY_CONFIG
from .trend_utils import TrendDetector

if TYPE_CHECKING:
    from .surface_consumer import SurfaceConsumer, SemanticSignals
    from .buffer_signals import BufferSignals
    from .meaning_reservoir import MeaningReservoir
    from .superego import ConscienceTracker, ValueAlignment, IdealSelf


from .registry import register


@register(
    name="predictive_sentinel",
    provides=["PredictiveSentinel"],
    depends_on=[
        "surface_consumer", "buffer_signals", "meaning_reservoir",
        "superego.alignment", "superego.conscience", "superego.ideal",
    ],
    param_wire={
        "buffer_signals": "signals",
        "meaning_reservoir": "reservoir",
        "surface_consumer": "consumer",
    },
)
class PredictiveSentinel:
    """信号预警系统。

    原始 13 信号 (body/共振场/缓冲池) + 可选 5 超我信号。
    超我信号只读取 conscience/alignment/ideal 数据，不修改其状态。
    """

    def __init__(
        self,
        consumer: SurfaceConsumer,
        signals: BufferSignals,
        reservoir: MeaningReservoir,
        conscience: ConscienceTracker | None = None,
        alignment: ValueAlignment | None = None,
        ideal: IdealSelf | None = None,
    ) -> None:
        self._consumer = consumer
        self._buffer_signals = signals
        self._reservoir = reservoir
        self._conscience = conscience
        self._alignment = alignment
        self._ideal = ideal

        # 趋势检测器
        self._trends: dict[str, TrendDetector] = {
            "strain": TrendDetector(),
            "damage": TrendDetector(),
            "recovery": TrendDetector(),
            "intimacy": TrendDetector(),
            "integration": TrendDetector(),
            "criticality": TrendDetector(),
            "sync": TrendDetector(),
            "phi": TrendDetector(),
            "chi": TrendDetector(),
        }
        self._cascade_count_7d: int = 0
        self._last_cascade_reset: float = time.time()
        self._check_history: list[dict[str, Any]] = []

    def update(self, signals: SemanticSignals) -> None:
        """每次 Surface 更新时调用。"""
        self._trends["strain"].update(signals.rhythm_strain)
        self._trends["damage"].update(signals.damage_accumulated)
        self._trends["recovery"].update(signals.damage_recovery)
        self._trends["integration"].update(signals.body_integration)
        self._trends["criticality"].update(signals.body_criticality)
        self._trends["sync"].update(signals.sync_order_smoothed)
        self._trends["phi"].update(signals.phi_smoothed)
        self._trends["chi"].update(signals.chi_smoothed)

        if signals.cascade_active:
            self._cascade_count_7d += 1

        # 每 7 天重置 cascade 计数
        now = time.time()
        if now - self._last_cascade_reset > 7 * 86400:
            self._cascade_count_7d = 0
            self._last_cascade_reset = now

    def check(self) -> dict[str, Any]:
        """运行预警检查。返回预警结果。"""
        triggered: list[str] = []

        # 1. strain_accelerating
        t = self._trends["strain"]
        if t.slope(window=7) > 0 and t.is_monotonic(7, "increasing"):
            triggered.append("strain_accelerating")

        # 2. damage_accelerating
        t = self._trends["damage"]
        if t.slope(window=7) > 0 and t.is_monotonic(7, "increasing"):
            triggered.append("damage_accelerating")

        # 3. cascade_frequency
        if self._cascade_count_7d > 3:
            triggered.append("cascade_frequency")

        # 4. recovery_decelerating
        t = self._trends["recovery"]
        if t.slope(window=7) < 0:
            triggered.append("recovery_decelerating")

        # 5. intimacy_declining
        t = self._trends["intimacy"]
        if t.slope(window=14) < 0 and t.is_monotonic(14, "decreasing"):
            triggered.append("intimacy_declining")

        # 6. integration_declining
        t = self._trends["integration"]
        if t.slope(window=7) < 0 and t.is_monotonic(7, "decreasing"):
            triggered.append("integration_declining")

        # 7. criticality_rising
        t = self._trends["criticality"]
        if t.slope(window=7) > 0 and t.is_monotonic(7, "increasing"):
            triggered.append("criticality_rising")

        # 8. sync_declining
        t = self._trends["sync"]
        if t.slope(window=7) < 0 and t.is_monotonic(7, "decreasing"):
            triggered.append("sync_declining")

        # 9. phi_declining
        t = self._trends["phi"]
        if t.slope(window=7) < 0 and t.is_monotonic(7, "decreasing"):
            triggered.append("phi_declining")

        # 10. chi_rising
        t = self._trends["chi"]
        if t.slope(window=7) > 0 and t.is_monotonic(7, "increasing"):
            triggered.append("chi_rising")

        # 11. buffer_stress
        if self._buffer_signals.buffer_temperature() > 0.7:
            triggered.append("buffer_stress")

        # 12. integration_failure
        if self._buffer_signals.confirmation_velocity() < 0.3:
            triggered.append("integration_failure")

        # 13. echo_persistence
        if any(e["count"] >= 5 for e in self._buffer_signals.echo_patterns()):
            triggered.append("echo_persistence")

        # ═══ 超我信号 (可选，只读) ═══
        if self._conscience is not None and SAFETY_CONFIG.get("enabled", True):
            # 14. conscience_pressure_rising
            if self._conscience.get_pressure() > SAFETY_CONFIG["pressure_rise_threshold"]:
                triggered.append("conscience_pressure_rising")

            # 15. value_conflict_clustering
            window = SAFETY_CONFIG["conflict_cluster_window_hours"]
            recent_conflicts = self._conscience.get_recent(
                hours=window, event_type="value_conflict",
            )
            if len(recent_conflicts) >= SAFETY_CONFIG["conflict_cluster_count"]:
                triggered.append("value_conflict_clustering")

            # 16. guard_reflex_frequency
            guard_window = SAFETY_CONFIG["guard_reflex_window_hours"]
            recent_guards = self._conscience.get_recent(
                hours=guard_window, event_type="guard_reflex",
            )
            if len(recent_guards) >= SAFETY_CONFIG["guard_reflex_count"]:
                triggered.append("guard_reflex_frequency")

        if self._alignment is not None and SAFETY_CONFIG.get("enabled", True):
            # 17. alignment_declining
            trend = self._alignment.get_trend(20)
            if trend < SAFETY_CONFIG["alignment_decline_threshold"]:
                triggered.append("alignment_declining")

        if self._ideal is not None and SAFETY_CONFIG.get("enabled", True):
            # 18. ideal_self_drift
            current_personality = self._consumer.consume({}).personality_deep
            if current_personality:
                gap = self._ideal.compute_gap({"deep": current_personality, "surface": {}})
                if gap > SAFETY_CONFIG["ideal_drift_threshold"]:
                    triggered.append("ideal_self_drift")

        # 判定级别
        warning_threshold = SENTINEL_CONFIG["warning_threshold"]
        critical_threshold = SENTINEL_CONFIG["critical_threshold"]

        if len(triggered) >= critical_threshold:
            level = "critical"
        elif len(triggered) >= warning_threshold:
            level = "warning"
        else:
            level = "normal"

        result = {
            "level": level,
            "triggered_count": len(triggered),
            "triggered_signals": triggered,
            "timestamp": time.time(),
        }

        self._check_history.append(result)
        if len(self._check_history) > 20:
            self._check_history = self._check_history[-20:]

        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "trends": {k: v.to_dict() for k, v in self._trends.items()},
            "cascade_count_7d": self._cascade_count_7d,
            "last_cascade_reset": self._last_cascade_reset,
            "check_history": self._check_history[-10:],
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        for k, v in data.get("trends", {}).items():
            if k in self._trends:
                self._trends[k].from_dict(v)
        self._cascade_count_7d = data.get("cascade_count_7d", 0)
        self._last_cascade_reset = data.get("last_cascade_reset", time.time())
        self._check_history = data.get("check_history", [])
