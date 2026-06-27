"""Tests for energy_model.py — circadian rhythm + personality modulation."""
from __future__ import annotations

from emotion_spirit.regulation.energy_model import get_energy_level, apply_energy_bias


def test_morning_high_energy():
    level = get_energy_level({"extraversion": 0.5, "neuroticism": 0.5}, "morning")
    assert level > 0.7


def test_night_low_energy():
    level = get_energy_level({"extraversion": 0.5, "neuroticism": 0.5}, "night")
    assert level < 0.3


def test_extraversion_boosts_morning_energy():
    base = get_energy_level({"extraversion": 0.5, "neuroticism": 0.5}, "morning")
    high = get_energy_level({"extraversion": 0.9, "neuroticism": 0.5}, "morning")
    assert high > base


def test_energy_bias_high_energy_prefers_physical():
    weights = {"physical": 0.0, "rest": 0.0}
    biased = apply_energy_bias(weights, energy_level=0.8)
    assert biased["physical"] > 0


def test_energy_bias_low_energy_prefers_rest():
    weights = {"physical": 0.0, "rest": 0.0}
    biased = apply_energy_bias(weights, energy_level=0.3)
    assert biased["rest"] > 0