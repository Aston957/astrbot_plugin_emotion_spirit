"""反事实模拟 — 为幽灵提供替代路径。

ghost 形成 ≥ 2 周 + sensitivity ≥ 0.25 → LLM 生成三个视角。
幽灵消化: 修复经验降低 sensitivity。
幽灵共振: 新条目标签和幽灵匹配 → 权重放大。
"""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .memory_pool import MemoryPool, MemoryEntry


_PERSPECTIVES = {
    "earlier": "如果更早注意到这个情况，结果会有什么不同?",
    "different": "如果用不同的方式处理，会怎么样?",
    "witness": "作为一个旁观者，你会怎么看这件事?",
}


from .registry import register



__all__ = [
    "Counterfactual",
]

@register(
    name="counterfactual",
    provides=["Counterfactual"],
    depends_on=["memory_pool"],
    param_wire={"memory_pool": "pool"},
)
class Counterfactual:
    """反事实模拟器。"""

    def __init__(self, pool: MemoryPool) -> None:
        self._pool = pool
        self._processed_ghosts: list[dict[str, Any]] = []

    def get_eligible_ghosts(self, user_id: str = "<global>") -> list[MemoryEntry]:
        """获取可以进行反事实模拟的幽灵。

        Args:
            user_id: Phase 2.0, 哪个 user 的 ghosts 池
        """
        now = time.time()
        two_weeks = 14 * 86400
        eligible = []

        for ghost in self._pool.ghosts_for(user_id):
            age = now - ghost.created_at
            if age >= two_weeks and ghost.ghost_sensitivity_shift >= 0.25:
                eligible.append(ghost)

        return eligible

    def build_counterfactual_prompt(self, ghost: MemoryEntry) -> str:
        """构建反事实 prompt。"""
        parts = [
            f"关于这件事: {ghost.text}",
            f"这件事的情感权重: {ghost.emotional_weight:.2f}",
            f"标签: {', '.join(ghost.tags)}",
            "",
        ]

        for perspective, question in _PERSPECTIVES.items():
            parts.append(f"[{perspective}] {question}")

        parts.append("")
        parts.append("请从这三个视角分别写 1-2 句话。不要提及你是AI。")

        return "\n".join(parts)

    def record_counterfactual(
        self,
        ghost_id: str,
        perspectives: dict[str, str],
    ) -> dict[str, Any]:
        """记录一个反事实模拟结果。"""
        result = {
            "ghost_id": ghost_id,
            "perspectives": perspectives,
            "timestamp": time.time(),
        }
        self._processed_ghosts.append(result)
        return result

    def check_ghost_decay(self, repair_count: int, user_id: str = "<global>") -> list[dict[str, Any]]:
        """检查幽灵消化。修复经验可以消化幽灵。

        Args:
            user_id: Phase 2.0, 哪个 user 的 ghosts/cold 池
        """
        digested: list[dict[str, Any]] = []

        ghosts = self._pool.ghosts_for(user_id)
        cold = self._pool.cold_for(user_id)
        for ghost in list(ghosts):
            ghost.ghost_sensitivity_shift *= (1 - repair_count * 0.1)
            if ghost.ghost_sensitivity_shift < 0.05:
                # 幽灵安息: 降级为冷池记忆
                ghost.is_ghost = False
                ghost.tier = "cold"
                ghosts.remove(ghost)
                cold.append(ghost)
                digested.append({
                    "ghost_id": ghost.id,
                    "text": ghost.text,
                    "tags": ghost.tags,
                })

        return digested

    def ghost_resonance(self, new_entry: MemoryEntry, user_id: str = "<global>") -> float:
        """幽灵共振: 新记忆和幽灵匹配 → 权重放大。

        Args:
            user_id: Phase 2.0, 哪个 user 的 ghosts 池
        """
        resonance_boost = 0.0
        for ghost in self._pool.ghosts_for(user_id):
            overlap = set(new_entry.tags) & set(ghost.tags)
            if overlap:
                resonance_boost += ghost.emotional_weight * len(overlap) * 0.1

        return resonance_boost

    def to_dict(self) -> dict[str, Any]:
        return {"processed_ghosts": self._processed_ghosts[-50:]}

    def from_dict(self, data: dict[str, Any]) -> None:
        self._processed_ghosts = data.get("processed_ghosts", [])
