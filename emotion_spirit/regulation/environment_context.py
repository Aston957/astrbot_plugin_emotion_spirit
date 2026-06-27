"""Seasonal, weather, and day-of-week context for activity planning."""
from __future__ import annotations
import datetime
from ..core.registry import register


@register(name="environment_context", provides=["EnvironmentContext"], depends_on=[])
class EnvironmentContext:
    def __init__(self, month: int | None = None, weekday: int | None = None):
        self._month = month or datetime.datetime.now().month
        self._weekday = weekday if weekday is not None else datetime.datetime.now().weekday()

    def get_season_bias(self) -> dict:
        if self._month in (12, 1, 2):
            return {"rest": 0.2, "physical": -0.1, "social": -0.1}
        if self._month in (6, 7, 8):
            return {"physical": 0.2, "social": 0.1, "rest": -0.1}
        return {}

    def get_weather_bias(self, weather: str = "sunny") -> dict:
        if weather == "rainy":
            return {"rest": 0.2, "creative": 0.1, "physical": -0.2}
        if weather == "sunny":
            return {"physical": 0.2, "social": 0.1, "rest": -0.1}
        return {}

    def get_day_bias(self) -> dict:
        if self._weekday >= 5:
            return {"social": 0.2, "rest": 0.1, "routine": -0.2}
        return {"routine": 0.1, "intellectual": 0.1}