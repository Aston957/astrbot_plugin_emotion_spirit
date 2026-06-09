"""Tests for TopicPrivacy (Phase 2.0 Step 6, CPM 理论).

验证:
1. 3 级隐私: private / circle / public
2. can_mention(user_a, user_b, topic) 边界检查
3. private: 永不提及
4. circle: 只在 in_circle 成员间提及
5. public: 可对任何人提及
6. 用户"明确禁止"覆盖: 任何 user 标记 private_forbid = 永不可提
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

from emotion_spirit.memory.topic_privacy import TopicPrivacy, PrivacyLevel
from emotion_spirit.memory.social_graph import SocialGraph, RelationType


def test_private_topic_never_mention():
    """private 话题: 任何 user 间都不可提及。"""
    tp = TopicPrivacy()
    tp.set_privacy("alice", "trauma_2024", PrivacyLevel.PRIVATE)
    # 即使 in_circle 内也不可
    assert not tp.can_mention("alice", "bob", "trauma_2024")
    assert not tp.can_mention("alice", "carol", "trauma_2024")


def test_circle_topic_mention_within_in_circle():
    """circle 话题: 只在 in_circle 成员间可提及。"""
    tp = TopicPrivacy()
    sg = SocialGraph()
    # alice 把 bob 加入 in_circle
    sg.add_edge("alice", "bob", relation=RelationType.IN_CIRCLE, strength=0.9, layer="psychological")
    tp.set_privacy("alice", "family_secret", PrivacyLevel.CIRCLE)
    # bob 在 in_circle → 可提
    assert tp.can_mention("alice", "bob", "family_secret", social_graph=sg)
    # carol 不在 in_circle → 不可提
    assert not tp.can_mention("alice", "carol", "family_secret", social_graph=sg)


def test_public_topic_mention_anyone():
    """public 话题: 可对任何人提及。"""
    tp = TopicPrivacy()
    tp.set_privacy("alice", "weather", PrivacyLevel.PUBLIC)
    assert tp.can_mention("alice", "bob", "weather")
    assert tp.can_mention("alice", "carol", "weather")


def test_default_privacy_is_private():
    """未设置的话题: 默认 private (保守)。"""
    tp = TopicPrivacy()
    assert tp.get_privacy("alice", "unknown_topic") == PrivacyLevel.PRIVATE


def test_user_explicit_forbid_overrides():
    """用户"明确禁止"覆盖任何默认: 一旦 forbid, 永不可提。"""
    tp = TopicPrivacy()
    tp.set_privacy("alice", "ex_relationship", PrivacyLevel.PUBLIC)
    tp.forbid_mention("alice", "ex_relationship")
    # 即使 public, forbid 后不可提
    assert not tp.can_mention("alice", "bob", "ex_relationship")


def test_can_mention_no_social_graph_treated_as_no_circle():
    """无 social_graph 时, circle 话题视为不可提 (除 bot 自己和 in_circle 假设)。"""
    tp = TopicPrivacy()
    tp.set_privacy("alice", "family_secret", PrivacyLevel.CIRCLE)
    # 没传 social_graph, 默认保守: 不可提
    assert not tp.can_mention("alice", "bob", "family_secret")


def test_in_circle_membership_includes_self():
    """in_circle 检查: 提及对象是 in_circle 成员即可, 无需反向。"""
    tp = TopicPrivacy()
    sg = SocialGraph()
    sg.add_edge("alice", "bob", relation=RelationType.IN_CIRCLE, strength=0.9, layer="psychological")
    tp.set_privacy("alice", "topic1", PrivacyLevel.CIRCLE)
    # bob 是 alice 视角的 in_circle → 可提
    assert tp.can_mention("alice", "bob", "topic1", social_graph=sg)
    # alice 自己提到自己也算 in_circle (退化为允许)
    # 这里不测试, 假设 bot 不会对自己提


def test_serialization_round_trip():
    """to_dict + from_dict 保留所有隐私设置。"""
    tp = TopicPrivacy()
    tp.set_privacy("alice", "topic_a", PrivacyLevel.PRIVATE)
    tp.set_privacy("alice", "topic_b", PrivacyLevel.CIRCLE)
    tp.forbid_mention("alice", "topic_c")
    data = tp.to_dict()
    tp2 = TopicPrivacy.from_dict(data)
    assert tp2.get_privacy("alice", "topic_a") == PrivacyLevel.PRIVATE
    assert tp2.get_privacy("alice", "topic_b") == PrivacyLevel.CIRCLE
    assert not tp2.can_mention("alice", "bob", "topic_c")


if __name__ == "__main__":
    test_private_topic_never_mention()
    test_circle_topic_mention_within_in_circle()
    test_public_topic_mention_anyone()
    test_default_privacy_is_private()
    test_user_explicit_forbid_overrides()
    test_can_mention_no_social_graph_treated_as_no_circle()
    test_in_circle_membership_includes_self()
    test_serialization_round_trip()
    print("All TopicPrivacy tests passed!")
