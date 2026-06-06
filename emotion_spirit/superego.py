"""超我反思层 — 价值抵抗 + 价值对齐 + 良心事件 + 理想自我。

P0 重构: 从"外部拦截"到"内在冲突"的范式转换。
- ValueResistance: 人格价值观对行为的光谱响应
- ValueAlignment: 追踪行为与价值观的对齐关系 (重写，修复多值冲突)
- ConscienceTracker: 良心压力追踪 (增压+减压路径)
- IdealSelf: 随经验漂移的理想人格

纯规则引擎，零 LLM。
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .persona_profiles import get_personality_params, get_value_behaviors, DIMENSION_DISPLAY, get_narrative
from .config import SUPEREGO_CONFIG


# ═══ 维度 → 张力倾向映射 ═══
# 基于 Tangney (2002) shame/guilt 区分理论:
#   guilt  → 关系/行为维度 → 违背行为标准 → 修复导向
#   doubt  → 认知/感知维度 → 认知一致性破坏 → 怀疑导向
#   shame  → 自我/自主维度 → 自我价值质疑 → 退缩导向
_TENSION_INCLINATION: dict[str, str] = {
    # guilt 组: 关系/行为维度
    "relational_gravity": "guilt",
    "intimacy_pull": "guilt",
    "warmth_bias": "guilt",
    "expression_drive": "guilt",
    # doubt 组: 认知/感知维度
    "inner_coherence": "doubt",
    "curiosity": "doubt",
    "perception_acuity": "doubt",
    "directness": "doubt",
    "boundary_permeability": "doubt",
    # shame 组: 自我/自主维度
    # v1.7: autonomy_guard 拆分
    "relational_autonomy": "shame",   # 边界被侵 → shame
    "patience": "shame",
    # v1.7: 新维度 exploration_openness 归 doubt 组 (认知/感知)
    "exploration_openness": "doubt",  # 探索受阻 → doubt (不是 shame)
}


# ═══ 价值抵抗 ═══

@dataclass
class ResistanceResult:
    """一次价值抵抗计算的结果。"""
    resistance: float
    conflict_values: list[str]
    aligned_values: list[str]
    tension_type: str | None
    behavioral_shift: float
    conscience_impact: float
    context_note: str


class ValueResistance:
    """价值抵抗计算器 — 人格价值观对行为的光谱响应。

    三阶段权重分化流水线:
      1. S 曲线非线性映射（Fleeson: 极端值影响力非线性）
      2. Top-K 核心维度筛选（Schwartz + ACT: 3-5 个核心价值观）
      3. 基线引力锚定（Kagan + Bowlby: 气质底色 + 压力重现）

    不持有标签引用。权重直接从当前 13 维参数推导，
    参数漂移后权重自动跟随。
    """

    def __init__(self, persona: str) -> None:
        self._persona = persona
        self._values: dict[str, float] = {}  # 扁平 dict: {dim: weight}
        self._reinforcement: dict[str, float] = {}
        self._baseline_personality: dict[str, dict[str, float]] = {}  # MBTI 初始化时保存
        self._interaction_count: int = 0
        self._current_personality: dict[str, dict[str, float]] | None = None  # 供 _build_note 使用

    def compute(
        self,
        action: str,
        context: dict[str, float] | None = None,
        current_personality: dict[str, dict[str, float]] | None = None,
        stress_level: float = 0.0,
    ) -> ResistanceResult:
        """计算人格对当前行为的价值抵抗。

        Args:
            action: SylannEngine decision action (express/withdraw/recover/...)
            context: 上下文信号 (可选)
            current_personality: 当前 13 维参数 (deep/surface)
            stress_level: 当前压力水平 [0, 1]，用于基线引力加成
        """
        self._current_personality = current_personality
        self._values = self._build_value_system(
            current_personality, stress_level,
        )

        cfg = SUPEREGO_CONFIG["resistance_context_modifiers"]
        value_behaviors = get_value_behaviors()

        conflict_values: list[str] = []
        aligned_values: list[str] = []

        for value_name, mapping in value_behaviors.items():
            if action in mapping.get("misaligned", []):
                conflict_values.append(value_name)
            elif action in mapping.get("aligned", []):
                aligned_values.append(value_name)

        conflict_strength = sum(self._get_weight(v) for v in conflict_values)
        aligned_strength = sum(self._get_weight(v) for v in aligned_values)

        total = conflict_strength + aligned_strength
        if total > 0:
            resistance = conflict_strength / total
        else:
            resistance = 0.0

        if context:
            body_crit = context.get("body_criticality", 0.0)
            resistance = min(1.0, resistance + body_crit * cfg["body_criticality_boost"])

            if context.get("cascade_active", False):
                resistance *= cfg["cascade_reduction"]

            intimacy = context.get("intimacy", 0.5)
            if action == "reach_out":
                resistance *= max(0.3, 1.0 - intimacy * cfg["intimacy_reach_out_reduction"])

        tension_type = self._classify_tension(
            conflict_values, aligned_values, current_personality,
        )

        behavioral_shift = resistance * 0.6
        if tension_type == "righteous":
            behavioral_shift *= 0.3

        # v2: 净效果 — aligned 减压 vs conflict 增压
        coef = SUPEREGO_CONFIG.get("conscience_impact_coef", 0.15)
        if conflict_values and aligned_values:
            # 两者都有: 净效果 = conflict增压 - aligned减压
            conflict_pressure = resistance * coef
            aligned_relief = SUPEREGO_CONFIG.get("alignment_base_relief", 0.12) * 0.3 * len(aligned_values)
            conscience_impact = conflict_pressure - aligned_relief
        elif conflict_values:
            conscience_impact = resistance * coef
        elif aligned_values:
            conscience_impact = -SUPEREGO_CONFIG.get("alignment_base_relief", 0.12) * 0.3 * len(aligned_values)
        else:
            conscience_impact = 0.0

        context_note = self._build_note(
            conflict_values, aligned_values, tension_type, resistance,
        )

        return ResistanceResult(
            resistance=round(resistance, 4),
            conflict_values=conflict_values,
            aligned_values=aligned_values,
            tension_type=tension_type,
            behavioral_shift=round(behavioral_shift, 4),
            conscience_impact=round(conscience_impact, 4),
            context_note=context_note,
        )

    def update_reinforcement(self, value_name: str, delta: float) -> None:
        """价值观经验强化/衰减。"""
        current = self._reinforcement.get(value_name, 0.0)
        max_shift = SUPEREGO_CONFIG["reinforcement_max"]
        self._reinforcement[value_name] = max(-max_shift, min(max_shift, current + delta))

    def _get_weight(self, value_name: str) -> float:
        """获取价值观权重 (参数值 + 经验强化)。"""
        base = self._values.get(value_name, 0.5)
        reinforcement = self._reinforcement.get(value_name, 0.0)
        return max(0.0, min(1.0, base + reinforcement))

    def _classify_tension(
        self,
        conflict_values: list[str],
        aligned_values: list[str],
        personality: dict[str, dict[str, float]] | None,
    ) -> str | None:
        """基于权重的动态 tension 分类。

        理论依据:
        - Tangney (2002): shame 攻击自我, guilt 攻击行为
        - Lopez (1997): 依恋风格调节 shame/guilt 易感性
        - Lazarus (1991): 情绪由认知评价决定, 核心关切影响评价
        - Weiner (1995): 归因 → 情绪 → 意图因果链

        算法:
        1. 同时有 aligned + conflict → 检查对齐比例，≥0.7 才是 righteous (v2: Weiner 归因模型)
        2. 每个冲突维度按其权重累加 tension 倾向得分
        3. 返回得分最高的 tension type
        """
        if not conflict_values:
            return None

        # 计算冲突和对齐的强度
        aligned_strength = sum(self._get_weight(v) for v in aligned_values) if aligned_values else 0.0
        conflict_strength = sum(self._get_weight(v) for v in conflict_values)
        total = aligned_strength + conflict_strength

        # 坚持型: 同时有对齐和冲突，且对齐比例足够高 (v2: 条件判断)
        if aligned_values and conflict_values:
            alignment_ratio = aligned_strength / total if total > 0 else 0.0
            if alignment_ratio >= 0.85:  # v2: 提高阈值，减少和平场景误判为 righteous
                return "righteous"
            # 对齐比例不足，fall through 到普通 tension 分类

        # 获取权重 (已在 compute() 中由 _build_value_system 构建)
        weights = self._values

        # 按权重累加每种 tension 的得分
        tension_scores: dict[str, float] = {"guilt": 0.0, "doubt": 0.0, "shame": 0.0}
        for dim in conflict_values:
            inclination = _TENSION_INCLINATION.get(dim)
            if inclination:
                w = weights.get(dim, 0.5)
                tension_scores[inclination] += w

        # 返回得分最高的 tension type
        if not any(tension_scores.values()):
            return "guilt"  # fallback

        return max(tension_scores, key=tension_scores.get)

    def _build_note(
        self,
        conflict_values: list[str],
        aligned_values: list[str],
        tension_type: str | None,
        resistance: float,
    ) -> str:
        """构建人格化自然语言描述（基于叙事模板）。"""
        if not conflict_values and not aligned_values:
            return ""

        personality = self._current_personality
        notes = []

        if conflict_values:
            scene = "violation"
            conflict_parts = [get_narrative(dim, scene, personality) for dim in conflict_values]
            notes.append("；".join(conflict_parts))

        if aligned_values:
            scene = "alignment"
            aligned_parts = [get_narrative(dim, scene, personality) for dim in aligned_values]
            notes.append("；".join(aligned_parts))

        return "；".join(notes)

    def _build_value_system(
        self,
        current_personality: dict[str, dict[str, float]] | None,
        stress_level: float = 0.0,
    ) -> dict[str, float]:
        """三阶段权重分化流水线。

        阶段 1: S 曲线非线性映射 (Fleeson, 2001)
        阶段 2: Top-K 核心维度筛选 (Schwartz, 1992; Hayes, 2006)
        阶段 3: 基线引力锚定 (Kagan, 1994; Roberts & DelVecchio, 2000)

        Returns:
            扁平 dict: {"dim": 0.763, ...}
        """
        # 降级：无 baseline 时退化为线性方案
        if not self._baseline_personality:
            return self._build_value_system_linear(current_personality)

        # 收集当前值
        current: dict[str, float] = {}
        for layer in ("deep", "surface"):
            for dim, val in (current_personality or {}).get(layer, {}).items():
                current[dim] = val

        # 如果 current 为空，使用 baseline
        if not current:
            for layer in ("deep", "surface"):
                for dim, val in self._baseline_personality.get(layer, {}).items():
                    current[dim] = val

        # ── 阶段 1: S 曲线非线性映射 ──
        # f(x) = (x - 0.5)³ × 4 + 0.5
        # 拉开两端，压缩中间 (Fleeson, 2001)
        nonlinear: dict[str, float] = {}
        for dim, val in current.items():
            shifted = (val - 0.5) ** 3 * 4 + 0.5
            nonlinear[dim] = max(0.0, min(1.0, round(shifted, 4)))

        # ── 阶段 2: Top-K 核心维度筛选 ──
        # 只保留权重最高的 K 个维度作为核心价值观 (Schwartz, 1992; Hayes, 2006)
        wd_cfg = SUPEREGO_CONFIG["weight_differentiation"]
        top_k = int(wd_cfg["top_k"])
        noncore_ratio = float(wd_cfg["noncore_ratio"])

        sorted_dims = sorted(nonlinear.items(), key=lambda x: x[1], reverse=True)
        core_dims = {d for d, _ in sorted_dims[:top_k]}

        # ── 阶段 3: 基线引力锚定 ──
        # anchor_strength = anchor_base × (1 / (1 + n / anchor_decay))
        # 基于 Roberts & DelVecchio (2000) 的稳定性系数拟合
        anchor_base = float(wd_cfg["anchor_base"])
        anchor_decay = float(wd_cfg["anchor_decay"])
        stress_multiplier = float(wd_cfg["stress_multiplier"])

        anchor_strength = anchor_base * (1.0 / (1.0 + self._interaction_count / anchor_decay))
        stress_boost = 1.0 + stress_level * stress_multiplier

        # 收集 baseline 值
        baseline: dict[str, float] = {}
        for layer in ("deep", "surface"):
            for dim, val in self._baseline_personality.get(layer, {}).items():
                baseline[dim] = val

        weights: dict[str, float] = {}
        for dim, val in nonlinear.items():
            # 核心 vs 非核心
            if dim in core_dims:
                weight = val
            else:
                weight = val * noncore_ratio

            # 基线引力
            deviation = current.get(dim, 0.5) - baseline.get(dim, current.get(dim, 0.5))
            gravity = deviation * anchor_strength * stress_boost
            weight = weight - gravity

            weights[dim] = max(0.0, min(1.0, round(weight, 4)))

        return weights

    def _build_value_system_linear(
        self, personality: dict[str, dict[str, float]] | None,
    ) -> dict[str, float]:
        """线性降级方案 — 无 baseline 时使用。

        直接用参数值作为权重，不做 S 曲线/Top-K/引力。
        """
        if not personality:
            from .label_mapper import _BASELINE
            personality = _BASELINE

        values: dict[str, float] = {}
        for layer in ("deep", "surface"):
            for dim, val in personality.get(layer, {}).items():
                values[dim] = round(val, 4)
        return values

    def to_dict(self) -> dict:
        return {
            "persona": self._persona,
            "baseline_personality": self._baseline_personality,
            "interaction_count": self._interaction_count,
            "reinforcement": dict(self._reinforcement),
        }

    def from_dict(self, data: dict) -> None:
        self._reinforcement = data.get("reinforcement", {})
        self._baseline_personality = data.get("baseline_personality", {})
        self._interaction_count = data.get("interaction_count", 0)


# ═══ 价值对齐 ═══

class ValueAlignment:
    """价值对齐追踪 — 记录行为与价值观的关系。

    P0 重写: 不再 early-return，每个涉及的价值观都会被记录。
    misaligned 路径也计入 _total_count，分数不再虚高。
    支持人格区分。
    """

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


# ═══ 良心事件 ═══

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
    """良心追踪 — 价值冲突增压 + 价值对齐减压。

    P0 重写: 新增减压路径 (alignment, repair)，guard/cascade 降权。
    """

    def __init__(self) -> None:
        self.guilt_events: list[GuiltEvent] = []
        self.alignment_events: list[AlignmentEvent] = []
        self._last_collapse_count: int = 0
        self._pressure: float = 0.0
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
        self._pressure = min(1.0, self._pressure + abs(conscience_impact))
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
        self._pressure = min(1.0, self._pressure + severity)
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
        self._pressure = min(1.0, self._pressure + severity * 0.5)
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
            self._pressure = min(1.0, self._pressure + 0.8)
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
        self._pressure = max(0.0, self._pressure - relief)
        return event

    def record_repair(self, repair_type: str = "simple") -> None:
        """修复行为 → 良心大幅减压。"""
        relief_map = SUPEREGO_CONFIG["repair_relief"]
        relief = relief_map.get(repair_type, relief_map["simple"])
        self._pressure = max(0.0, self._pressure - relief)

    # ═══ 向后兼容 ═══

    def record_guard_rejected(self, risk_score: float, reason: str) -> GuiltEvent:
        """向后兼容: 转发到 record_guard_reflex。"""
        return self.record_guard_reflex(risk_score, reason)

    # ═══ 读取 ═══

    def get_pressure(self) -> float:
        """良心压力 [0, 1]。"""
        return round(max(0.0, min(1.0, self._pressure)), 4)

    def tick_pressure(self, hours_elapsed: float) -> None:
        """自然衰减 (每小时调用)。"""
        ratio = (1.0 - self._pressure_decay_rate) ** hours_elapsed
        self._pressure *= ratio

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
            "pressure": self.get_pressure(),
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
            "pressure": self._pressure,
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
        self._pressure = data.get("pressure", 0.0)
        self._last_collapse_count = data.get("last_collapse_count", 0)


# ═══ 理想自我 ═══

class IdealSelf:
    """理想自我 — 随经验漂移的目标人格。

    v1: 从 persona 标签固定推导。
    P0: ideal_self 会随 value_reinforcement 动态调整。
    """

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