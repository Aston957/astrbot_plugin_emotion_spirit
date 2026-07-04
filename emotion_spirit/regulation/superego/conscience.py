"""ConscienceTracker — 追踪良心压力事件（增压+减压）。

P0 重写: 新增减压路径 (alignment, repair)，guard/cascade 降权。
Phase 4 C1: 滑动窗口 P95 分位归一化 (B2 算法)。
"""
from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ...core.config import SUPEREGO_CONFIG
from ...layer import global_only

# Phase 4 C1: ConscienceTracker 滑动窗口 P95 归一化 (B2 算法)
_DEFAULT_WINDOW = 200
_DEFAULT_QUANTILE = 0.95
_COLD_START_THRESHOLD = 10
_PRESSURE_WINDOW_ENV = "EMOTION_SPIRIT_PRESSURE_WINDOW"


def _get_window_size() -> int:
    """读 env var 覆盖窗口大小, 默认 200。"""
    return int(os.environ.get(_PRESSURE_WINDOW_ENV, _DEFAULT_WINDOW))


@dataclass
class GuiltEvent:
    """单个良心事件。"""
    trigger: str
    severity: float
    timestamp: float = field(default_factory=time.time)
    reason: str = ""
    tension_type: str = ""
    conflict_values: list = field(default_factory=list)
    conscience_impact: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger,
            "severity": round(self.severity, 6),
            "timestamp": self.timestamp,
            "reason": self.reason,
            "tension_type": self.tension_type,
            "conflict_values": self.conflict_values,
            "conscience_impact": round(self.conscience_impact, 6),
        }


@dataclass
class AlignmentEvent:
    """价值对齐事件 — 良心减压。"""
    value_name: str
    action: str
    timestamp: float = field(default_factory=time.time)
    relief: float = 0.0


