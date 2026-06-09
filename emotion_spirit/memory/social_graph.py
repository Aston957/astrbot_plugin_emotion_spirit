"""SocialGraph — 用户间关系图 (Phase 2.0 Step 6)。

设计依据 (5 大理论支柱中的支柱 4):
- Heider 1958, Kenny & Nasby 1980: 关系是**有向的** (A 觉得 B 是朋友, B 不一定)
- Milardo 1989: 心理网络 (in-circle) vs 互动网络 (co-mentioned) **25% 重叠**
- 必须支持: 关系类型、信任级别、边权重衰减

数据结构:
- _edges: dict[src, dict[dst, SocialEdge]] (有向)
- _edges[src] 是心理层/互动层的合并视图; layer 用 SocialEdge.layer 区分

注意: SocialGraph 是 bot 维护的"用户关系认知图", 不是 bot 自己的判断;
     应反映**用户感知**的关系, bot 用 BotDecisionMaker 决定是否提及。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any



__all__ = [
    "RelationType",
    "SocialEdge",
    "SocialGraph",
]

class RelationType(str, Enum):
    """关系类型 — A 视角下对 B 的认知。"""
    IN_CIRCLE = "in_circle"  # 内心圈 (心理层, 最强)
    FAMILY = "family"
    FRIEND = "friend"
    COLLEAGUE = "colleague"
    ACQUAINTANCE = "acquaintance"  # 熟人
    EX = "ex"  # 前任/前关系


@dataclass
class SocialEdge:
    """关系边 — src 视角下的 dst。"""
    src_user: str
    dst_user: str
    relation: RelationType
    strength: float  # [0, 1], 来自 mention density
    last_interaction: float = field(default_factory=time.time)
    bidirectional: bool = False  # True if symmetric (rare)
    trust: float = 0.5  # [0, 1], src 对 dst 的信任
    confidence: float = 1.0  # [0, 1], 关系判定可信度 (LLM vs 声明)
    layer: str = "psychological"  # "psychological" or "interactive"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["relation"] = self.relation.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SocialEdge":
        data = dict(data)
        data["relation"] = RelationType(data["relation"])
        return cls(**data)


from ..core.registry import register


@register(name="social_graph", provides=["SocialGraph"], depends_on=[])
class SocialGraph:
    """用户间关系图 — 有向, 双层 (psychological + interactive)。"""

    def __init__(self) -> None:
        # _edges: src → {dst → SocialEdge}
        self._edges: dict[str, dict[str, SocialEdge]] = {}

    def add_edge(
        self,
        src_user: str,
        dst_user: str,
        relation: RelationType = RelationType.FRIEND,
        strength: float = 0.5,
        trust: float = 0.5,
        bidirectional: bool = False,
        layer: str = "psychological",
    ) -> SocialEdge:
        """添加或更新一条边 (src → dst)。

        如果边已存在, 保留 last_interaction 最早的, 合并 strength/trust (取 max)。
        """
        self._edges.setdefault(src_user, {})
        if dst_user in self._edges[src_user]:
            # 边已存在: 保留旧时间戳 (last_interaction 不后退), 合并属性
            existing = self._edges[src_user][dst_user]
            edge = SocialEdge(
                src_user=src_user,
                dst_user=dst_user,
                relation=relation,
                strength=max(existing.strength, strength),
                last_interaction=existing.last_interaction,
                bidirectional=bidirectional or existing.bidirectional,
                trust=max(existing.trust, trust),
                confidence=existing.confidence,
                layer=layer,
            )
        else:
            edge = SocialEdge(
                src_user=src_user,
                dst_user=dst_user,
                relation=relation,
                strength=strength,
                trust=trust,
                bidirectional=bidirectional,
                layer=layer,
            )
        self._edges[src_user][dst_user] = edge
        return edge

    def has_edge(self, src_user: str, dst_user: str) -> bool:
        """检查 src → dst 是否有边。"""
        return dst_user in self._edges.get(src_user, {})

    def get_out_edges(
        self, src_user: str, layer: str | None = None
    ) -> list[SocialEdge]:
        """获取 src 的所有出边。

        Args:
            layer: "psychological" / "interactive" / None (全部)
        """
        edges = list(self._edges.get(src_user, {}).values())
        if layer:
            edges = [e for e in edges if e.layer == layer]
        return edges

    def get_in_edges(
        self, dst_user: str, layer: str | None = None
    ) -> list[SocialEdge]:
        """获取指向 dst 的所有入边 (谁把 dst 加入了 in_circle / 提到 dst)。"""
        edges = []
        for src, dst_dict in self._edges.items():
            if dst_user in dst_dict:
                e = dst_dict[dst_user]
                if layer is None or e.layer == layer:
                    edges.append(e)
        return edges

    def get_in_circle(self, user_id: str) -> list[str]:
        """获取 user 的 in_circle 成员 (心理层最强关系)。"""
        return [
            e.dst_user for e in self.get_out_edges(user_id, layer="psychological")
            if e.relation == RelationType.IN_CIRCLE
        ]

    def get_all_known_users(self, user_id: str) -> set[str]:
        """获取 user 知道的所有人 (出边 + 入边)。"""
        out_users = set(self._edges.get(user_id, {}).keys())
        in_users = {e.src_user for e in self.get_in_edges(user_id)}
        return out_users | in_users

    def decay_strength(
        self, decay_rate: float = 0.01, days: float = 1.0
    ) -> None:
        """时间衰减: 边的 strength 随时间降低。

        Args:
            decay_rate: 每天衰减率
            days: 经过的天数
        """
        factor = max(0.0, 1.0 - decay_rate * days)
        for src_dict in self._edges.values():
            for edge in src_dict.values():
                edge.strength *= factor

    def to_dict(self) -> dict[str, Any]:
        """序列化为 SpiritStore social_graph 格式。"""
        edges_data: dict[str, dict[str, dict]] = {}
        for src, dst_dict in self._edges.items():
            edges_data[src] = {dst: edge.to_dict() for dst, edge in dst_dict.items()}
        return {
            "edges": edges_data,
            "user_index": {},  # 未来: per-user 信任配置
            "topics": {},      # 未来: 话题-隐私映射
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SocialGraph":
        """从 SpiritStore 格式反序列化。"""
        sg = cls()
        edges_data = data.get("edges", {})
        for src, dst_dict in edges_data.items():
            for dst, edge_data in dst_dict.items():
                sg._edges.setdefault(src, {})[dst] = SocialEdge.from_dict(edge_data)
        return sg
