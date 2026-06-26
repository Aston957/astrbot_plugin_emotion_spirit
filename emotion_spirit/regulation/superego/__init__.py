"""Superego 子系统 — 4 个聚焦模块（超我道德调节）。

- ValueResistance: 价值抵抗（行为对人格的光谱响应）
- ValueAlignment: 价值对齐追踪
- ConscienceTracker: 良心压力追踪（增压+减压）
- IdealSelf: 理想自我（随经验漂移的目标人格）

通过 @register 注册到 ModuleRegistry，4 sub-classes 走 multi-instance 分支。
"""
from __future__ import annotations

from ...core.registry import register
from .alignment import ValueAlignment
from .conscience import (
    AlignmentEvent,
    ConscienceTracker,
    GuiltEvent,
)
from .ideal import IdealSelf
from .resistance import ResistanceResult, ValueResistance


__all__ = [
    "ResistanceResult",
    "ValueResistance",
    "ValueAlignment",
    "GuiltEvent",
    "AlignmentEvent",
    "ConscienceTracker",
    "IdealSelf",
    "_SuperegoBundle",
    "_SuperegoMarker",
]


class _SuperegoBundle:
    """4 sub-component 容器 (registry build() multi-instance 入口)。

    实际不实例化, build() 用 provides_classes 走 multi-instance 分支。
    marker class 见文件末尾 (4 sub-classes 定义完后才注册, 避免 monkey-patch + type: ignore)。
    """


@register(
    name="superego",
    provides=["ValueResistance", "ValueAlignment", "ConscienceTracker", "IdealSelf"],
    depends_on=[],
    config_keys={"persona_id", "labels", "persona"},
    param_wire={"persona_id": "persona"},  # config_key "persona_id" → __init__ 形参 "persona"
    provides_classes={
        "alignment": ValueAlignment,
        "resistance": ValueResistance,
        "conscience": ConscienceTracker,
        "ideal": IdealSelf,
    },
)
class _SuperegoMarker(_SuperegoBundle):
    pass
