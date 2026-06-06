"""Tests for BotDecisionMaker stub (Phase 2.0 Step 7).

验证:
1. 默认保守: can_mention_person 永远 False (gossip_tendency=0.0)
2. 永不提及自己
3. can_mention_topic 委托 TopicPrivacy
4. should_initiate_proactive 永远 False
5. Phase 4 接入点: set_gossip_tendency 调整参数
6. 决策日志: get_recent_decisions
"""

import sys
import os

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

from emotion_spirit.bot_decision import BotDecisionMaker
from emotion_spirit.topic_privacy import TopicPrivacy, PrivacyLevel


def test_default_can_mention_person_is_false():
    """默认 gossip_tendency=0, 保守: 永不主动提人。"""
    dm = BotDecisionMaker()
    assert not dm.can_mention_person("alice", "bob", "carol")


def test_can_mention_self_is_false():
    """提及对象 = 听众自己 → 永远 False。"""
    dm = BotDecisionMaker()
    # 即使 gossip_tendency 拉满, 也不能提听众自己
    dm.set_gossip_tendency(1.0)
    assert not dm.can_mention_person("alice", "bob", "bob")


def test_set_gossip_tendency_enables_decision():
    """Phase 4 接入点: gossip_tendency >= 0.5 才允许提人。"""
    dm = BotDecisionMaker()
    # 默认 False
    assert not dm.can_mention_person("alice", "bob", "carol")
    # 拉到 0.6 → True
    dm.set_gossip_tendency(0.6)
    assert dm.can_mention_person("alice", "bob", "carol")
    # 边界: 0.5 → True
    dm.set_gossip_tendency(0.5)
    assert dm.can_mention_person("alice", "bob", "carol")
    # 边界: 0.4 → False
    dm.set_gossip_tendency(0.4)
    assert not dm.can_mention_person("alice", "bob", "carol")


def test_gossip_tendency_clamped_to_0_1():
    """gossip_tendency 在 [0, 1] 范围 (越界 clamp)。"""
    dm = BotDecisionMaker()
    dm.set_gossip_tendency(2.0)
    assert dm.get_gossip_tendency() == 1.0
    dm.set_gossip_tendency(-0.5)
    assert dm.get_gossip_tendency() == 0.0


def test_can_mention_topic_delegates_to_topic_privacy():
    """can_mention_topic 委托 TopicPrivacy.can_mention。"""
    tp = TopicPrivacy()
    tp.set_privacy("alice", "public_topic", PrivacyLevel.PUBLIC)
    dm = BotDecisionMaker(topic_privacy=tp)
    # public 话题 → 可提
    assert dm.can_mention_topic("alice", "bob", "public_topic")
    # 未设置 → private 默认 → 不可提
    assert not dm.can_mention_topic("alice", "bob", "unknown_topic")


def test_can_mention_topic_no_topic_privacy_conservative():
    """无 TopicPrivacy: can_mention_topic 永远 False (保守)。"""
    dm = BotDecisionMaker(topic_privacy=None)
    assert not dm.can_mention_topic("alice", "bob", "any_topic")


def test_should_initiate_proactive_always_false():
    """Phase 2.0: should_initiate_proactive 永远 False (等用户先说)。"""
    dm = BotDecisionMaker()
    assert not dm.should_initiate_proactive()
    # 即使 gossip_tendency 拉满, 主动发起仍为 False
    dm.set_gossip_tendency(1.0)
    assert not dm.should_initiate_proactive()


def test_decision_log_records_calls():
    """get_recent_decisions 返回最近 N 条。"""
    dm = BotDecisionMaker()
    dm.can_mention_person("alice", "bob", "carol")
    dm.can_mention_person("alice", "bob", "dave")
    dm.can_mention_topic("alice", "bob", "topic1")
    decisions = dm.get_recent_decisions(n=10)
    assert len(decisions) == 3
    # 类型记录
    types = {d["type"] for d in decisions}
    assert "can_mention_person" in types
    assert "can_mention_topic" in types


if __name__ == "__main__":
    test_default_can_mention_person_is_false()
    test_can_mention_self_is_false()
    test_set_gossip_tendency_enables_decision()
    test_gossip_tendency_clamped_to_0_1()
    test_can_mention_topic_delegates_to_topic_privacy()
    test_can_mention_topic_no_topic_privacy_conservative()
    test_should_initiate_proactive_always_false()
    test_decision_log_records_calls()
    print("All BotDecisionMaker tests passed!")
