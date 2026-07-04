"""ConscienceTracker — 追踪良心压力事件(双通道: 急性瞬时 + 慢性累计)。

v1.3.0 rc.2 (handbook §1.7 轴心驱动重写):
- 双通道: 急性压力(_acute, 分钟级衰减) + 慢性压力(_chronic, 小时级衰减)
- 人格耦合: set_personality(personality) 从 13维 personality 算 6 个轴心参数
  (KB conscience_params.json). 不硬编码 SUPEREGO_CONFIG.
- suppression_level: record_* 动态调制慢性积累速度 (压抑起作用时积累慢)
- lazy decay: get_pressure 时按时间差衰减 (避免 tick loop 死了就不衰)
- get_pressure: = min(1.0, acute + chronic)  (Bug-G 治本: 删 P95 饱和公式)
- reset: 补 §1.5 生命周期 (test_lifecycle_pairs 守护)

历史:
- v1.2.10: _raw_pressure + P95 公式 (Bug-G 根因: 公式饱和 1.0)
- v1.2.11 test2: _window 增量语义 + _decay_tick_loop 接线 (半修)
- v1.3.0 rc.2: 治本 (本文件)
"""
from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ...core.config import SUPEREGO_CONFIG
from ...layer import global_only

# 滑动窗口保留供 get_pressure_breakdown 诊断 (不用于归一化, 治 Bug-G)
_DEFAULT_WINDOW = 200
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
    """良心追踪 — 价值冲突增压 + 价值对齐减压 (v1.3.0 rc.2: 双通道 + 人格耦合).

    §1.7 轴心驱动: 衰减率/阈值/倍率从 13维 personality 算 (set_personality),
    不硬编码 SUPEREGO_CONFIG. 双通道: _acute (瞬时, 快衰减) + _chronic (累计, 慢衰减).
    suppression_level 动态调制慢性积累速度.
    """

    def __init__(self) -> None:
        self.guilt_events: list[GuiltEvent] = []
        self.alignment_events: list[AlignmentEvent] = []
        self._last_collapse_count: int = 0
        # v1.3.0 rc.2: 双通道 (急性瞬时 + 慢性累计)
        self._acute_pressure: float = 0.0
        self._chronic_pressure: float = 0.0
        self._last_tick_time: float = time.time()  # lazy decay 用
        # 人格参数 (set_personality 覆盖; 默认值 = SUPEREGO_CONFIG 旧值, 向后兼容)
        self._acute_decay_rate_per_min: float = 0.12
        self._chronic_decay_rate_per_hour: float = SUPEREGO_CONFIG["pressure_decay_rate_per_hour"]
        self._collapse_threshold: float = 0.75
        self._acute_multiplier: float = 1.0
        self._chronic_multiplier: float = 0.30
        self._suppression_efficiency: float = 0.50
        # _window 保留诊断 (get_pressure_breakdown 用, 不用于归一化)
        self._window: deque[float] = deque(maxlen=_get_window_size())

    # ═══ §1.7 轴心耦合 ═══

    def set_personality(self, personality: dict[str, float]) -> None:
        """§1.7 轴心耦合: 从 13维 personality 算轴心参数.

        调 compute_conscience_params_from_personality 覆盖 6 个轴心参数:
        acute_decay_rate_per_min / chronic_decay_rate_per_hour / collapse_threshold /
        acute_multiplier / chronic_multiplier / suppression_efficiency.

        Args:
            personality: 13维 personality dict (warmth_bias/patience/... etc).
                         缺维度用 0.5 中性兜底 (compute 函数内部处理).
        """
        from ...utils.persona_profiles import compute_conscience_params_from_personality
        params = compute_conscience_params_from_personality(personality)
        self._acute_decay_rate_per_min = params["acute_decay_rate_per_min"]
        self._chronic_decay_rate_per_hour = params["chronic_decay_rate_per_hour"]
        self._collapse_threshold = params["collapse_threshold"]
        self._acute_multiplier = params["acute_multiplier"]
        self._chronic_multiplier = params["chronic_multiplier"]
        self._suppression_efficiency = params["suppression_efficiency"]

    # ═══ 增压路径 (双通道 + suppression 调制) ═══

    def record_value_conflict(
        self,
        resistance: float,
        conflict_values: list[str],
        tension_type: str,
        behavioral_shift: float,
        conscience_impact: float,
        suppression_level: float = 0.0,  # v1.3.0 rc.2: 动态调制慢性积累
    ) -> GuiltEvent:
        """价值冲突 → 良心增压 (急性 + 慢性双通道).

        急性: += impact * acute_multiplier (大, 快衰减)
        慢性: += impact * chronic_multiplier * (1 - suppression_level * suppression_efficiency)
               (压抑起作用时积累慢)
        """
        impact = abs(conscience_impact)
        acute_gain = impact * self._acute_multiplier
        chronic_gain = impact * self._chronic_multiplier * (1.0 - suppression_level * self._suppression_efficiency)
        self._acute_pressure += acute_gain
        self._chronic_pressure += max(0.0, chronic_gain)
        self._window.append(impact)  # 诊断: 单次增量

        event = GuiltEvent(
            trigger="value_conflict",
            severity=round(impact, 4),
            tension_type=tension_type,
            conflict_values=list(conflict_values),
            conscience_impact=conscience_impact,
            reason=f"values {conflict_values} in conflict, tension={tension_type}",
        )
        self.guilt_events.append(event)
        return event

    def record_guard_reflex(
        self,
        risk_score: float,
        reason: str,
        suppression_level: float = 0.0,
    ) -> GuiltEvent:
        """本我反射弧触发 (guard.allowed=False).

        这不是良心! 是本能防御. severity 降低到 30%.
        v1.3.0 rc.2: 双通道 + suppression 调制.
        """
        mult = SUPEREGO_CONFIG["guard_reflex_conscience_multiplier"]
        severity = risk_score * mult
        impact = severity
        acute_gain = impact * self._acute_multiplier
        chronic_gain = impact * self._chronic_multiplier * (1.0 - suppression_level * self._suppression_efficiency)
        self._acute_pressure += acute_gain
        self._chronic_pressure += max(0.0, chronic_gain)
        self._window.append(severity)  # 诊断

        event = GuiltEvent(
            trigger="guard_reflex",
            severity=round(severity, 4),
            reason=f"instinctive boundary: {reason}",
            tension_type="doubt",
            conscience_impact=severity,
        )
        self.guilt_events.append(event)
        return event

    def record_cascade(
        self,
        intensity: float,
        suppression_level: float = 0.0,
    ) -> GuiltEvent:
        """级联事件 — 情感崩溃, 不是良心. severity 降低到 50%.

        v1.3.0 rc.2: 双通道 + suppression 调制.
        """
        mult = SUPEREGO_CONFIG["cascade_conscience_multiplier"]
        severity = min(1.0, intensity * mult)
        impact = severity * 0.5
        acute_gain = impact * self._acute_multiplier
        chronic_gain = impact * self._chronic_multiplier * (1.0 - suppression_level * self._suppression_efficiency)
        self._acute_pressure += acute_gain
        self._chronic_pressure += max(0.0, chronic_gain)
        self._window.append(impact)  # 诊断

        event = GuiltEvent(
            trigger="cascade",
            severity=severity,
            tension_type="shame",
            conscience_impact=impact,
            reason="emotional cascade",
        )
        self.guilt_events.append(event)
        return event

    def record_collapse(self, collapse_count: int) -> GuiltEvent | None:
        """人格坍缩. 双通道 (无 suppression 调制 — 坍缩瞬时全冲击)."""
        if collapse_count > self._last_collapse_count:
            self._last_collapse_count = collapse_count
            impact = 0.8
            acute_gain = impact * self._acute_multiplier
            chronic_gain = impact * self._chronic_multiplier
            self._acute_pressure += acute_gain
            self._chronic_pressure += chronic_gain
            self._window.append(impact)  # 诊断

            event = GuiltEvent(
                trigger="personality_collapse",
                severity=1.0,
                tension_type="shame",
                conscience_impact=impact,
                reason="personality collapse detected",
            )
            self.guilt_events.append(event)
            return event
        return None

    # ═══ 减压路径 (双通道) ═══

    def record_alignment(
        self,
        value_name: str,
        action: str,
        suppression_level: float = 0.0,  # 占位, 减压不受 suppression 调制
    ) -> AlignmentEvent:
        """价值对齐 → 良心减压 (急性优先 0.7, 慢性 0.3). 做了符合价值观的事。"""
        relief = SUPEREGO_CONFIG["alignment_base_relief"]
        acute_relief = relief * 0.7
        chronic_relief = relief * 0.3
        self._acute_pressure = max(0.0, self._acute_pressure - acute_relief)
        self._chronic_pressure = max(0.0, self._chronic_pressure - chronic_relief)

        event = AlignmentEvent(
            value_name=value_name,
            action=action,
            relief=relief,
        )
        self.alignment_events.append(event)
        return event

    def record_repair(
        self,
        repair_type: str = "simple",
        suppression_level: float = 0.0,  # 占位, 减压不受 suppression 调制
    ) -> None:
        """修复行为 → 良心大幅减压 (双通道, 急性优先)."""
        relief_map = SUPEREGO_CONFIG["repair_relief"]
        relief = relief_map.get(repair_type, relief_map["simple"])
        acute_relief = relief * 0.7
        chronic_relief = relief * 0.3
        self._acute_pressure = max(0.0, self._acute_pressure - acute_relief)
        self._chronic_pressure = max(0.0, self._chronic_pressure - chronic_relief)

    # ═══ 向后兼容 ═══

    def record_guard_rejected(
        self,
        risk_score: float,
        reason: str,
        suppression_level: float = 0.0,
    ) -> GuiltEvent:
        """向后兼容: 转发到 record_guard_reflex."""
        return self.record_guard_reflex(risk_score, reason, suppression_level)

    # ═══ 读取 ═══

    def _apply_lazy_decay(self) -> None:
        """按时间差衰减双通道 (get_pressure 时调, 避免不调时不衰).

        急性按分钟衰减, 慢性按小时衰减. 更新 _last_tick_time 防重复.
        """
        now = time.time()
        hours = (now - self._last_tick_time) / 3600.0
        if hours <= 0:
            return
        mins = hours * 60
        self._acute_pressure *= (1.0 - self._acute_decay_rate_per_min) ** mins
        self._chronic_pressure *= (1.0 - self._chronic_decay_rate_per_hour) ** hours
        self._last_tick_time = now

    def get_pressure(self) -> float:
        """良心压力 [0, 1] = 急性 + 慢性 (lazy decay 按时间差衰减, 不饱和).

        v1.3.0 rc.2: Bug-G 治本. 旧 P95 公式删除.

        Returns:
            ∈ [0, 1] (ForceDynamics 契约保持)
        """
        self._apply_lazy_decay()
        return min(1.0, self._acute_pressure + self._chronic_pressure)

    def tick_pressure(self, hours_elapsed: float) -> None:
        """自然衰减 (hourly, _decay_tick_loop 调). 双通道.

        Bug-G v1.2.11: 不再 append self._raw_pressure 到 _window (Bug-G 根因).
        v1.3.0 rc.2: 双通道 + 同步 _last_tick_time (避免 lazy decay 重复衰).
        """
        mins = hours_elapsed * 60
        self._acute_pressure *= (1.0 - self._acute_decay_rate_per_min) ** mins
        self._chronic_pressure *= (1.0 - self._chronic_decay_rate_per_hour) ** hours_elapsed
        # _last_tick_time 同步 (避免 lazy decay 重复衰)
        self._last_tick_time = time.time()

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
        """良心压力分解 (供 prompt_injector). v1.3.0 rc.2: 双通道字段."""
        self._apply_lazy_decay()
        recent_guilt = self.get_recent(24)
        recent_align = self.get_recent_alignments(24)

        by_type: dict[str, float] = {}
        for e in recent_guilt:
            t = e.tension_type or e.trigger
            by_type[t] = by_type.get(t, 0.0) + e.severity

        total_alignment = sum(e.relief for e in recent_align)

        return {
            "acute_pressure": round(self._acute_pressure, 6),
            "chronic_pressure": round(self._chronic_pressure, 6),
            "total": min(1.0, self._acute_pressure + self._chronic_pressure),
            "collapse_threshold": self._collapse_threshold,
            "acute_decay_rate_per_min": self._acute_decay_rate_per_min,
            "chronic_decay_rate_per_hour": self._chronic_decay_rate_per_hour,
            "raw_window_recent": list(self._window)[-10:],  # 诊断最近 10 帧
            "pressure": min(1.0, self._acute_pressure + self._chronic_pressure),  # 兼容旧 key
            "by_type": by_type,
            "alignment_relief_24h": round(total_alignment, 4),
            "dominant_tension": max(by_type, key=by_type.get) if by_type else None,
        }

    # ═══ §1.5 生命周期 (to_dict / from_dict / reset) ═══

    def to_dict(self) -> dict[str, Any]:
        """序列化. v1.3.0 rc.2: 双通道字段 + _last_tick_time."""
        self._apply_lazy_decay()
        return {
            "acute_pressure": self._acute_pressure,
            "chronic_pressure": self._chronic_pressure,
            # 兼容旧 schema key (raw_pressure)
            "raw_pressure": self._acute_pressure + self._chronic_pressure,
            "pressure": self._acute_pressure + self._chronic_pressure,
            "guilt_events": [e.to_dict() for e in self.guilt_events[-50:]],
            "alignment_events": [{
                "value_name": e.value_name,
                "action": e.action,
                "timestamp": e.timestamp,
                "relief": e.relief,
            } for e in self.alignment_events[-30:]],
            "last_collapse_count": self._last_collapse_count,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """反序列化. v1.3.0 rc.2: 优先新 schema (双通道), 兼容旧 schema."""
        # 新 schema
        if "acute_pressure" in data and "chronic_pressure" in data:
            self._acute_pressure = float(data["acute_pressure"])
            self._chronic_pressure = float(data["chronic_pressure"])
        else:
            # 兼容旧 schema (single _raw_pressure): 全部当急性 (从急性衰减快恢复)
            legacy_pressure = data.get("raw_pressure", data.get("pressure", 0.0))
            self._acute_pressure = float(legacy_pressure)
            self._chronic_pressure = 0.0
        # events
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
        self._last_collapse_count = data.get("last_collapse_count", 0)
        # _last_tick_time 用当前时间, 避免反序列化后 lazy decay 用旧时间戳算超大间隔
        self._last_tick_time = time.time()

    def reset(self) -> None:
        """§1.5 生命周期: 清双通道 + events + collapse count + tick time.

        v1.3.0 rc.2 补 (test_lifecycle_pairs 守护).
        """
        self._acute_pressure = 0.0
        self._chronic_pressure = 0.0
        self.guilt_events = []
        self.alignment_events = []
        self._last_collapse_count = 0
        self._last_tick_time = time.time()
        self._window.clear()