"""RelationshipPersonality — per-user 11 维人格微调 (Phase 2.5 Step 1)。

理论依据: Bowlby 内部工作模型 per-relationship
- 同一个 bot 对不同 user 展示不同"面"
- 11 维 base personality 不变, per-user delta 累加
- 每次读时合成 effective_personality (base + delta_for_user)
- delta 范围 [-0.3, 0.3]: 微调不应剧烈改变人格

数据结构:
- _deltas: dict[user_id, dict[dim_name, accumulated_value]]
- apply_to_layers(layers, user_id) 返回新 dict (不修改 layers)

11 维人格参数 (与 label_mapper 对齐):
- warmth, autonomy, intimacy_pull, expression_drive, conscience_pressure
- relational_autonomy, exploration_openness
- shadow_suppression, narrative_coherence
- value_resistance, drift_pull
"""

from __future__ import annotations

import copy
from typing import Any

from .label_mapper import ALL_PERSONALITY_DIMS


# Delta 累加范围 (微调应小)
_DELTA_MIN = -0.3
_DELTA_MAX = 0.3

# v1.7.2: ALL_DIMS 改为引用 label_mapper 权威集合 (13 维)
# 单一真相: label_mapper.ALL_PERSONALITY_DIMS = 5 deep + 8 surface
# 之前 hardcoded 11 维 (含 warmth/autonomy/conscience_pressure/shadow_suppression/
# narrative_coherence/value_resistance/drift_pull) 是 12 维 SylannEngine 的子集
# 且漏掉 gossip_tendency (v1.7.2 新增)
ALL_DIMS: tuple[str, ...] = tuple(sorted(ALL_PERSONALITY_DIMS))


class RelationshipPersonality:
    """per-user 11 维人格微调。

    每次与 user 互动, bot 可以"调整"对这位 user 的微调面 (set_delta)。
    读取时, apply_to_layers(layers, user_id) 返回合成后的 effective_personality。
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

    def apply_to_layers(
        self,
        layers: dict[str, dict[str, float]],
        user_id: str,
    ) -> dict[str, dict[str, float]]:
        """Phase 2.5 集成: 应用 delta 到 layer 格式 (deep/surface)。

        Args:
            layers: 格式 {"deep": {dim: val}, "surface": {dim: val}}
            user_id: 目标 user

        Returns:
            新 dict (不修改 layers), 每个 layer 的每个 dim += delta
        """
        effective = copy.deepcopy(layers)
        user_delta = self._deltas.get(user_id)
        if not user_delta:
            return effective

        for layer_name, layer in effective.items():
            if not isinstance(layer, dict):
                continue
            for dim, delta in user_delta.items():
                if dim in layer:
                    base_val = layer[dim]
                    new_val = max(0.0, min(1.0, base_val + delta))
                    layer[dim] = new_val
        return effective

    def apply_tone(
        self,
        user_id: str,
        tone: dict[str, float],
    ) -> None:
        """Phase 2.5 集成: 应用 IntimacyTracker.get_relationship_tone() 返回的色调。

        把 tone dict 的所有值累加到 user 的 delta (不覆盖既有 delta)。

        Args:
            user_id: 目标 user
            tone: 11 维色调 dict, 如 {"warmth": 0.1, "expression_drive": 0.05, ...}
        """
        for dim, value in tone.items():
            self.set_delta(user_id, dim, value)

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
