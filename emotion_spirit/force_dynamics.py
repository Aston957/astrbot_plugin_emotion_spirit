"""emotion_spirit 三元力学引擎原型 (Phase 3.0A)。

理论基础: three-force-framework (memory)
- 自然 (Natural): warmth_bias, patience, boundary_permeability (3 dim)
- 社会 (Social): relational_gravity, intimacy_pull, expression_drive, gossip_tendency (4 dim)
- 个体 (Individual): inner_coherence, curiosity, perception_acuity, directness,
                     relational_autonomy, exploration_openness (6 dim)

算法 H (per-dim 极化 × 跨人方差):
  1. signed_dev = Σ (value - 0.5) × std[dim] / count
  2. salience = Σ |value - 0.5| × std[dim] / count
  3. intensity = signed_dev × salience
  4. normalize |intensity| → sum=1.0

Phase 3.0A 范围: 静态计算 + 验证
Phase 3.0B 接入: body state → 力学漂移, ConscienceTracker 累积
"""
from __future__ import annotations
from dataclasses import dataclass

from .registry import register
from .knowledge import KnowledgeBase


@dataclass
class ForceState:
    """三元力学状态 (3 权重, 归一化到 sum=1.0)."""

    natural: float
    social: float
    individual: float

    def __post_init__(self) -> None:
        total = self.natural + self.social + self.individual
        assert abs(total - 1.0) < 0.01, (
            f"ForceState 3 权重归一化和 != 1.0: {total:.4f}"
        )

    @property
    def dominant(self) -> str:
        """主导力 (按 natural → social → individual 顺序取最大)。"""
        if self.natural >= self.social and self.natural >= self.individual:
            return "natural"
        if self.social >= self.individual:
            return "social"
        return "individual"

    def to_dict(self) -> dict[str, float]:
        return {
            "natural": self.natural,
            "social": self.social,
            "individual": self.individual,
        }


@register(
    name="force_dynamics",
    provides=["ForceDynamics"],
    depends_on=[],  # 纯计算模块, 无 DI
)
class ForceDynamics:
    """三元力学引擎 — 13-dim personality → ForceState (算法 H)。"""

    def __init__(self) -> None:
        # KB 提供 DIM_FORCE + DIM_CROSS_PERSONA_STD
        self._dim_to_force = KnowledgeBase.DIM_FORCE
        self._dim_std = KnowledgeBase.DIM_CROSS_PERSONA_STD
        # 各力的 dim 列表 (算 count)
        self._force_dims: dict[str, list[str]] = {
            "natural": [], "social": [], "individual": [],
        }
        for dim, force in self._dim_to_force.items():
            self._force_dims[force].append(dim)

    def compute(self, personality: dict[str, float]) -> ForceState:
        """算法 H: per-dim 极化 × 跨人方差 → ForceState。

        Args:
            personality: 13 维 dim → float (允许 > 1.0, B 决策)

        Returns:
            ForceState (3 权重, sum=1.0)

        处理:
            - 缺 dim 跳过
            - 不在 DIM_FORCE 的 dim 跳过
            - 全 0 → 均匀 1/3 each
        """
        intensities: dict[str, float] = {"natural": 0.0, "social": 0.0, "individual": 0.0}
        for force in ("natural", "social", "individual"):
            signed_dev_sum = 0.0
            salience_sum = 0.0
            for dim in self._force_dims[force]:
                if dim not in personality:
                    continue
                value = personality[dim]
                std = self._dim_std.get(dim, 0.20)  # fallback
                dev = value - 0.5
                signed_dev_sum += dev * std
                salience_sum += abs(dev) * std
            count = len(self._force_dims[force])
            if count > 0:
                signed_dev = signed_dev_sum / count
                salience = salience_sum / count
                intensities[force] = signed_dev * salience

        # |intensity| 归一化
        abs_intensities = {f: abs(intensities[f]) for f in intensities}
        total = sum(abs_intensities.values())
        if total == 0:
            # 全 0.5 时所有 intensity=0 (无偏离中性), 退均匀
            return ForceState(natural=1/3, social=1/3, individual=1/3)
        return ForceState(
            natural=abs_intensities["natural"] / total,
            social=abs_intensities["social"] / total,
            individual=abs_intensities["individual"] / total,
        )

    def force_state_from_labels(self, labels: dict[str, str]) -> ForceState:
        """5 label → 13-dim baseline → ForceState (便捷方法)。"""
        baseline = KnowledgeBase.compute_baseline_from_labels(labels)
        return self.compute(baseline)
