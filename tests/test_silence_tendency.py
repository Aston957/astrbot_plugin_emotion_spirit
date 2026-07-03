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


# ═══ Task 3: compute_silence_tendency 测试 ═══


def test_compute_silence_tendency_default_personality_neutral():
    """默认人格 + 中性信号 → 得分应在 [0.2, 0.5] 区间"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator

    coord = SegmentedReplyCoordinator()
    personality = {
        "extraversion": 0.5,
        "neuroticism": 0.5,
        "agreeableness": 0.5,
        "openness": 0.5,
        "conscientiousness": 0.5,
    }

    result = coord.compute_silence_tendency(
        session_key="test_session",
        personality=personality,
        force_state=None,
        body_state=None,
        signals=None,
        intimacy_level=0.3,
        context={"social_audience": 0.5, "authority_present": 0.0},
    )

    assert 0.2 <= result.score <= 0.5, (
        f"默认人格得分 {result.score} 不在 [0.2, 0.5] 区间"
    )
    assert isinstance(result.reason, str) and len(result.reason) > 0
    assert isinstance(result.components, dict) and len(result.components) > 0


def test_compute_silence_tendency_introvert_anxious_high_intimacy_silences():
    """内向 + 焦虑 + 高亲密 → 受伤/空洞得分 > 0.7"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator

    coord = SegmentedReplyCoordinator()
    personality = {
        "extraversion": 0.1,
        "neuroticism": 0.9,
        "agreeableness": 0.3,
        "openness": 0.3,
        "conscientiousness": 0.5,
    }

    result = coord.compute_silence_tendency(
        session_key="test_introvert",
        personality=personality,
        force_state={"natural": 0.3, "social": 0.2, "individual": 0.5},
        body_state={"energy": 0.3, "arousal": 0.7},
        signals={
            "rhythm_strain": 0.8,
            "hot_pool_pressure": 0.9,
            "pad_valence": 0.1,
            "pad_arousal": 0.7,
        },
        intimacy_level=0.9,
        context={"social_audience": 0.8, "authority_present": 0.0},
    )

    assert result.score > 0.7, (
        f"内向+焦虑+高亲密得分 {result.score} 应 > 0.7"
    )
    assert result.components["hurt_void"] > 0.5, (
        f"hurt_void {result.components['hurt_void']} 应 > 0.5"
    )


def test_compute_silence_tendency_extrovert_open_low_intimacy_speaks():
    """外向 + 开放 + 低亲密 → 得分 < 0.3"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator

    coord = SegmentedReplyCoordinator()
    personality = {
        "extraversion": 0.9,
        "neuroticism": 0.1,
        "agreeableness": 0.3,
        "openness": 0.9,
        "conscientiousness": 0.5,
    }

    result = coord.compute_silence_tendency(
        session_key="test_extrovert",
        personality=personality,
        force_state={"natural": 0.3, "social": 0.5, "individual": 0.2},
        body_state={"energy": 0.8, "arousal": 0.3},
        signals={
            "rhythm_strain": 0.2,
            "hot_pool_pressure": 0.1,
            "pad_valence": 0.8,
            "pad_arousal": 0.3,
        },
        intimacy_level=0.1,
        context={"social_audience": 0.2, "authority_present": 0.0},
    )

    assert result.score < 0.3, (
        f"外向+开放+低亲密得分 {result.score} 应 < 0.3"
    )


def test_compute_silence_tendency_returns_correct_reason():
    """reason 应反映 dominant factor"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator

    coord = SegmentedReplyCoordinator()
    personality = {
        "extraversion": 0.5,
        "neuroticism": 0.5,
        "agreeableness": 0.5,
        "openness": 0.5,
        "conscientiousness": 0.5,
    }

    result = coord.compute_silence_tendency(
        session_key="test_reason",
        personality=personality,
        force_state=None,
        body_state=None,
        signals={"rhythm_strain": 0.3, "hot_pool_pressure": 0.1, "pad_valence": 0.5, "pad_arousal": 0.5},
        intimacy_level=0.5,
        context={"social_audience": 0.5, "authority_present": 0.0},
    )

    dominant = result.components.get("dominant_factor")
    assert dominant is not None, "components 缺少 dominant_factor"
    assert len(result.reason) > 0, "reason 不应为空"


