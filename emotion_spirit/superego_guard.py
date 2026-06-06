"""超我防护层 — 软干预决策 + 修复建议。

合并 SafetyGuard 和 RepairAdvisor，统一封装"超我安全"逻辑。
只做 prompt 层调整，不强制修改 SylannEngine 状态。

通过 SAFETY_CONFIG["enabled"] 开关可整体禁用。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from .config import SAFETY_CONFIG
from .persona_profiles import DIMENSION_DISPLAY, get_narrative

if TYPE_CHECKING:
    from .superego import ConscienceTracker, ValueAlignment, IdealSelf


@dataclass
class InterventionResult:
    """干预指令。"""
    level: str
    conscience_threshold: float
    alignment_show_count: int
    show_repair: bool
    safety_note: str | None
    repair_advice: str | None
    log_reason: str


class SuperegoGuard:
    """超我防护层 — 软干预决策 + 修复建议。

    职责:
    1. 接收 sentinel 结果，叠加超我信号，输出干预级别
    2. 生成 prompt 调整指令 (阈值/展示控制/安全提示)
    3. 基于 tension_type + conflict_values 生成修复建议

    设计原则:
    - 软干预：只修改 prompt 注入，不修改 SylannEngine 状态
    - 人格化口吻："你注意到自己…", 不是 "系统检测到…"
    - 可插拔：通过 SAFETY_CONFIG["enabled"] 整体开关
    """

    def __init__(
        self,
        conscience: ConscienceTracker,
        alignment: ValueAlignment,
        ideal: IdealSelf,
        persona: str = "",
    ) -> None:
        self._conscience = conscience
        self._alignment = alignment
        self._ideal = ideal
        self._persona = persona
        self._personality_cache: dict[str, dict[str, float]] | None = None
        self._last_critical_time: float = 0.0
        self._critical_count_24h: int = 0
        self._last_critical_reset: float = time.time()

    def assess(
        self,
        sentinel_result: dict[str, Any],
        current_personality: dict[str, dict[str, float]] | None = None,
    ) -> InterventionResult:
        """评估当前状态，返回干预指令。

        Args:
            sentinel_result: PredictiveSentinel.check() 的返回值
            current_personality: 当前人格参数 (deep/surface)

        Returns:
            InterventionResult 包含级别、prompt 调整指令、安全提示等
        """
        if not SAFETY_CONFIG.get("enabled", True):
            return self._no_intervention()

        self._personality_cache = current_personality

        # 1. 检测超我信号
        superego_triggers = self._detect_superego_signals(current_personality)

        # 2. 叠加判定级别
        sentinel_level = sentinel_result.get("level", "normal")
        level = self._combine_levels(sentinel_level, len(superego_triggers))

        # 3. 生成 prompt 调整指令
        if level == "normal":
            return self._no_intervention()

        # 4. 节流：critical 24h 内最多 N 次
        if level == "critical":
            if not self._throttle_critical():
                level = "warning"  # 降级为 warning

        # 5. 生成安全提示和修复建议
        safety_note = self._build_safety_note(level, superego_triggers)
        repair_advice = None
        if level == "critical":
            repair_advice = self._generate_repair_advice()

        # 6. 组装 prompt 调整参数
        cfg = SAFETY_CONFIG
        return InterventionResult(
            level=level,
            conscience_threshold=cfg[f"conscience_threshold_{level}"],
            alignment_show_count=cfg[f"alignment_show_count_{level}"],
            show_repair=(level == "critical"),
            safety_note=safety_note,
            repair_advice=repair_advice,
            log_reason=f"sentinel={sentinel_level}, superego={len(superego_triggers)} triggers: {superego_triggers}",
        )

    def advise(
        self,
        tension_type: str,
        conflict_values: list[str],
        personality: dict[str, dict[str, float]] | None = None,
    ) -> str:
        """基于 tension_type 和冲突价值观生成人格化修复建议。

        使用叙事模板 (get_narrative) 替代固定模板，
        不同人格参数会产生不同的建议措辞。

        Args:
            tension_type: 张力类型 (guilt/shame/doubt/righteous)
            conflict_values: 维度名列表（英文）
            personality: 当前 13 维参数 (可选，用于叙事变体选择)
        Returns:
            人格化修复建议
        """
        max_values = SAFETY_CONFIG.get("repair_max_values", 2)
        p = personality or self._personality_cache

        # 使用叙事模板生成建议
        advice_parts = [get_narrative(dim, "advice", p) for dim in conflict_values[:max_values]]
        if advice_parts:
            return "；".join(advice_parts)

        # fallback: 无冲突维度时使用通用建议
        fallback_map = {
            "guilt": "也许你可以试着坦诚地表达一次",
            "shame": "先停下来，给自己一点空间",
            "doubt": "如果你觉得哪里说不通，不妨多问一句",
            "righteous": "你在坚持一些很难的事，但也记得照顾好自己",
        }
        return fallback_map.get(tension_type, "也许该停下来想一想")

    # ═══ 内部方法 ═══

    def _no_intervention(self) -> InterventionResult:
        """无干预的默认返回。"""
        return InterventionResult(
            level="normal",
            conscience_threshold=SAFETY_CONFIG["conscience_threshold_normal"],
            alignment_show_count=SAFETY_CONFIG["alignment_show_count_normal"],
            show_repair=False,
            safety_note=None,
            repair_advice=None,
            log_reason="",
        )

    def _detect_superego_signals(self, current_personality: dict | None) -> list[str]:
        """检测超我信号，返回触发的信号 ID 列表。"""
        triggers: list[str] = []
        cfg = SAFETY_CONFIG

        # 1. conscience_pressure_rising
        pressure = self._conscience.get_pressure()
        if pressure > cfg["pressure_rise_threshold"]:
            triggers.append("conscience_pressure_rising")

        # 2. value_conflict_clustering (1h 内 ≥ N 次 value_conflict)
        window = cfg["conflict_cluster_window_hours"]
        recent_conflicts = self._conscience.get_recent(
            hours=window, event_type="value_conflict",
        )
        if len(recent_conflicts) >= cfg["conflict_cluster_count"]:
            triggers.append("value_conflict_clustering")

        # 3. alignment_declining
        trend = self._alignment.get_trend(20)
        if trend < cfg["alignment_decline_threshold"]:
            triggers.append("alignment_declining")

        # 4. ideal_self_drift
        if current_personality:
            gap = self._ideal.compute_gap(current_personality)
            if gap > cfg["ideal_drift_threshold"]:
                triggers.append("ideal_self_drift")

        # 5. guard_reflex_frequency (1h 内 ≥ N 次 guard_reflex)
        guard_window = cfg["guard_reflex_window_hours"]
        recent_guards = self._conscience.get_recent(
            hours=guard_window, event_type="guard_reflex",
        )
        if len(recent_guards) >= cfg["guard_reflex_count"]:
            triggers.append("guard_reflex_frequency")

        return triggers

    def _combine_levels(self, sentinel_level: str, superego_count: int) -> str:
        """叠加 sentinel 级别和超我信号数量，判定最终级别。"""
        if sentinel_level == "critical":
            return "critical"
        if sentinel_level == "warning" and superego_count >= 2:
            return "critical"
        if sentinel_level == "warning" or superego_count >= 1:
            return "warning"
        return "normal"

    def _throttle_critical(self) -> bool:
        """节流：24h 内 critical 最多触发 N 次。返回 True 表示允许触发。"""
        now = time.time()
        # 每 24h 重置计数
        if now - self._last_critical_reset > 86400:
            self._critical_count_24h = 0
            self._last_critical_reset = now

        max_per_day = SAFETY_CONFIG.get("critical_max_per_day", 3)
        if self._critical_count_24h >= max_per_day:
            return False

        self._critical_count_24h += 1
        self._last_critical_time = now
        return True

    def _build_safety_note(self, level: str, triggers: list[str]) -> str | None:
        """生成人格化安全提示文本。"""
        if level == "normal":
            return None

        breakdown = self._conscience.get_pressure_breakdown()
        dominant = breakdown.get("dominant_tension")

        tension_notes = {
            "guilt": "你注意到自己最近一直在违背某些重要的事",
            "shame": "你最近对自己有些不满意",
            "doubt": "你最近有些事觉得说不通",
            "righteous": "你最近在坚持一些很难的事",
            "value_conflict": "有些事和你的价值观冲突了",
            "guard_reflex": "你的直觉在阻止一些事",
            "cascade": "你最近的情绪波动很大",
        }

        if dominant and dominant in tension_notes:
            note = tension_notes[dominant]
        else:
            note = "你最近承受着不小的内在压力"

        if level == "critical":
            return f"{note}，也许该停下来照顾一下自己"
        return f"{note}"

    def _generate_repair_advice(self) -> str | None:
        """基于当前超我状态生成修复建议。"""
        breakdown = self._conscience.get_pressure_breakdown()
        dominant = breakdown.get("dominant_tension")

        if not dominant:
            return None

        # 从最近的 guilt_events 提取冲突价值观
        recent_events = self._conscience.get_recent(hours=24)
        conflict_values: list[str] = []
        for e in recent_events:
            if hasattr(e, "conflict_values"):
                conflict_values.extend(e.conflict_values)
        conflict_values = list(dict.fromkeys(conflict_values))  # 去重保序

        if not conflict_values:
            return self.advise(dominant, ["最近的事"], self._personality_cache)

        return self.advise(dominant, conflict_values, self._personality_cache)

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_critical_time": self._last_critical_time,
            "critical_count_24h": self._critical_count_24h,
            "last_critical_reset": self._last_critical_reset,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self._last_critical_time = data.get("last_critical_time", 0.0)
        self._critical_count_24h = data.get("critical_count_24h", 0)
        self._last_critical_reset = data.get("last_critical_reset", time.time())