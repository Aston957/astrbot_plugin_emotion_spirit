"""Tests for dim consistency (Phase A, P0-1d 必做)。

防止 v1.7 (11→12 维) 的 dim 错位再次发生:
验证所有下游 dim 集合 ⊆ label_mapper 权威 13 维。

这些测试是 Phase A Task 3/4 (修 dim 错位) 的"二级保险" — 阻止 bug 复发。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_label_mapper_returns_13_dims():
    """v1.7.2: 5 deep + 8 surface (含 gossip_tendency) = 13。"""
    from emotion_spirit.label_mapper import (
        ALL_PERSONALITY_DIMS,
        PERSONALITY_DIMS_DEEP,
        PERSONALITY_DIMS_SURFACE,
    )
    assert len(PERSONALITY_DIMS_DEEP) == 5
    assert len(PERSONALITY_DIMS_SURFACE) == 8
    assert len(ALL_PERSONALITY_DIMS) == 13


def test_relationship_personality_all_dims_match_label_mapper():
    """P0-1a: ALL_DIMS 必须 = label_mapper.ALL_PERSONALITY_DIMS。

    防止 RelationshipPersonality 内部重复定义维度集合 (历史上曾有 11/12 维错位)。
    """
    from emotion_spirit.relationship_personality import ALL_DIMS
    from emotion_spirit.label_mapper import ALL_PERSONALITY_DIMS
    assert set(ALL_DIMS) == ALL_PERSONALITY_DIMS, (
        f"差集: {set(ALL_DIMS) ^ ALL_PERSONALITY_DIMS}"
    )


def test_intimacy_segment_tones_no_unknown_personality_dims():
    """P0-1b: 4 段 tone 的所有 dim 必须在 13 维人格集合内。

    防止 segment_tones 用 warmth 错名 (应是 warmth_bias) 或
    narrative_coherence (不是 personality dim) 等错位。
    """
    from emotion_spirit.intimacy import IntimacyTracker
    from emotion_spirit.label_mapper import ALL_PERSONALITY_DIMS

    tracker = IntimacyTracker()
    for user_id in ["test1", "test2", "test3", "test4"]:
        tone = tracker.get_relationship_tone(user_id)
        unknown = set(tone.keys()) - ALL_PERSONALITY_DIMS
        assert not unknown, f"{user_id} tone 含非 personality dim: {unknown}"