def test_compute_silence_tendency_components_dict_present():
    """components 应包含所有因子 + 修饰符信息"""
    from emotion_spirit.output.segmented_reply_coordinator import SegmentedReplyCoordinator

    coord = SegmentedReplyCoordinator()
    personality = {
        "extraversion": 0.5,
        "neuroticism": 0.5,
        "agreeableness": 0.5,
        "openness": 0.5,
        "conscientiousness": 0.5,
    }

    result = coord.compute_silence_tendency(
        session_key="test_components",
        personality=personality,
        force_state=None,
        body_state=None,
        signals=None,
        intimacy_level=0.5,
        context={"social_audience": 0.5, "authority_present": 0.0},
    )

    expected_keys = {
        "tension_stress",
        "hurt_void",
        "satisfaction_quiet",
        "exhaustion",
        "overload",
        "social_audience",
        "intimacy_modifier",
        "context_modifier",
        "force_modifier",
        "dominant_factor",
    }
    missing = expected_keys - set(result.components.keys())
    assert not missing, f"components 缺 key: {missing}"
    # 所有数值字段应在合理范围
    for key in expected_keys - {"dominant_factor"}:
        val = result.components[key]
        assert isinstance(val, (int, float)), f"{key} = {val} 不是数值"


# ═══ Task 4: should_be_silent / record_silence_event / record_response_event ═══


def test_should_be_silent_under_threshold():
    """score=0.3 < 0.5 → not silent"""
    from emotion_spirit.output.segmented_reply_coordinator import (
        SegmentedReplyCoordinator,
        SilenceTendency,
    )

    coord = SegmentedReplyCoordinator()
    tendency = SilenceTendency(score=0.3, reason="测试低分")
    config = {"silent_threshold": 0.5, "silent_cooldown_turns": 2, "max_consecutive_silence": 3}

    silent, reason, adj = coord.should_be_silent("s1", tendency, config)

    assert silent is False
    assert reason == "below_threshold"
    assert adj.score == 0.3


def test_should_be_silent_above_threshold():
    """score=0.7 > 0.5 → silent"""
    from emotion_spirit.output.segmented_reply_coordinator import (
        SegmentedReplyCoordinator,
        SilenceTendency,
    )

    coord = SegmentedReplyCoordinator()
    tendency = SilenceTendency(score=0.7, reason="测试高分")
    config = {"silent_threshold": 0.5, "silent_cooldown_turns": 2, "max_consecutive_silence": 3}

    silent, reason, adj = coord.should_be_silent("s2", tendency, config)

    assert silent is True
    assert reason == "silence_threshold_met"
    assert adj.score == 0.7


def test_should_be_silent_cooldown_blocks_repeat():
    """turns_since=1 < cooldown=2 → not silent even with high score"""
    from emotion_spirit.output.segmented_reply_coordinator import (
        SegmentedReplyCoordinator,
        SilenceTendency,
    )

    coord = SegmentedReplyCoordinator()
    # simulate: just silenced, so turns_since_last_silence = 0, cooldown=2
    coord._turns_since_last_silence["s3"] = 0
    # now user sent a message and we record_response_event → turns_since becomes 1
    coord.record_response_event("s3")

    tendency = SilenceTendency(score=0.8, reason="高分但冷却中")
    config = {"silent_threshold": 0.5, "silent_cooldown_turns": 2, "max_consecutive_silence": 3}

    silent, reason, adj = coord.should_be_silent("s3", tendency, config)

    assert silent is False
    assert reason == "cooldown_active"
    assert adj.score == 0.8


def test_should_be_silent_max_consecutive_force_response():
    """consecutive=3 >= max=3 → threshold=0.9, score=0.6 not silent"""
    from emotion_spirit.output.segmented_reply_coordinator import (
        SegmentedReplyCoordinator,
        SilenceTendency,
    )

    coord = SegmentedReplyCoordinator()
    # simulate: 3 consecutive silences
    coord._consecutive_silence_count["s4"] = 3
    # cooldown is satisfied (turns_since >= 2)
    coord._turns_since_last_silence["s4"] = 5

    tendency = SilenceTendency(score=0.6, reason="中等倾向")
    config = {"silent_threshold": 0.5, "silent_cooldown_turns": 2, "max_consecutive_silence": 3}

    silent, reason, adj = coord.should_be_silent("s4", tendency, config)

    assert silent is False
    assert reason == "below_threshold"
