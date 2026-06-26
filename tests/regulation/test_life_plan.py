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
