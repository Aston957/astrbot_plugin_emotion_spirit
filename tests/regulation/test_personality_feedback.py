"""Tests for PersonalityFeedback (Task 7).

Activity → personality feedback mechanism: activities slowly shift personality
over time. Feedback rate is configurable to prevent rapid drift.

v1.3.0 Y-0b (§1.8): drift 表迁 13 维 (权威模型). 测试期望按 13 维断言:
  - creative → +curiosity / +exploration_openness / +perception_acuity
  - rest → -boundary_permeability / +inner_coherence / +patience (N 反向)
"""
import pytest
from emotion_spirit.regulation.personality_feedback import PersonalityFeedback, ACTIVITY_PERSONALITY_FEEDBACK


def test_creative_activity_boosts_openness_dims():
    """§1.8: creative 提升 curiosity / exploration_openness / perception_acuity (O 派生 dims)."""
    pf = PersonalityFeedback(feedback_rate=1.0)
    personality = {
        "warmth_bias": 0.5, "expression_drive": 0.5, "gossip_tendency": 0.5,
        "intimacy_pull": 0.5, "relational_gravity": 0.5,
        "boundary_permeability": 0.5, "inner_coherence": 0.5, "patience": 0.5,
        "curiosity": 0.5, "perception_acuity": 0.5, "exploration_openness": 0.5,
        "directness": 0.5,
    }
    pf.apply_activity_effect(personality, "creative")
    # O 派生 dims 应升 (O 主载荷)
    assert personality["curiosity"] > 0.5
    assert personality["exploration_openness"] > 0.5
    assert personality["perception_acuity"] > 0.5
    # E 反向 dims (creative 含 extraversion -0.001) 应降
    assert personality["warmth_bias"] < 0.5


def test_clamping_keeps_traits_in_bounds():
    """§1.8: clamp 仍对 13 dim 生效 (feedback_rate 极端值)."""
    pf = PersonalityFeedback(feedback_rate=100.0)  # extreme rate
    personality = {
        "curiosity": 0.9, "exploration_openness": 0.9, "perception_acuity": 0.9,
        "warmth_bias": 0.5, "expression_drive": 0.5, "gossip_tendency": 0.5,
        "intimacy_pull": 0.5, "relational_gravity": 0.5,
        "boundary_permeability": 0.5, "inner_coherence": 0.5, "patience": 0.5,
        "directness": 0.5,
    }
    pf.apply_activity_effect(personality, "creative")
    assert personality["curiosity"] <= 0.95
    assert personality["exploration_openness"] <= 0.95
    assert personality["perception_acuity"] <= 0.95


def test_floor_keeps_traits_above_minimum():
    """§1.8: rest → N 反向 → -boundary_permeability / +inner_coherence / +patience."""
    pf = PersonalityFeedback(feedback_rate=100.0)
    personality = {
        "boundary_permeability": 0.9, "inner_coherence": 0.1, "patience": 0.1,
        "warmth_bias": 0.5, "expression_drive": 0.5, "gossip_tendency": 0.5,
        "intimacy_pull": 0.5, "relational_gravity": 0.5,
        "curiosity": 0.5, "perception_acuity": 0.5, "exploration_openness": 0.5,
        "directness": 0.5,
    }
    pf.apply_activity_effect(personality, "rest")  # rest: N -0.003 → bp 减, ic/pat 加 (反向)
    assert personality["boundary_permeability"] >= 0.05
    assert personality["inner_coherence"] <= 0.95
    assert personality["patience"] <= 0.95