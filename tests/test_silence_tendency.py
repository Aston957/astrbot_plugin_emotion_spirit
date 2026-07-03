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
