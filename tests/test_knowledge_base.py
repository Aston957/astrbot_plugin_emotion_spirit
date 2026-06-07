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


def test_knowledge_base_exposes_categorical_regions():
    """Step 2: KnowledgeBase.CATEGORICAL_REGIONS 含 7 基本情绪。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert len(KnowledgeBase.CATEGORICAL_REGIONS) >= 7
    for emotion in ["joy", "anger", "sadness", "fear", "surprise", "disgust", "neutral"]:
        assert emotion in KnowledgeBase.CATEGORICAL_REGIONS


def test_knowledge_base_exposes_compound_regions():
    """Step 2: KnowledgeBase.COMPOUND_REGIONS 含 4 复合情绪。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert len(KnowledgeBase.COMPOUND_REGIONS) == 4
    for compound in ["sad_excitement", "angry_despair", "joyful_anxiety", "sad_calm"]:
        assert compound in KnowledgeBase.COMPOUND_REGIONS


def test_knowledge_base_exposes_emotion_zh():
    """Step 2: KnowledgeBase.EMOTION_ZH 含 11 个中文情绪名。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert len(KnowledgeBase.EMOTION_ZH) == 11
    assert KnowledgeBase.EMOTION_ZH["joy"] == "喜悦"


def test_knowledge_base_exposes_narrative_templates():
    """Step 2: KnowledgeBase.NARRATIVE_TEMPLATES 含 11 dim × 2 level × 3 scene = 66 条。"""
    from emotion_spirit.knowledge import KnowledgeBase
    total = 0
    for dim, levels in KnowledgeBase.NARRATIVE_TEMPLATES.items():
        assert "high" in levels and "low" in levels
        for level, scenes in levels.items():
            assert "violation" in scenes and "alignment" in scenes and "advice" in scenes
            for _scene_name, _template in scenes.items():
                total += 1
    assert total == 66


def test_knowledge_base_get_narrative_template_returns_string():
    """Step 2: get_narrative_template(dim, level, scene) 返回字符串。"""
    from emotion_spirit.knowledge import KnowledgeBase
    template = KnowledgeBase.get_narrative_template("warmth_bias", "high", "violation")
    assert isinstance(template, str)
    assert len(template) > 0


def test_old_label_mapper_fields_removed():
    """Step 3: 旧 _MBTI_LETTER_DELTAS 等字段必须从 label_mapper 删除。"""
    import emotion_spirit.label_mapper as lm
    for old_field in ["_MBTI_LETTER_DELTAS", "_ATTACHMENT_DELTAS", "_EMOTION_STYLE_DELTAS", "_CONFLICT_STYLE_DELTAS", "_TIME_FOCUS_DELTAS"]:
        for suffix in ["", "_DEPRECATED"]:
            full = old_field + suffix
            assert not hasattr(lm, full), f"label_mapper.{full} 应已删"


def test_old_emotion_classifier_fields_removed():
    """Step 3: CATEGORICAL_REGIONS 等必须从 emotion_classifier 删除。"""
    import emotion_spirit.emotion_classifier as ec
    for old_field in ["CATEGORICAL_REGIONS", "COMPOUND_REGIONS", "EMOTION_ZH"]:
        for suffix in ["", "_DEPRECATED"]:
            full = old_field + suffix
            assert not hasattr(ec, full), f"emotion_classifier.{full} 应已删"


if __name__ == "__main__":
    test_knowledge_base_exposes_personality_baselines()
    test_knowledge_base_exposes_mbti_letter_deltas()
    test_knowledge_base_get_delta_for_label_dispatches_correctly()
    test_knowledge_base_get_persona_baseline_returns_copy()
    test_knowledge_base_thresholds_include_intimacy_segments()
    test_knowledge_base_get_threshold_supports_mixed_types()
    test_knowledge_base_get_threshold_raises_on_unknown()
    print("\n[OK] KnowledgeBase Step 1: 7/7 tests passed (parity test xfail via pytest)")
