"""PersonalityBridge — 5D Embodiment ↔ 12D personality 双向映射。

SylannEngine 的 5D Embodiment:
  - expression_drive, perception_acuity, boundary_permeability,
    inner_coherence, relational_gravity

emotion_spirit 的 12D personality:
  Deep (6): relational_autonomy, exploration_openness, perception_acuity,
            boundary_permeability, inner_coherence, relational_gravity
  Surface (7): expression_drive, warmth_bias, directness, curiosity,
               patience, intimacy_pull, autonomy_guard

映射规则:
  - expression_drive → 拆分为 relational_autonomy + exploration_openness
  - 其余 4 个直接映射
  - 7 个 KB 管理的 surface 维度独立, 不从 5D 推导

参考: MERGER_PLAN §3.3 人格双轨映射
"""

from __future__ import annotations

__all__ = ["PersonalityBridge"]

# 5D Embodiment 维度名
EMBODIMENT_DIMS = (
    "expression_drive",
    "perception_acuity",
    "boundary_permeability",
    "inner_coherence",
    "relational_gravity",
)

# 直接映射: 5D → 12D (不拆分的维度)
_DIRECT_MAP = {
    "perception_acuity": "perception_acuity",
    "boundary_permeability": "boundary_permeability",
    "inner_coherence": "inner_coherence",
    "relational_gravity": "relational_gravity",
}

# expression_drive 拆分权重
# 基于 v1.7 设计: autonomy_guard → relational_autonomy + exploration_openness
_SPLIT_WEIGHTS = {
    "relational_autonomy": 0.6,    # 关系中的自主性 (偏向"守")
    "exploration_openness": 0.4,   # 探索开放性 (偏向"攻")
}

# 默认值
_DEFAULT = 0.5


class PersonalityBridge:
    """5D ↔ 12D 人格映射器。"""

    @staticmethod
    def map_5d_to_12d(embodiment_5d: dict[str, float]) -> dict[str, float]:
        """5D Embodiment → 12D personality deep 层。

        Args:
            embodiment_5d: SylannEngine 的 5 维人格参数。

        Returns:
            12D deep 层的 6 个维度 (不含 KB 管理的 surface 维度)。
        """
        result: dict[str, float] = {}

        # 直接映射 4 个维度 (clamp 到 [0, 1])
        for engine_dim, spirit_dim in _DIRECT_MAP.items():
            result[spirit_dim] = max(0.0, min(1.0, float(embodiment_5d.get(engine_dim, _DEFAULT))))

        # expression_drive 拆分
        expr_drive = float(embodiment_5d.get("expression_drive", _DEFAULT))
        for dim, weight in _SPLIT_WEIGHTS.items():
            result[dim] = max(0.0, min(1.0, expr_drive * weight + _DEFAULT * (1 - weight)))

        return result

    @staticmethod
    def map_12d_to_5d(personality_12d: dict[str, float]) -> dict[str, float]:
        """12D personality → 5D Embodiment (反向映射, 用于引擎反馈)。

        Args:
            personality_12d: emotion_spirit 的 12 维人格参数 (可以是 deep+surface 合并)。

        Returns:
            SylannEngine 的 5 维人格参数。
        """
        result: dict[str, float] = {}

        # 直接映射 4 个维度 (反向)
        for engine_dim, spirit_dim in _DIRECT_MAP.items():
            result[engine_dim] = float(personality_12d.get(spirit_dim, _DEFAULT))

        # expression_drive: 从 relational_autonomy + exploration_openness 重建
        rel_autonomy = float(personality_12d.get("relational_autonomy", _DEFAULT))
        expl_openness = float(personality_12d.get("exploration_openness", _DEFAULT))
        # 加权平均, 权重与拆分权重对称
        result["expression_drive"] = max(0.0, min(1.0,
            rel_autonomy * _SPLIT_WEIGHTS["relational_autonomy"]
            + expl_openness * _SPLIT_WEIGHTS["exploration_openness"]
        ))

        # 如果有 surface 层的 expression_drive, 优先使用
        if "expression_drive" in personality_12d:
            result["expression_drive"] = float(personality_12d["expression_drive"])

        return result

    @staticmethod
    def merge_deep_surface(
        deep: dict[str, float],
        surface: dict[str, float],
    ) -> dict[str, float]:
        """合并 deep 和 surface 层为完整的 12D personality dict。

        用于 map_12d_to_5d() 的输入准备。
        """
        merged = dict(deep)
        merged.update(surface)
        return merged
