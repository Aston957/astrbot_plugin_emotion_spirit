"""Tests for KnowledgeBase Step 1 (label_mapper 全量迁移, 155 项)。

Step 1 范围:
  - 13 维 personality 权威集合
  - 5 persona baseline (含 gossip_tendency)
  - 5 轴标签 delta (mbti/attachment/emotion_style/conflict_style/time_focus)
  - 数值阈值 (intimacy_segments, lifecycle, buffer, regression 等)
  - 统一查询 API: get_persona_baseline / get_delta_for_label / get_threshold
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_knowledge_base_exposes_personality_baselines():
    """Step 1: KnowledgeBase.PERSONA_BASELINES 必须含 5 persona baseline。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert hasattr(KnowledgeBase, "PERSONA_BASELINES")
    assert len(KnowledgeBase.PERSONA_BASELINES) == 5
    for persona in ["INFP-A", "ISTJ-S", "ENTP-AV", "ISFJ-D", "ESTP-A"]:
        assert persona in KnowledgeBase.PERSONA_BASELINES


def test_knowledge_base_exposes_mbti_letter_deltas():
    """Step 1: KnowledgeBase.MBTI_LETTER_DELTAS 暴露 8 字母 delta (I/E/N/S/F/T/P/J)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    for letter in ["I", "E", "N", "S", "F", "T", "P", "J"]:
        assert letter in KnowledgeBase.MBTI_LETTER_DELTAS


def test_knowledge_base_get_delta_for_label_dispatches_correctly():
    """Step 1: get_delta_for_label('mbti', 'I') 返回 I 的 dim delta。"""
    from emotion_spirit.knowledge import KnowledgeBase
    i_delta = KnowledgeBase.get_delta_for_label("mbti", "I")
    assert "warmth_bias" in i_delta
    assert i_delta["warmth_bias"] < 0  # I 偏冷


def test_knowledge_base_get_persona_baseline_returns_copy():
    """Step 1: get_persona_baseline 返回 dict 副本, 修改不影响原数据。"""
    from emotion_spirit.knowledge import KnowledgeBase
    baseline = KnowledgeBase.get_persona_baseline("INFP-A")
    baseline["gossip_tendency"] = 999  # 不应影响原数据
    fresh = KnowledgeBase.get_persona_baseline("INFP-A")
    assert fresh["gossip_tendency"] != 999


def test_knowledge_base_thresholds_include_intimacy_segments():
    """Step 1: THRESHOLDS.intimacy_segments 是 4 段阈值 tuple。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert KnowledgeBase.THRESHOLDS["intimacy_segments"] == (0.65, 0.40, 0.15, 0.0)


def test_knowledge_base_get_threshold_supports_mixed_types():
    """get_threshold 必须支持 19 个不同类型 threshold (int/float/tuple) 不出错。"""
    from emotion_spirit.knowledge import KnowledgeBase
    # tuple (4 段阈值)
    segments = KnowledgeBase.get_threshold("intimacy_segments")
    assert isinstance(segments, tuple) and len(segments) == 4
    # int (数字)
    assert isinstance(KnowledgeBase.get_threshold("buffer_capacity"), int)
    # float (比率)
    rate = KnowledgeBase.get_threshold("deep_regression_rate")
    assert isinstance(rate, float) and 0 < rate < 1


def test_knowledge_base_get_threshold_raises_on_unknown():
    """get_threshold 未知 name 抛 KeyError, 含 name 提示。"""
    from emotion_spirit.knowledge import KnowledgeBase
    with pytest.raises(KeyError, match="未知阈值"):
        KnowledgeBase.get_threshold("nonexistent_threshold_xyz")


@pytest.mark.xfail(reason="KB 与 label_mapper 数据漂移, B3 (Task B3) 决策后回归", strict=False)
def test_knowledge_base_5_persona_baseline_shared_dims_match_label_mapper():
    """B1 已知数据漂移, 5 shared surface dim (warmth_bias/intimacy_pull/relational_autonomy/exploration_openness/gossip_tendency)
    应该在 KB.PERSONA_BASELINES 和 label_mapper.PERSONA_BASELINES 之间一致。

    当前 (B1) 3 persona (INFP-A/ISFJ-D/ENTP-AV) gossip_tendency 漂移:
    - INFP-A: KB 0.30 vs 旧 0.15
    - ISFJ-D: KB 0.40 vs 旧 0.15
    - ENTP-AV: KB 0.65 vs 旧 0.70
    - ISTJ-S/ESTP-A 一致

    B3 (Task B3) 删旧字段时会强制统一, 届时本测试应从 xfail → pass。
    """
    from emotion_spirit.knowledge import KnowledgeBase
    from emotion_spirit.label_mapper import PERSONA_BASELINES as OLD

    shared_dims = ["warmth_bias", "intimacy_pull", "relational_autonomy", "exploration_openness", "gossip_tendency"]
    for persona in ["INFP-A", "ISTJ-S", "ENTP-AV", "ISFJ-D", "ESTP-A"]:
        for dim in shared_dims:
            kb_val = KnowledgeBase.PERSONA_BASELINES[persona][dim]
            old_val = OLD[persona][dim]
            assert kb_val == old_val, (
                f"{persona}.{dim} 漂移: KB={kb_val}, label_mapper={old_val}"
            )


if __name__ == "__main__":
    test_knowledge_base_exposes_personality_baselines()
    test_knowledge_base_exposes_mbti_letter_deltas()
    test_knowledge_base_get_delta_for_label_dispatches_correctly()
    test_knowledge_base_get_persona_baseline_returns_copy()
    test_knowledge_base_thresholds_include_intimacy_segments()
    test_knowledge_base_get_threshold_supports_mixed_types()
    test_knowledge_base_get_threshold_raises_on_unknown()
    print("\n[OK] KnowledgeBase Step 1: 7/7 tests passed (parity test xfail via pytest)")
