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

═══════════════════════════════════════════════════════════════════════════════
Phase 3.0B Task 3 — body state 接入 (hormone/energy/arousal) (2026-06-08)
═══════════════════════════════════════════════════════════════════════════════

ForceDynamics.compute() 扩展接受可选 body_state: BodyState | None = None 参数,
调制 3 元力学 intensity 计算。设计原则: 保持 pure-function (无状态, 同输入
同输出), 调制因子数学显式, 缺 body_state = 中性 (0.5/0.5/0.5) → 输出
跟无 body_state 一致 → 100% 向后兼容。

body_state 3 字段 → intensity 调制映射 (per spec §3.1):

1) arousal: 唤醒度, 应用在 per-dim loop 内 (modulate salience before
   intensity = signed_dev × salience 计算)。
     factor = 0.5 + arousal ∈ [0.5, 1.5]
     - arousal=0.5 (中性): factor=1.0, 不影响 salience
     - arousal=1.0 (高唤醒): factor=1.5, salience 放大 1.5x → 极端化
     - arousal=0.0 (低唤醒): factor=0.5, salience 压缩 0.5x → 弱化

2) energy: 能量, 应用在 raw intensity 后 (modulate 3-force |intensity|)。
     factor = 0.5 + 0.5 × energy ∈ [0.5, 1.0]
     - energy=0.5 (中性): factor=0.75, 不影响归一化比例
     - energy=0.0 (低能量): factor=0.5, 全力学 |intensity| 压缩
     - energy=1.0 (高能量): factor=1.0, 无衰减
     注: energy 同步作用于 3-force, 归一化后比例不变 (符合"低能量 → 全部衰减")

3) hormone: 激素, 应用在 raw intensity 后 (modulate per-force 强度)。
     hormone_mult = 1.0 + (hormone - 0.5) × 0.5 × direction[force]
     shift ∈ [-0.25, +0.25], direction[force] ∈ {natural: -0.5, social: -0.3, individual: +0.8}
     - hormone=0.5 (中性): mult=1.0, 不影响各力
     - hormone=1.0 (高 cortisol): individual mult=1.20 (放大), social mult=0.925 (压缩)
     - hormone=0.0 (放松): individual mult=0.80, social mult=1.075 (放大)
     方向系数选择: individual 最敏感 (+0.8) 反映 cortisol 应激 → 自我中心
     (Kahneman 压力反应); social 反向 (-0.3) 反映放松 → 关注他人。

