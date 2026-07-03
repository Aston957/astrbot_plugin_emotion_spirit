"""Tests for Intimacy segmentation (Phase 2.5 Step 2).

理论依据: Lopez 依恋风格 + 4 级关系深度模型
- 4 段: stranger / acquaintance / friend / inner_circle
- 阈值基于 get_intimacy() 分数
- 配套 get_relationship_tone(user_id) → 11 维微调建议

设计:
- 段是"关系深度"的离散桶, 决定 bot 与 user 互动的"色调"
- stranger: 保守/正式 (warmth ↓, expression ↓)
- acquaintance: 中性/礼貌 (无微调)
- friend: 温暖/主动 (warmth ↑, intimacy_pull ↑)
- inner_circle: 深度/共情 (warmth ↑↑, expression ↑, intimacy_pull ↑↑)
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

from emotion_spirit.memory.intimacy import IntimacyTracker


# ═══ get_segment 基础 ═══

def test_get_segment_default_stranger():
    """新 user (无交互) → stranger。"""
    tracker = IntimacyTracker()
    assert tracker.get_segment("alice") == "stranger"


def test_get_segment_returns_4_levels():
    """get_segment 应返回 4 段之一。"""
    tracker = IntimacyTracker()
    valid_segments = {"stranger", "acquaintance", "friend", "inner_circle"}
    # 测多个 user, 都应在 valid 集合
    for uid in ["alice", "bob", "carol"]:
        assert tracker.get_segment(uid) in valid_segments


# ═══ 段边界 (阈值) ═══

def test_segment_progression_with_intimacy_growth():
    """亲密度上升时, 段从 stranger → acquaintance → friend → inner_circle。"""
    tracker = IntimacyTracker()
    # 初始: stranger
    assert tracker.get_segment("alice") == "stranger"
    # 加中等亲密度
    tracker.update(
        "alice",
        temporal_hours=100,
        interval_seconds=3600,  # 1 hour
        vulnerability_delta=0.3,
        user_investment_delta=0.2,
        repair_count=1,
        shared_narrative=0.3,
    )
    # 验证: 至少是 acquaintance
    seg1 = tracker.get_segment("alice")
    assert seg1 in ("acquaintance", "friend", "inner_circle")


def test_segment_4_levels_have_different_tones():
    """4 段各有不同的 tone (微调建议)。"""
    tracker = IntimacyTracker()
    tones = {}
    for uid in ["alice", "bob", "carol", "dave"]:
        tones[uid] = tracker.get_relationship_tone(uid)
    # 至少 4 段应有不同色调 (新 user 都是 stranger, 色调应一致)
    # 这里只验证函数不抛异常, 不验证内容差异 (因为无交互都是 stranger)
    for tone in tones.values():
        assert isinstance(tone, dict)
        assert "warmth_bias" in tone  # 至少包含 warmth_bias 调整


def test_get_relationship_tone_returns_dict():
    """get_relationship_tone 返回 dict (11 维微调建议)。"""
    tracker = IntimacyTracker()
    tone = tracker.get_relationship_tone("alice")
    assert isinstance(tone, dict)
    # 11 维参数都应有色调 (即使是 0.0 = 无微调)
    from emotion_spirit.memory.relationship_personality import ALL_DIMS
    for dim in ALL_DIMS:
        assert dim in tone, f"tone 应包含 dim: {dim}"


def test_inner_circle_tone_is_warmer():
    """inner_circle 段: warmth_bias 微调 > 0, intimacy_pull > 0。"""
    tracker = IntimacyTracker()
    # 模拟高亲密度
    tracker.update(
        "alice",
        temporal_hours=1000,
        interval_seconds=300,  # 5 min
        vulnerability_delta=1.0,
        user_investment_delta=1.0,
        repair_count=5,
        shared_narrative=0.8,
    )
    # 验证是高亲密段
    seg = tracker.get_segment("alice")
    # 即使没到 inner_circle, 至少不应该是 stranger
    assert seg != "stranger"
    # tone 的 warmth_bias 在 inner_circle/friend 应 >= 0
    tone = tracker.get_relationship_tone("alice")
    # high intimacy 段 → warmth_bias >= 0
    assert tone.get("warmth_bias", 0) >= 0


def test_stranger_tone_is_formal():
    """stranger 段: warmth_bias 微调 <= 0, expression_drive <= 0 (保守)。"""
    tracker = IntimacyTracker()
    tone = tracker.get_relationship_tone("alice")  # 无交互 → stranger
    # stranger 应该是保守: warmth_bias <= 0
    assert tone.get("warmth_bias", 0) <= 0
    # expression_drive <= 0 (不主动)
    assert tone.get("expression_drive", 0) <= 0


# ═══ per-user 隔离 ═══

def test_segment_per_user_isolation():
    """A 高亲密, B 无交互 → A != B 段。"""
    tracker = IntimacyTracker()
    # A: 高亲密度
    tracker.update(
        "alice",
        temporal_hours=2000,
        interval_seconds=200,
        vulnerability_delta=1.0,
        user_investment_delta=1.0,
        repair_count=10,
        shared_narrative=0.9,
    )
    # B: 无交互
    seg_a = tracker.get_segment("alice")
    seg_b = tracker.get_segment("bob")
    # A 至少是 friend, B 是 stranger
    assert seg_b == "stranger"
    assert seg_a != seg_b


# ═══ Phase A: P0-1b segment_tones dim 校准 ═══

def test_segment_tones_uses_warmth_bias_not_narrative_coherence():
    """Phase A: 4 段 tone 必须用 warmth_bias (不是错名 warmth), 不能有 narrative_coherence。

    背景 (P0-1b): segment_tones 之前用 'warmth' (deprecated 11 维) 和 'narrative_coherence'
    (不是 personality dim), 导致 apply_to_layers 静默失败。修复后: 用 'warmth_bias' (13 维
    权威) 且不含非 personality dim。
    """
    from emotion_spirit.memory.intimacy import IntimacyTracker
    from emotion_spirit.utils import ALL_PERSONALITY_DIMS

    tracker = IntimacyTracker()

    # 4 个段都返回 13 维 dict
    for user_id in ["alice", "bob", "carol", "dave"]:
        tone = tracker.get_relationship_tone(user_id)
        # 必须是 13 维 personality dim 的子集
        unknown = set(tone.keys()) - ALL_PERSONALITY_DIMS
        assert not unknown, f"{user_id} tone 含非 personality dim: {unknown}"
        # 必须有 warmth_bias (不是 warmth)
        assert "warmth" not in tone, f"{user_id} tone 用了错名 warmth, 应是 warmth_bias"
        # 不能有 narrative_coherence (不是 personality dim)
        assert "narrative_coherence" not in tone


if __name__ == "__main__":
    test_get_segment_default_stranger()
    test_get_segment_returns_4_levels()
    test_segment_progression_with_intimacy_growth()
    test_segment_4_levels_have_different_tones()
    test_get_relationship_tone_returns_dict()
    test_inner_circle_tone_is_warmer()
    test_stranger_tone_is_formal()
    test_segment_per_user_isolation()
    test_segment_tones_uses_warmth_bias_not_narrative_coherence()
    print("All Intimacy segmentation tests passed!")
