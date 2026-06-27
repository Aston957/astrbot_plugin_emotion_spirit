"""Tests for emotion_spirit.regulation.life_plan — LifeSimulator v2 data structures."""

import time
from emotion_spirit.regulation.life_plan import (
    PlannedEvent, DailyPlan, PLAN_TEMPLATES, PERSONALITY_TEMPLATE_WEIGHTS,
    select_template_activities, _time_to_slot,
)


def test_planned_event_defaults():
    e = PlannedEvent(id="e1", time_slot="morning", approximate_time="10:00",
                     activity="看书", category="template")
    assert e.status == "planned"
    assert e.flexibility == 0.5
    assert e.cancellation_reason is None


def test_daily_plan_creation():
    now = time.time()
    events = [
        PlannedEvent(id="e1", time_slot="morning", approximate_time="10:00",
                     activity="看书", category="template"),
        PlannedEvent(id="e2", time_slot="afternoon", approximate_time="14:00",
                     activity="逛商场", category="llm_random"),
    ]
    plan = DailyPlan(
        date="2026-06-27",
        generated_at=now,
        events=events,
        personality_snapshot={"openness": 0.8},
        adaptations=[],
        dream_seed="",
    )
    assert len(plan.events) == 2
    assert plan.events[0].activity == "看书"
    assert plan.events[1].category == "llm_random"


def test_time_to_slot():
    import datetime
    # Use a fixed date to create deterministic local-time epoch timestamps
    base = datetime.datetime(2026, 6, 27)
    assert _time_to_slot(base.replace(hour=6).timestamp()) == "morning"
    assert _time_to_slot(base.replace(hour=12).timestamp()) == "afternoon"
    assert _time_to_slot(base.replace(hour=18).timestamp()) == "evening"
    assert _time_to_slot(base.replace(hour=23).timestamp()) == "night"


def test_templates_exist():
    assert "creative" in PLAN_TEMPLATES
    assert "reading" in PLAN_TEMPLATES.get("intellectual", []) or "看书" in PLAN_TEMPLATES.get("intellectual", [])


def test_personality_weights_sum_to_one():
    for trait, weights in PERSONALITY_TEMPLATE_WEIGHTS.items():
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01, f"{trait} weights sum to {total}"


def test_emotion_activity_bias_exists():
    from emotion_spirit.regulation.life_plan import EMOTION_ACTIVITY_BIAS
    assert "happy" in EMOTION_ACTIVITY_BIAS
    assert "social" in EMOTION_ACTIVITY_BIAS["happy"]


def test_personality_activity_bias_exists():
    from emotion_spirit.regulation.life_plan import PERSONALITY_ACTIVITY_BIAS
    assert "extraversion" in PERSONALITY_ACTIVITY_BIAS
    assert "social" in PERSONALITY_ACTIVITY_BIAS["extraversion"]


def test_emotion_activity_bias_values_are_floats():
    from emotion_spirit.regulation.life_plan import EMOTION_ACTIVITY_BIAS
    for emotion, biases in EMOTION_ACTIVITY_BIAS.items():
        for category, value in biases.items():
            assert isinstance(value, float), f"{emotion}/{category} value must be float"


def test_personality_activity_bias_values_are_floats():
    from emotion_spirit.regulation.life_plan import PERSONALITY_ACTIVITY_BIAS
    for trait, biases in PERSONALITY_ACTIVITY_BIAS.items():
        for category, value in biases.items():
            assert isinstance(value, float), f"{trait}/{category} value must be float"


def test_emotion_activity_bias_all_categories_known():
    """All categories in EMOTION_ACTIVITY_BIAS must exist in PLAN_TEMPLATES."""
    from emotion_spirit.regulation.life_plan import EMOTION_ACTIVITY_BIAS
    valid_categories = set(PLAN_TEMPLATES.keys())
    for emotion, biases in EMOTION_ACTIVITY_BIAS.items():
        for category in biases.keys():
            assert category in valid_categories, f"{emotion}/{category} not in PLAN_TEMPLATES"


def test_personality_activity_bias_all_categories_known():
    """All categories in PERSONALITY_ACTIVITY_BIAS must exist in PLAN_TEMPLATES."""
    from emotion_spirit.regulation.life_plan import PERSONALITY_ACTIVITY_BIAS
    valid_categories = set(PLAN_TEMPLATES.keys())
    for trait, biases in PERSONALITY_ACTIVITY_BIAS.items():
        for category in biases.keys():
            assert category in valid_categories, f"{trait}/{category} not in PLAN_TEMPLATES"
