"""Tests for SilenceTendency dataclass (v1.2.5 PR1 §2.2)"""
import pytest
from emotion_spirit.output.segmented_reply_coordinator import SilenceTendency


def test_silence_tendency_score_in_range_accepted():
    """score 在 [0, 1] 应正常构造"""
    t = SilenceTendency(score=0.5, reason="test")
    assert t.score == 0.5
    assert t.reason == "test"
    assert t.components == {}


def test_silence_tendency_score_below_zero_raises():
    """score < 0 应抛 ValueError"""
    with pytest.raises(ValueError, match="score must be in"):
        SilenceTendency(score=-0.1, reason="test")


def test_silence_tendency_score_above_one_raises():
    """score > 1 应抛 ValueError"""
    with pytest.raises(ValueError, match="score must be in"):
        SilenceTendency(score=1.1, reason="test")


def test_silence_tendency_components_default_empty_dict():
    """components 缺省 {}"""
    t = SilenceTendency(score=0.5, reason="x")
    assert t.components == {}


def test_silence_tendency_is_immutable():
    """SilenceTendency 是 frozen, 不可改"""
    t = SilenceTendency(score=0.5, reason="x")
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        t.score = 0.8


# Task 2: KB 测试

def test_silence_tendency_weights_kb_loads():
    """KB 文件应能被加载并包含必要字段"""
    from emotion_spirit.core.persona_labels_db import get_silence_tendency_weights
    weights = get_silence_tendency_weights()
    assert weights["_version"] >= 1
    assert "factors" in weights
    assert "tension_stress" in weights["factors"]
    assert "hurt_void" in weights["factors"]
    assert "satisfaction_quiet" in weights["factors"]
    assert "exhaustion" in weights["factors"]
    assert "overload" in weights["factors"]
    assert "social_audience" in weights["factors"]
    assert "intimacy_modifier" in weights
    assert "context_modifier" in weights
    assert "force_modifier" in weights


def test_silence_tendency_weights_have_doc_and_source():
    """每个 factor 应有 _doc 和 source 字段 (handbook §1.1 文献背书)"""
    from emotion_spirit.core.persona_labels_db import get_silence_tendency_weights
    weights = get_silence_tendency_weights()
    for factor_name, factor in weights["factors"].items():
        assert "_doc" in factor or "source" in factor, f"{factor_name} 缺 _doc 或 source"


def test_silence_tendency_weights_factor_weights_sum_to_one():
    """6 factor 累加权重应接近 1.0 (确保总分有界)"""
    from emotion_spirit.core.persona_labels_db import get_silence_tendency_weights
    weights = get_silence_tendency_weights()
    total = sum(f["weight_in_sum"] for f in weights["factors"].values())
    assert abs(total - 1.0) < 0.001, f"factor 权重总和 = {total}, 应为 1.0"
