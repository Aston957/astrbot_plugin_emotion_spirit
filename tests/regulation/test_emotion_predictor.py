"""Tests for emotion_predictor.py — mood trajectory prediction from DailyPlan."""
from __future__ import annotations

from emotion_spirit.regulation.emotion_predictor import EmotionPredictor
from emotion_spirit.regulation.life_plan import DailyPlan, PlannedEvent


def test_predict_trajectory_with_social_events():
    ep = EmotionPredictor()
    plan = DailyPlan(
        date="2026-06-27", generated_at=0.0,
        events=[PlannedEvent(id="e1", time_slot="afternoon", approximate_time="14:00",
                             activity="和朋友吃饭", category="social", status="planned", flexibility=0.5)],
        personality_snapshot={}, adaptations=[], dream_seed="",
    )
    trajectory = ep.predict_mood_trajectory(plan, {"valence": 0.0, "arousal": 0.0})
    assert trajectory[-1]["valence"] > 0  # Social should increase valence


def test_suggest_adjustment_for_negative_trend():
    ep = EmotionPredictor()
    trajectory = [{"valence": 0.0}, {"valence": -0.2}, {"valence": -0.4}]
    suggestion = ep.suggest_adjustment(trajectory)
    assert suggestion is not None