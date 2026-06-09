"""Phase 2.0 完整集成测试 (Step 8)。

跨模块验证:
1. per-user memory: 隔离 (A 不读 B 的)
2. social_graph: A 的关系图与 B 独立
3. topic_privacy: A 的隐私设置不影响 B
4. bot_decision: 综合所有组件做决策
5. 端到端流: 用户消息 → memory → 决策 → 输出
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
astrbot_api_mock.logger.debug = lambda *a, **kw: None
astrbot_api_mock.logger.error = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.memory.memory_pool import MemoryPool
from emotion_spirit.output.buffer_signals import BufferSignals
from emotion_spirit.regulation.pattern_extractor import PatternExtractor
from emotion_spirit.regulation.counterfactual import Counterfactual
from emotion_spirit.output.diary_writer import DiaryWriter
from emotion_spirit.output.narrative_identity import NarrativeIdentity
from emotion_spirit.output.prompt_injector import PromptInjector
from emotion_spirit.memory.social_graph import SocialGraph, RelationType
from emotion_spirit.memory.topic_privacy import TopicPrivacy, PrivacyLevel
from emotion_spirit.output.bot_decision import BotDecisionMaker


def test_e2e_per_user_memory_isolation():
    """端到端: 2 个 user 的 4 层记忆池完全隔离。"""
    pool = MemoryPool()
    # alice 添加 10 条
    for i in range(10):
        pool.add_for_user("alice", f"a_{i}", 0.5, 0.5, ["x"], "alice")
    # bob 添加 5 条
    for i in range(5):
        pool.add_for_user("bob", f"b_{i}", 0.5, 0.5, ["y"], "bob")
    # 隔离
    assert len(pool.buffer_for("alice")) == 10
    assert len(pool.buffer_for("bob")) == 5
    assert len(pool.user_ids()) == 2


def test_e2e_signals_isolated_across_users():
    """BufferSignals 在不同 user_id 下看到不同数据。"""
    pool = MemoryPool()
    for i in range(20):
        pool.add_for_user("alice", f"a_{i}", 0.9, 0.5, ["x"], "alice")
    # bob: 0
    sig_a = BufferSignals(pool, user_id="alice")
    sig_b = BufferSignals(pool, user_id="bob")
    # alice 温度高, bob 温度 0
    assert sig_a.buffer_temperature() > 0
    assert sig_b.buffer_temperature() == 0.0


def test_e2e_social_graph_directed_per_user():
    """每个 user 有自己的关系图, 互不影响。"""
    sg = SocialGraph()
    # alice 把 bob 加入 in_circle
    sg.add_edge("alice", "bob", relation=RelationType.IN_CIRCLE, strength=0.9)
    # carol 把 dave 加入 in_circle (alice 不知道 dave)
    sg.add_edge("carol", "dave", relation=RelationType.IN_CIRCLE, strength=0.9)
    # 隔离
    alice_circle = sg.get_in_circle("alice")
    carol_circle = sg.get_in_circle("carol")
    assert alice_circle == ["bob"]
    assert carol_circle == ["dave"]


def test_e2e_topic_privacy_per_user():
    """每个 user 的隐私设置独立。"""
    tp = TopicPrivacy()
    # alice 把 trauma 设为 private
    tp.set_privacy("alice", "trauma", PrivacyLevel.PRIVATE)
    # bob 把 trauma 设为 public
    tp.set_privacy("bob", "trauma", PrivacyLevel.PUBLIC)
    # 验证独立
    assert tp.get_privacy("alice", "trauma") == PrivacyLevel.PRIVATE
    assert tp.get_privacy("bob", "trauma") == PrivacyLevel.PUBLIC


def test_e2e_decision_combines_social_graph_and_privacy():
    """BotDecisionMaker 综合 social_graph + topic_privacy 做决策。"""
    sg = SocialGraph()
    tp = TopicPrivacy()
    # alice 把 bob 加入 in_circle
    sg.add_edge("alice", "bob", relation=RelationType.IN_CIRCLE, strength=0.9)
    # alice 把 family_secret 设为 circle
    tp.set_privacy("alice", "family_secret", PrivacyLevel.CIRCLE)
    # alice 把 trauma 设为 private
    tp.set_privacy("alice", "trauma", PrivacyLevel.PRIVATE)
    # alice 把 weather 设为 public
    tp.set_privacy("alice", "weather", PrivacyLevel.PUBLIC)

    dm = BotDecisionMaker(social_graph=sg, topic_privacy=tp, gossip_tendency=1.0)
    # public 话题: 任何人都可提
    assert dm.can_mention_topic("alice", "bob", "weather")
    # private 话题: 不可提
    assert not dm.can_mention_topic("alice", "bob", "trauma")
    # circle 话题 + bob 在 in_circle: 可提
    assert dm.can_mention_topic("alice", "bob", "family_secret")
    # circle 话题 + carol 不在 in_circle: 不可提
    assert not dm.can_mention_topic("alice", "carol", "family_secret")


def test_e2e_full_user_message_flow():
    """完整用户消息流: 写入 → buffer → 流转 → 决策。"""
    pool = MemoryPool()
    sg = SocialGraph()
    tp = TopicPrivacy()
    dm = BotDecisionMaker(social_graph=sg, topic_privacy=tp, gossip_tendency=1.0)

    # 1. alice 提到 bob (添加关系边 + 记忆)
    sg.add_edge("alice", "bob", relation=RelationType.FRIEND, strength=0.7, layer="interactive")
    pool.add_for_user("alice", "今天和 Bob 聊了", 0.5, 0.5, ["chitchat", "friend"], "alice")

    # 2. 流转到 warm
    pool.confirm_check_for_user("alice")
    alice_warm = pool.warm_for("alice")
    assert len(alice_warm) == 1
    assert "friend" in alice_warm[0].tags

    # 3. bot 决定对 carol 提 bob (gossip_tendency=1.0 + bob 在 social_graph)
    # can_mention_person: gossip_tendency >= 0.5 → True
    assert dm.can_mention_person("alice", "carol", "bob")


def test_e2e_forbid_hard_constraint_overrides():
    """用户明确禁止覆盖所有默认 (CPM 边界协调的硬约束)。"""
    tp = TopicPrivacy()
    dm = BotDecisionMaker(topic_privacy=tp, gossip_tendency=1.0)
    # 设置为 public
    tp.set_privacy("alice", "ex_relationship", PrivacyLevel.PUBLIC)
    # 验证 public → 可提
    assert dm.can_mention_topic("alice", "bob", "ex_relationship")
    # 明确禁止后 → 不可提
    tp.forbid_mention("alice", "ex_relationship")
    assert not dm.can_mention_topic("alice", "bob", "ex_relationship")


def test_e2e_aggregate_views_for_global_analytics():
    """聚合视图: Bot 自身感知 (跨用户)。"""
    pool = MemoryPool()
    for i in range(15):
        pool.add_for_user("alice", f"a_{i}", 0.02, 0.5, ["x"], "alice")
    for i in range(15):
        pool.add_for_user("bob", f"b_{i}", 0.02, 0.5, ["x"], "bob")
    # 聚合温度 vs 单 user 温度
    agg = BufferSignals.aggregate_temperature(pool)
    alice_only = BufferSignals(pool, user_id="alice").buffer_temperature()
    # 聚合 > 单 user (跨用户感知更强)
    assert agg > alice_only


if __name__ == "__main__":
    test_e2e_per_user_memory_isolation()
    test_e2e_signals_isolated_across_users()
    test_e2e_social_graph_directed_per_user()
    test_e2e_topic_privacy_per_user()
    test_e2e_decision_combines_social_graph_and_privacy()
    test_e2e_full_user_message_flow()
    test_e2e_forbid_hard_constraint_overrides()
    test_e2e_aggregate_views_for_global_analytics()
    print("All Phase 2.0 integration tests passed!")
