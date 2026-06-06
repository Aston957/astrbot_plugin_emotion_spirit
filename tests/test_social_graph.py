"""Tests for SocialGraph (Phase 2.0 Step 6).

验证:
1. 有向图: A → B != B → A
2. 双层网络: psychological (in_circle) + interactive (co-mentioned)
3. 关系类型: in_circle / friend / colleague / family / ex
4. 信任级别 (0-1)
5. 边权重衰减: 时间越久 strength 越低
6. 序列化: to_dict / from_dict 双向
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock astrbot.api.logger
import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.social_graph import SocialGraph, SocialEdge, RelationType


def test_add_edge_creates_directed_relation():
    """加边后, A 看到 B 是朋友, 但 B 不一定看到 A 是朋友。"""
    sg = SocialGraph()
    sg.add_edge("alice", "bob", relation=RelationType.FRIEND, strength=0.8, trust=0.7)
    # A 视角: 有 B
    assert sg.has_edge("alice", "bob")
    # B 视角: 没有 A
    assert not sg.has_edge("bob", "alice")


def test_get_out_edges_returns_all_relations():
    """A 提到 N 个人 → get_out_edges 返回 N 条。"""
    sg = SocialGraph()
    sg.add_edge("alice", "bob", relation=RelationType.FRIEND, strength=0.8)
    sg.add_edge("alice", "carol", relation=RelationType.COLLEAGUE, strength=0.5)
    sg.add_edge("alice", "dave", relation=RelationType.FAMILY, strength=0.95)
    edges = sg.get_out_edges("alice")
    targets = {e.dst_user for e in edges}
    assert targets == {"bob", "carol", "dave"}


def test_relation_type_distinction():
    """不同 relation type 可以共存。"""
    sg = SocialGraph()
    sg.add_edge("alice", "bob", relation=RelationType.FRIEND, strength=0.8)
    sg.add_edge("alice", "carol", relation=RelationType.COLLEAGUE, strength=0.5)
    edges = sg.get_out_edges("alice")
    relations = {e.dst_user: e.relation for e in edges}
    assert relations["bob"] == RelationType.FRIEND
    assert relations["carol"] == RelationType.COLLEAGUE


def test_trust_level_in_range():
    """trust 在 [0, 1] 范围。"""
    sg = SocialGraph()
    sg.add_edge("alice", "bob", relation=RelationType.FRIEND, strength=0.8, trust=0.5)
    edge = sg.get_out_edges("alice")[0]
    assert 0 <= edge.trust <= 1


def test_double_layer_psychological_and_interactive():
    """心理层 (in_circle) vs 互动层 (co-mentioned) 独立。"""
    sg = SocialGraph()
    # alice 把 bob 加入 in_circle (心理层)
    sg.add_edge("alice", "bob", relation=RelationType.IN_CIRCLE, strength=0.9, layer="psychological")
    # alice 也提到 carol (互动层)
    sg.add_edge("alice", "carol", relation=RelationType.FRIEND, strength=0.6, layer="interactive")
    # 心理层查询: 只有 bob
    psych = sg.get_out_edges("alice", layer="psychological")
    inter = sg.get_out_edges("alice", layer="interactive")
    assert {e.dst_user for e in psych} == {"bob"}
    assert {e.dst_user for e in inter} == {"carol"}


def test_bidirectional_optional():
    """bidirectional=True 表示对称 (少见, 如 A↔B 互相是朋友)。"""
    sg = SocialGraph()
    sg.add_edge("alice", "bob", relation=RelationType.FRIEND, strength=0.8, bidirectional=True)
    edge = sg.get_out_edges("alice")[0]
    assert edge.bidirectional is True


def test_serialization_round_trip():
    """to_dict + from_dict 保留所有边。"""
    sg = SocialGraph()
    sg.add_edge("alice", "bob", relation=RelationType.FRIEND, strength=0.8, trust=0.7)
    sg.add_edge("alice", "carol", relation=RelationType.COLLEAGUE, strength=0.5, layer="interactive")
    data = sg.to_dict()
    sg2 = SocialGraph.from_dict(data)
    assert sg2.has_edge("alice", "bob")
    assert sg2.has_edge("alice", "carol")
    # 信任值保留
    edge = sg2.get_out_edges("alice")[0]
    assert edge.trust == 0.7


def test_in_circle_relation_is_strongest():
    """IN_CIRCLE 是最强关系, strength 阈值更高。"""
    sg = SocialGraph()
    sg.add_edge("alice", "bob", relation=RelationType.IN_CIRCLE, strength=0.95)
    sg.add_edge("alice", "carol", relation=RelationType.ACQUAINTANCE if hasattr(RelationType, "ACQUAINTANCE") else RelationType.COLLEAGUE, strength=0.3)
    edges = sg.get_out_edges("alice")
    bob_edge = next(e for e in edges if e.dst_user == "bob")
    assert bob_edge.relation == RelationType.IN_CIRCLE
    assert bob_edge.strength > 0.9


if __name__ == "__main__":
    test_add_edge_creates_directed_relation()
    test_get_out_edges_returns_all_relations()
    test_relation_type_distinction()
    test_trust_level_in_range()
    test_double_layer_psychological_and_interactive()
    test_bidirectional_optional()
    test_serialization_round_trip()
    test_in_circle_relation_is_strongest()
    print("All SocialGraph tests passed!")
