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


__all__ = [
    "DefenseStates",
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
