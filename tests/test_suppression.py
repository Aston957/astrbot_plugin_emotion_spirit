"""Tests for SuppressionState L1 force_state integration (v1.2.5 PR2 §4.3)"""
from emotion_spirit.memory.suppression import SuppressionState


def test_suppression_backward_compatible_no_force_state():
    """不传 force_state 输出跟 v1.2.4 一致"""
    sup = SuppressionState()
    level = sup.compute(
        personality={"neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5},
        context={"authority_present": 0, "social_audience": 0},
        conscience_pressure=0.0,
        relationship_intimacy=0.5,
    )
    # baseline 0.5, intimacy_factor 0.8, 没有 authority/social/pressure
    # 0.5 * 0.8 + 0 + 0 + 0 = 0.4
    assert abs(level - 0.4) < 0.001


def test_suppression_with_force_state_social_increases():
    """force_state.social 高 → 压抑升高 (社会面前更想藏)"""
    sup = SuppressionState()
    base_level = sup.compute(
        personality={"neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5},
        context={}, conscience_pressure=0.0, relationship_intimacy=0.5,
    )
    social_level = sup.compute(
        personality={"neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5},
        context={}, conscience_pressure=0.0, relationship_intimacy=0.5,
        force_state={"natural": 0.5, "social": 0.9, "individual": 0.5},
    )
    assert social_level > base_level


def test_suppression_with_force_state_individual_increases():
    """force_state.individual 高 → 压抑升高 (独处时也压抑)"""
    sup = SuppressionState()
    base_level = sup.compute(
        personality={"neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5},
        context={}, conscience_pressure=0.0, relationship_intimacy=0.5,
    )
    indiv_level = sup.compute(
        personality={"neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5},
        context={}, conscience_pressure=0.0, relationship_intimacy=0.5,
        force_state={"natural": 0.5, "social": 0.5, "individual": 0.9},
    )
    assert indiv_level > base_level


def test_suppression_force_state_clamped():
    """force_state 加权后仍 clamp 到 [0, 1]"""
    sup = SuppressionState()
    level = sup.compute(
        personality={"neuroticism": 0.5, "agreeableness": 0.5, "openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5},
        context={}, conscience_pressure=0.0, relationship_intimacy=0.5,
        force_state={"natural": 1.0, "social": 1.0, "individual": 1.0},
    )
    assert 0.0 <= level <= 1.0
