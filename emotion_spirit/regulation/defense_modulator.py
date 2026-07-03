"""Defense Modulator — 压抑/崩溃/沉默 三防御子系统与力学的耦合调制器 (v1.2.5 PR2 §4)

L1 (输入调制): 三子读 force_state, 输出 DefenseStates
L2 (输出回写): 防御事件触发后调 force_dynamics.shift()
v1.3 加: L3 fixpoint 完全耦合

设计原则 (handbook §1.2):
- 单一职责: 只管三子↔力学耦合, 不掺业务
- 加新防御子 (v1.3 焦虑/解离等): 在此加字段, 不动 main.py
- 系数全部从 KB 读 (handbook §1.1), 不硬编码
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any

from ..core.persona_labels_db import get_defense_deltas
from ..core.registry import register


__all__ = [
    "DefenseStates",
    "DefenseModulator",
]


@dataclass
class DefenseStates:
    """v1.2.5 PR2 三子连续值 (供 force_dynamics 决策)

    字段全 [0, 1], 缺省 0.0 (无防御激活)
    """
    suppression_level: float = 0.0
    collapse_tendency: float = 0.0
    silence_tendency: float = 0.0
    silence_reason: str = ""           # 透明性
    silence_components: dict = field(default_factory=dict)

    def __post_init__(self):
        # Clamp 到 [0, 1]
        self.suppression_level = max(0.0, min(1.0, self.suppression_level))
        self.collapse_tendency = max(0.0, min(1.0, self.collapse_tendency))
        self.silence_tendency = max(0.0, min(1.0, self.silence_tendency))


@register(
    name="defense_modulator",
    provides=["DefenseModulator"],
    depends_on=[
        "force_dynamics",
        "suppression",
        "collapse_archetype_selector",
        "segmented_reply_coordinator",
    ],
)
class DefenseModulator:
    """v1.2.5 PR2: 压抑/崩溃/沉默 三防御子系统与力学的耦合调制器

    L1 (输入调制): 三子读 force_state, 输出 DefenseStates
    L2 (输出回写): 防御事件触发后调 force_dynamics.shift()
    v1.3 加: L3 fixpoint 完全耦合

    v1.2.5 单步法 (不上 fixpoint): 用上次累积的 force_state 算当前三子
    """

    def __init__(
        self,
        force_dynamics: Any = None,
        suppression: Any = None,
        collapse_archetype_selector: Any = None,
        segmented_reply_coordinator: Any = None,
    ) -> None:
        # factory 通过 depends_on 注入依赖
        self._force_dynamics = force_dynamics
        self._suppression = suppression
        self._collapse_selector = collapse_archetype_selector
        self._segmented_coordinator = segmented_reply_coordinator

    def compute_defense_states(
        self,
        personality: dict,
        signals: Optional[Any],
        body_state: Optional[Any],
        intimacy_level: float,
        context: dict,
        force_state: Optional[dict],
        conscience_pressure: float = 0.0,  # v1.2.7 HP-2: 显式传参, 替代旧 hasattr 分支
    ) -> DefenseStates:
        """L1: 三子读力学, 返回 DefenseStates

        向后兼容: force_state=None 时, 三子都不接收 force_state (跟 v1.2.4 一致)
        conscience_pressure 默认 0.0 (向后兼容不传的场景)
        """
        # 1. 压抑
        kwargs = {"force_state": force_state} if force_state is not None else {}
        suppression_level = self._suppression.compute(
            personality, context,
            conscience_pressure=conscience_pressure,
            relationship_intimacy=intimacy_level,
            **kwargs,
        )

        # 2. 崩溃
        _, _, collapse_tendency = self._collapse_selector.compute_bas_bis(
            personality, **kwargs,
        )

        # 3. 沉默
        session_key = context.get("session_key", "default")
        silence_tendency_obj = self._segmented_coordinator.compute_silence_tendency(
            user_id=session_key,
            personality=personality,
            force_state=force_state,
            body_state=body_state,
            signals=signals,
            intimacy_level=intimacy_level,
            context=context,
        )

        return DefenseStates(
            suppression_level=suppression_level,
            collapse_tendency=collapse_tendency,
            silence_tendency=silence_tendency_obj.score,
            silence_reason=silence_tendency_obj.reason,
            silence_components=silence_tendency_obj.components,
        )

    def apply_event(
        self,
        defense_type: str,  # Literal["suppression", "collapse", "silence"]
        intensity: float,
    ) -> None:
        """L2: 防御事件触发后回写 force_state (从 KB 读 delta)

        intensity ∈ [0, 1]

        v1.2.5 (单步法): 仅累加到 force_dynamics._cumulative_offset,
        不影响下次 compute() 输出. v1.3 L3 fixpoint 接通 compute() 调制.
        """
        if defense_type not in ("suppression", "collapse", "silence"):
            raise ValueError(f"defense_type must be suppression/collapse/silence, got {defense_type!r}")

        deltas_kb = get_defense_deltas()
        deltas = deltas_kb[defense_type]

        self._force_dynamics.shift(
            individual_delta=deltas.get("individual", 0.0) * intensity,
            natural_delta=deltas.get("natural", 0.0) * intensity,
            social_delta=deltas.get("social", 0.0) * intensity,
        )
