"""Body state — hormone/energy/arousal 三字段 (Phase 3.0B Task 3)。

3 字段 (all in [0, 1]) 代表身体生理状态, 用于 ForceDynamics.compute() 调
制 3 元力学的强度计算 (per spec §3.1)：

- hormone: 激素水平 (cortisol-like).
    高 (0.8) → individual 倾向 (Kahneman 压力反应: 应激时自我中心)
    低 (0.2) → social 倾向 (放松时更关注他人)
    方向系数: natural -0.5, social -0.3, individual +0.8 (个体最敏感)
- energy:  能量储备.
    低 (0.0) → 全力学衰减 (Selye 一般适应综合征: 疲劳时全维度衰减)
    高 (1.0) → 全力学完整 (无衰减)
    factor = 0.5 + 0.5 * energy ∈ [0.5, 1.0], 同步作用于 3 力 raw intensity
- arousal: 唤醒度 (Yerkes-Dodson 曲线).
    高 (1.0) → 极端化 (高唤醒时 per-dim 偏离被放大)
    低 (0.0) → 弱化 (低唤醒时 per-dim 偏离被压缩)
    factor = 0.5 + arousal ∈ [0.5, 1.5], 作用于 per-dim salience (在
    intensity = signed_dev * salience 计算前)

BodyState 接入 ForceDynamics:
  - hormone=0.5, energy=0.5, arousal=0.5 → 中性值, 输出跟无 body_state 一致
  - 默认 factory: BodyStateModule.default() → BodyState(0.5, 0.5, 0.5)
  - 纯数据, 无 DI 依赖 (独立模块, 不被其他模块依赖)
"""
from __future__ import annotations
from dataclasses import dataclass

from .registry import register



__all__ = [
    "BodyState",
    "BodyStateModule",
]

@dataclass
class BodyState:
    """身体状态 (Phase 3.0B) — 3 字段 [0, 1]。

    - hormone: 激素水平 (cortisol-like). 高 → individual 倾向 (Kahneman 压力反应)
    - energy:  能量储备. 低 → 全力学衰减 (Selye 一般适应综合征)
    - arousal: 唤醒度 (Yerkes-Dodson 曲线). 高 → 极端化
    """

    hormone: float = 0.5
    energy: float = 0.5
    arousal: float = 0.5

    def __post_init__(self) -> None:
        for name in ("hormone", "energy", "arousal"):
            v = getattr(self, name)
            if not (0.0 <= v <= 1.0):
                raise ValueError(
                    f"BodyState.{name} 必须在 [0, 1], got {v}"
                )


@register(
    name="body_state",
    provides=["BodyState"],
    depends_on=[],  # 纯数据, 无 DI
)
class BodyStateModule:
    """BodyState factory + 默认值 (Phase 3.0B)。

    职责:
    - default() → BodyState(0.5, 0.5, 0.5) 中性值
    - from_dict(dict) → BodyState 构造, 缺字段填 0.5

    未来 Phase 3.0C/3.5 可接入 public_api.get_body_state() 把现有
    warmth/pulse/expression/repair 4 字段转换成 hormone/energy/arousal 3 字段
    (映射公式待设计), 当前 task 不做。
    """

    def __init__(self) -> None:
        self._default = BodyState()  # 全 0.5 中性

    def default(self) -> BodyState:
        return self._default

    def from_dict(self, d: dict[str, float]) -> BodyState:
        return BodyState(
            hormone=d.get("hormone", 0.5),
            energy=d.get("energy", 0.5),
            arousal=d.get("arousal", 0.5),
        )
