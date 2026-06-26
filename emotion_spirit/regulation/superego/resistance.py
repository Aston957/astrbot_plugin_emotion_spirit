"""ValueResistance — 行为对人格价值观的光谱响应。

三阶段权重分化流水线:
  1. S 曲线非线性映射（Fleeson: 极端值影响力非线性）
  2. Top-K 核心维度筛选（Schwartz + ACT: 3-5 个核心价值观）
  3. 基线引力锚定（Kagan + Bowlby: 气质底色 + 压力重现）

不持有标签引用。权重直接从当前 13 维参数推导，
参数漂移后权重自动跟随。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...core.config import SUPEREGO_CONFIG
from ...memory.persona_profiles import get_value_behaviors, get_narrative


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
    """价值抵抗计算器 — 人格价值观对行为的光谱响应。"""

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

        # 按权重累加每种 tension 的得分 (Phase B: 走 KnowledgeBase.TENSION_INCLINATION)
        from ...core.knowledge import KnowledgeBase
        tension_inclination = KnowledgeBase.TENSION_INCLINATION
        tension_scores: dict[str, float] = {}
        for dim in conflict_values:
            inclination = tension_inclination.get(dim)
            if inclination:
                w = weights.get(dim, 0.5)
                tension_scores[inclination] = tension_scores.get(inclination, 0.0) + w

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
            from ...core.label_mapper import _BASELINE
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
