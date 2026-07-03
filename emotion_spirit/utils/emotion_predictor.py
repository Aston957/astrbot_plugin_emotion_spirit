"""Predict mood trajectory from daily plan activities."""
from __future__ import annotations
from typing import Any


ACTIVITY_EMOTION_EFFECT = {
    "social":   {"valence": +0.2, "arousal": +0.1},
    "creative": {"valence": +0.1, "arousal": -0.1},
    "physical": {"valence": +0.1, "arousal": +0.2},
    "rest":     {"valence": 0.0, "arousal": -0.2},
    "routine":  {"valence": 0.0, "arousal": -0.1},
}


class EmotionPredictor:
    def predict_mood_trajectory(self, plan, current_mood: dict) -> list:
        trajectory = [dict(current_mood)]
        for event in plan.events:
            if event.status != "planned":
                continue
            effect = ACTIVITY_EMOTION_EFFECT.get(event.category, {})
            predicted = dict(trajectory[-1])
            predicted["valence"] = predicted.get("valence", 0) + effect.get("valence", 0)
            predicted["arousal"] = predicted.get("arousal", 0) + effect.get("arousal", 0)
            trajectory.append(predicted)
        return trajectory

    def suggest_adjustment(self, trajectory: list) -> str | None:
        if trajectory[-1].get("valence", 0) < -0.3:
            return "今天的安排可能让你情绪低落，要不要加个轻松的活动？"
        return None