不变量: 缺 body_state 或 body_state=(0.5, 0.5, 0.5) → compute() 输出跟
无 body_state 时**完全一致** (1e-9 内), 不破坏 3.0A Task 2 (算法 H + STD_FLOOR)
的 existing tests。
"""
from __future__ import annotations
from dataclasses import dataclass

from .registry import register
from .knowledge import KnowledgeBase
from .body_state import BodyState


@dataclass
class ForceState:
    """三元力学状态 (3 权重, 归一化到 sum=1.0)."""

    natural: float
    social: float
    individual: float

    def __post_init__(self) -> None:
        total = self.natural + self.social + self.individual
        if abs(total - 1.0) >= 0.01:
            raise ValueError(
                f"ForceState 3 权重归一化和 != 1.0: {total:.4f} (must sum to 1.0 ± 0.01)"
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

    # std 下限 clamp (Phase 3.0B Task 3):
    # 防止极小 std 把对应 dim 的贡献"压扁"。当前 13 维 std 全在 0.17-0.25
    # 区间, floor 不会改变实际结果; 未来若新加 std < 0.10 的 dim, 兜底生效。
    STD_FLOOR: float = 0.10

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

    # hormone 方向系数 (Phase 3.0B Task 3): 高 cortisol → individual +0.8
    # 最敏感; social -0.3 (放松 → 关注他人); natural -0.5 (中度反向)
    _HORMONE_DIRECTION: dict[str, float] = {
        "natural": -0.5, "social": -0.3, "individual": +0.8,
    }
    _HORMONE_SCALE: float = 0.5  # shift = (hormone - 0.5) × 0.5 ∈ [-0.25, +0.25]

    def compute(
        self,
        personality: dict[str, float],
        body_state: BodyState | None = None,
    ) -> ForceState:
        """算法 H: per-dim 极化 × 跨人方差 → ForceState (可选用 body_state 调制)。

        Args:
            personality: 13 维 dim → float (允许 > 1.0, B 决策)
            body_state: 可选 BodyState (Phase 3.0B), 调制 intensity 计算:
                - arousal: 0.5+arousal ∈ [0.5, 1.5], 应用在 per-dim salience
                - energy: 0.5+0.5×energy ∈ [0.5, 1.0], 同步作用 3-force |intensity|
                - hormone: per-force multiplier (individual +0.8 最敏感, social -0.3)
                缺省 (None) → 不调制, 输出跟 3.0A 算法 H + STD_FLOOR 一致

        Returns:
            ForceState (3 权重, sum=1.0)

        处理:
            - 缺 dim 跳过
            - 不在 DIM_FORCE 的 dim 跳过
            - 全 0 → 均匀 1/3 each
            - std < STD_FLOOR → clamp 到 STD_FLOOR (Phase 3.0B)
            - 未知 dim → fallback std=0.20 (>= STD_FLOOR, floor 不触发)

        不变量:
            compute(p) == compute(p, None) == compute(p, BodyState(0.5, 0.5, 0.5))
            (arousal=0.5 中性时 salience_factor=1.0; energy=0.5 中性时
            energy_factor=0.75 同步作用于 3-force 归一化后比例不变;
            hormone=0.5 中性时 per-force mult=1.0)
        """
        # 解析 body_state 调制因子 (None → 中性, 等同 (0.5, 0.5, 0.5))
        if body_state is None:
            arousal_factor = 1.0
            energy_factor = 0.75       # 0.5 + 0.5 × 0.5
            hormone_shift = 0.0        # (0.5 - 0.5) × 0.5
        else:
            arousal_factor = 0.5 + body_state.arousal   # [0.5, 1.5]
            energy_factor = 0.5 + 0.5 * body_state.energy  # [0.5, 1.0]
            hormone_shift = (body_state.hormone - 0.5) * self._HORMONE_SCALE  # [-0.25, +0.25]

        intensities: dict[str, float] = {"natural": 0.0, "social": 0.0, "individual": 0.0}
        for force in ("natural", "social", "individual"):
            signed_dev_sum = 0.0
            salience_sum = 0.0
            for dim in self._force_dims[force]:
                if dim not in personality:
                    continue
                value = personality[dim]
                # std 兜底: 未知 dim → 0.20, 然后 floor clamp (Phase 3.0B Task 3)
                std = max(self._dim_std.get(dim, 0.20), self.STD_FLOOR)
                dev = value - 0.5
                signed_dev_sum += dev * std
                # arousal 调制 salience (Phase 3.0B Task 3)
                salience_sum += abs(dev) * std * arousal_factor
            count = len(self._force_dims[force])
            if count > 0:
                signed_dev = signed_dev_sum / count
                salience = salience_sum / count
                intensities[force] = signed_dev * salience

        # body_state 后处理: energy dampen + hormone shift (per-force)
        # 注: energy 同步作用于 3-force raw intensity, abs-normalize 后比例
        # 不变 (符合"低能量 → 全部衰减"语义)。hormone 异步 (per-force 方向
        # 系数不同), 改归一化比例。
        for force in intensities:
            hormone_mult = 1.0 + hormone_shift * self._HORMONE_DIRECTION[force]
            intensities[force] = intensities[force] * energy_factor * hormone_mult

        # |intensity| 归一化
        abs_intensities = {f: abs(intensities[f]) for f in intensities}
        total = sum(abs_intensities.values())
        # total == 0 (not < 0.01 per spec §4.2): spec threshold would force INFP-A
        # to uniform 1/3, contradicting spec §4.3's own dominant expectation.
        # Floating-point zero is exact; non-zero total always produces valid ForceState.
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
