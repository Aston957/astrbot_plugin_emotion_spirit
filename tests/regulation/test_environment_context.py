"""Tests for environment_context.py — season/weather/day bias for planning."""
from __future__ import annotations

from emotion_spirit.regulation.environment_context import EnvironmentContext


def test_winter_biases_toward_rest():
    ec = EnvironmentContext(month=12)
    bias = ec.get_season_bias()
    assert bias.get("rest", 0) > 0


def test_summer_biases_toward_physical():
    ec = EnvironmentContext(month=7)
    bias = ec.get_season_bias()
    assert bias.get("physical", 0) > 0


def test_rainy_weather_reduces_physical():
    ec = EnvironmentContext()
    bias = ec.get_weather_bias("rainy")
    assert bias.get("physical", 0) < 0


def test_weekend_biases_toward_social():
    ec = EnvironmentContext(weekday=5)  # Saturday
    bias = ec.get_day_bias()
    assert bias.get("social", 0) > 0