class ConscienceTracker:
    """良心追踪 — 价值冲突增压 + 价值对齐减压。"""

    def __init__(self) -> None:
        self.guilt_events: list[GuiltEvent] = []
        self.alignment_events: list[AlignmentEvent] = []
        self._last_collapse_count: int = 0
        # Phase 4 C1: 累加器是真相源, raw 真相 ℝ⁺ 无上限
        self._raw_pressure: float = 0.0
        # 滑动窗口 P95 分位归一化 (B2 算法)
        self._window: deque[float] = deque(maxlen=_get_window_size())
        self._window_quantile: float = 0.0
        self._pressure_decay_rate: float = SUPEREGO_CONFIG["pressure_decay_rate_per_hour"]

    # ═══ 增压路径 ═══

    def record_value_conflict(
        self,
        resistance: float,
        conflict_values: list[str],
        tension_type: str,
        behavioral_shift: float,
        conscience_impact: float,
    ) -> GuiltEvent:
        """价值冲突 → 良心增压。"""
        event = GuiltEvent(
            trigger="value_conflict",
            severity=round(abs(conscience_impact), 4),
            tension_type=tension_type,
            conflict_values=list(conflict_values),
            conscience_impact=conscience_impact,
            reason=f"values {conflict_values} in conflict, tension={tension_type}",
        )
        self.guilt_events.append(event)
        self._raw_pressure += abs(conscience_impact)  # 累加器是真相源, 无上限
        self._window.append(abs(conscience_impact))  # Bug-G v1.2.11: 增量语义 (P95 = 单次事件强度高分位)
        self._window_quantile = 0.0  # 失效缓存
        return event

    def record_guard_reflex(self, risk_score: float, reason: str) -> GuiltEvent:
        """本我反射弧触发 (guard.allowed=False)。

        这不是良心！是本能防御。severity 降低到 30%。
        """
        mult = SUPEREGO_CONFIG["guard_reflex_conscience_multiplier"]
        severity = risk_score * mult
        event = GuiltEvent(
            trigger="guard_reflex",
            severity=round(severity, 4),
            reason=f"instinctive boundary: {reason}",
            tension_type="doubt",
            conscience_impact=severity,
        )
        self.guilt_events.append(event)
        self._raw_pressure += severity
        self._window.append(severity)  # Bug-G v1.2.11: 增量
        self._window_quantile = 0.0
        return event

    def record_cascade(self, intensity: float) -> GuiltEvent:
        """级联事件 — 情感崩溃，不是良心。severity 降低到 50%。"""
        mult = SUPEREGO_CONFIG["cascade_conscience_multiplier"]
        severity = min(1.0, intensity * mult)
        event = GuiltEvent(
            trigger="cascade",
            severity=severity,
            tension_type="shame",
            conscience_impact=severity * 0.5,
            reason="emotional cascade",
        )
        self.guilt_events.append(event)
        self._raw_pressure += severity * 0.5
        self._window.append(severity * 0.5)  # Bug-G v1.2.11: 增量
        self._window_quantile = 0.0
        return event

    def record_collapse(self, collapse_count: int) -> GuiltEvent | None:
        """人格坍缩。"""
        if collapse_count > self._last_collapse_count:
            self._last_collapse_count = collapse_count
            event = GuiltEvent(
                trigger="personality_collapse",
                severity=1.0,
                tension_type="shame",
                conscience_impact=0.8,
                reason="personality collapse detected",
            )
            self.guilt_events.append(event)
            self._raw_pressure += 0.8
            self._window.append(0.8)  # Bug-G v1.2.11: 增量
            self._window_quantile = 0.0
            return event
        return None

    # ═══ 减压路径 ═══

    def record_alignment(self, value_name: str, action: str) -> AlignmentEvent:
        """价值对齐 → 良心减压。做了符合价值观的事。"""
        relief = SUPEREGO_CONFIG["alignment_base_relief"]
        event = AlignmentEvent(
            value_name=value_name,
            action=action,
            relief=relief,
        )
        self.alignment_events.append(event)
        self._raw_pressure = max(0.0, self._raw_pressure - relief)
        # Bug-G v1.2.11: record_alignment (缓解) 不入 _window — P95 应反映事件强度而非缓解后水平
        self._window_quantile = 0.0
        return event

    def record_repair(self, repair_type: str = "simple") -> None:
        """修复行为 → 良心大幅减压。"""
        relief_map = SUPEREGO_CONFIG["repair_relief"]
        relief = relief_map.get(repair_type, relief_map["simple"])
        self._raw_pressure = max(0.0, self._raw_pressure - relief)
        # Bug-G v1.2.11: record_repair (缓解) 不入 _window — P95 应反映事件强度而非缓解后水平
        self._window_quantile = 0.0

    # ═══ 向后兼容 ═══

    def record_guard_rejected(self, risk_score: float, reason: str) -> GuiltEvent:
        """向后兼容: 转发到 record_guard_reflex。"""
        return self.record_guard_reflex(risk_score, reason)

    # ═══ 读取 ═══

    def get_pressure(self) -> float:
        """良心压力 [0, 1] (P95 分位归一化)。

        累加器 (_raw_pressure) 保留 raw 真相 (ℝ⁺, 无上限)。
        消费时按滑动窗口 P95 分位归一化。
        冷启动期 (< 10 帧) 返回 raw 不归一化 (degraded mode)。
        极低压力场景 (P95 < 0.01) 返回 0.0 避免除零。

        Returns:
            ∈ [0, 1] (ForceDynamics 契约保持)
        """
        if len(self._window) < _COLD_START_THRESHOLD:
            return self._raw_pressure
        if self._window_quantile == 0.0:
            sorted_window = sorted(self._window)
            p95_idx = int(len(sorted_window) * _DEFAULT_QUANTILE)
            self._window_quantile = sorted_window[p95_idx]
        if self._window_quantile < 0.01:
            return 0.0
        return min(1.0, self._raw_pressure / self._window_quantile)

    def tick_pressure(self, hours_elapsed: float) -> None:
        """自然衰减 (每小时调用)。

        Bug-G v1.2.11: 不再 append self._raw_pressure 到 _window — 衰减 tick 不是事件强度,
        append post-decay 累计值会让 P95 = 当前值, 永饱和. 只失效缓存即可.
        """
        ratio = (1.0 - self._pressure_decay_rate) ** hours_elapsed
        self._raw_pressure *= ratio
        self._window_quantile = 0.0  # 失效缓存, 等下次 get_pressure 重算

    def get_recent(self, hours: float = 24, event_type: str | None = None) -> list:
        """获取近期事件。可选按类型筛选。"""
        cutoff = time.time() - hours * 3600
        if event_type:
            return [e for e in self.guilt_events
                    if e.timestamp > cutoff and e.trigger == event_type]
        return [e for e in self.guilt_events if e.timestamp > cutoff]

    def get_recent_alignments(self, hours: float = 24) -> list[AlignmentEvent]:
        """获取近期对齐事件。"""
        cutoff = time.time() - hours * 3600
        return [e for e in self.alignment_events if e.timestamp > cutoff]

    @global_only
    def get_pressure_breakdown(self) -> dict:
        """良心压力分解 (供 prompt_injector)。"""
        recent_guilt = self.get_recent(24)
        recent_align = self.get_recent_alignments(24)

        by_type: dict[str, float] = {}
        for e in recent_guilt:
            t = e.tension_type or e.trigger
            by_type[t] = by_type.get(t, 0.0) + e.severity

        total_alignment = sum(e.relief for e in recent_align)

        return {
            "pressure": self.get_pressure(),  # P95 归一化 (Phase 4 C1)
            "raw_pressure": self._raw_pressure,  # 新增: raw 真相
            "by_type": by_type,
            "alignment_relief_24h": round(total_alignment, 4),
            "dominant_tension": max(by_type, key=by_type.get) if by_type else None,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "guilt_events": [e.to_dict() for e in self.guilt_events[-50:]],
            "alignment_events": [{
                "value_name": e.value_name,
                "action": e.action,
                "timestamp": e.timestamp,
                "relief": e.relief,
            } for e in self.alignment_events[-30:]],
            "pressure": self._raw_pressure,
            "raw_pressure": self._raw_pressure,  # Phase 4 C1: 双写兼容
            "last_collapse_count": self._last_collapse_count,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        events_raw = data.get("guilt_events", [])
        self.guilt_events = []
        for e in events_raw:
            if isinstance(e, dict):
                self.guilt_events.append(GuiltEvent(
                    trigger=e.get("trigger", "unknown"),
                    severity=e.get("severity", 0.0),
                    timestamp=e.get("timestamp", time.time()),
                    reason=e.get("reason", ""),
                    tension_type=e.get("tension_type", ""),
                    conflict_values=e.get("conflict_values", []),
                    conscience_impact=e.get("conscience_impact",
                                            e.get("severity", 0.0)),
                ))
        self.alignment_events = []
        for e in data.get("alignment_events", []):
            self.alignment_events.append(AlignmentEvent(
                value_name=e.get("value_name", ""),
                action=e.get("action", ""),
                timestamp=e.get("timestamp", time.time()),
                relief=e.get("relief", 0.03),
            ))
        self._raw_pressure = data.get("pressure", 0.0)  # 兼容旧 schema
        if "raw_pressure" in data:
            self._raw_pressure = data["raw_pressure"]
        self._last_collapse_count = data.get("last_collapse_count", 0)
