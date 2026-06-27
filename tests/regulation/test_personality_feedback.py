"""Tests for PersonalityFeedback (Task 7).

Activity → personality feedback mechanism: activities slowly shift personality
over time. Feedback rate is configurable to prevent rapid drift.
"""
import pytest
from emotion_spirit.regulation.personality_feedback import PersonalityFeedback, ACTIVITY_PERSONALITY_FEEDBACK


def test_creative_activity_boosts_openness():
    pf = PersonalityFeedback(feedback_rate=1.0)
    personality = {"openness": 0.5, "extraversion": 0.5, "neuroticism": 0.5,
                  "agreeableness": 0.5, "conscientiousness": 0.5}
    pf.apply_activity_effect(personality, "creative")
    assert personality["openness"] > 0.5


def test_clamping_keeps_traits_in_bounds():
    pf = PersonalityFeedback(feedback_rate=100.0)  # extreme rate
    personality = {"openness": 0.9, "extraversion": 0.5, "neuroticism": 0.5,
                  "agreeableness": 0.5, "conscientiousness": 0.5}
    pf.apply_activity_effect(personality, "creative")
    assert personality["openness"] <= 0.95


def test_floor_keeps_traits_above_minimum():
    pf = PersonalityFeedback(feedback_rate=100.0)
    personality = {"openness": 0.1, "extraversion": 0.5, "neuroticism": 0.5,
                  "agreeableness": 0.5, "conscientiousness": 0.5}
    pf.apply_activity_effect(personality, "rest")  # rest decreases openness indirectly via extraversion
    assert personality["openness"] >= 0.05