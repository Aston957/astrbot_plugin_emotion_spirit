"""RelationshipPersonality — per-user 11 维人格微调 (Phase 2.5 Step 1)。

理论依据: Bowlby 内部工作模型 per-relationship
- 同一个 bot 对不同 user 展示不同"面"
- 11 维 base personality 不变, per-user delta 累加
- 每次读时合成 effective_personality (base + delta_for_user)
- delta 范围 [-0.3, 0.3]: 微调不应剧烈改变人格

数据结构:
- _deltas: dict[user_id, dict[dim_name, accumulated_value]]
- apply_to(base, user_id) 返回新 dict (不修改 base)

11 维人格参数 (与 label_mapper 对齐):
- warmth, autonomy, intimacy_pull, expression_drive, conscience_pressure
- relational_autonomy, exploration_openness
- shadow_suppression, narrative_coherence
- value_resistance, drift_pull
"""

from __future__ import annotations

import copy
from typing import Any


# Delta 累加范围 (微调应小)
_DELTA_MIN = -0.3
_DELTA_MAX = 0.3

# 11 维人格参数 (Phase 1.7 后的全量)
ALL_DIMS = (
    "warmth",
    "autonomy",
    "intimacy_pull",
    "expression_drive",
    "conscience_pressure",
    "relational_autonomy",
    "exploration_openness",
    "shadow_suppression",
    "narrative_coherence",
    "value_resistance",
    "drift_pull",
)


class RelationshipPersonality:
    """per-user 11 维人格微调。

    每次与 user 互动, bot 可以"调整"对这位 user 的微调面 (set_delta)。
    读取时, apply_to(base, user_id) 返回合成后的 effective_personality。
    """

    def __init__(self) -> None:
        # _deltas[user_id][dim] = accumulated_value (clamped to [_DELTA_MIN, _DELTA_MAX])
        self._deltas: dict[str, dict[str, float]] = {}

    def get_delta(self, user_id: str) -> dict[str, float]:
        """获取 user 的所有 dim delta 副本 (修改不影响内部状态)。"""
        return dict(self._deltas.get(user_id, {}))

    def get_single_delta(self, user_id: str, dim: str) -> float:
        """获取 user 单个 dim 的 delta (无记录返回 0.0)。"""
        return self._deltas.get(user_id, {}).get(dim, 0.0)

    def set_delta(self, user_id: str, dim: str, value: float) -> None:
        """累加 user 在某 dim 的 delta (非覆盖)。

        Args:
            user_id: 目标 user
            dim: 11 维参数名
            value: 本次累加值 (正负, 累加后 clamp 到 [-0.3, 0.3])
        """
        self._deltas.setdefault(user_id, {})
        current = self._deltas[user_id].get(dim, 0.0)
        new_value = max(_DELTA_MIN, min(_DELTA_MAX, current + value))
        self._deltas[user_id][dim] = new_value

    def reset_delta(self, user_id: str, dim: str | None = None) -> None:
        """重置 user 的 delta。

        Args:
            dim: None = 重置所有 dim, str = 仅重置该 dim
        """
        if user_id not in self._deltas:
            return
        if dim is None:
            del self._deltas[user_id]
        else:
            self._deltas[user_id].pop(dim, None)
            if not self._deltas[user_id]:
                del self._deltas[user_id]

    def apply_to(
        self,
        base_personality: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        """合成 effective_personality = base + delta_for_user。

        Args:
            base_personality: 11 维 base 格式 {"personality": {dim: {"baseline": x, "current": y}}}
            user_id: 目标 user (其 delta 将叠加)

        Returns:
            新 dict, 不修改 base_personality

        行为:
        - 无 delta 时: 返回 deep copy of base (避免外部修改影响)
        - 有 delta 时: 临时合成 current = clamp(base + delta, [0, 1])
        """
        # Deep copy 保证不修改 base
        effective = copy.deepcopy(base_personality)
        user_delta = self._deltas.get(user_id)
        if not user_delta:
            return effective

        personality = effective.get("personality", {})
        for dim, delta in user_delta.items():
            if dim in personality:
                base_current = personality[dim].get("current", 0.0)
                new_current = max(0.0, min(1.0, base_current + delta))
                personality[dim]["current"] = new_current
        return effective

    def list_users_with_deltas(self) -> list[str]:
        """列出有 delta 记录的所有 user。"""
        return list(self._deltas.keys())

    def to_dict(self) -> dict[str, Any]:
        """序列化为 SpiritStore 兼容格式。"""
        return {
            "deltas": {
                user_id: dict(dims) for user_id, dims in self._deltas.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RelationshipPersonality":
        """从 SpiritStore 格式反序列化。"""
        rp = cls()
        deltas = data.get("deltas", {})
        for user_id, dims in deltas.items():
            for dim, value in dims.items():
                # 跳过 range 校验, 直接设 (避免迁移时被 clamp 掉)
                rp._deltas.setdefault(user_id, {})[dim] = value
        return rp
