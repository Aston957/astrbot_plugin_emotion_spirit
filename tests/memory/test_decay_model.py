"""Tests for decay_model.py -- dual-axis decay functions."""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.memory.decay_model import DecayModel


def test_power_law_decay_basic():
    """Power law: R = t^(-b), b=0.27. At t=1, R=1.0."""
    dm = DecayModel()
    r = dm.memory_retention(elapsed_hours=1.0, initial_weight=1.0)
    assert abs(r - 1.0) < 0.01


def test_power_law_decay_decreases():
    """Power law: retention decreases over time."""
    dm = DecayModel()
    r_1h = dm.memory_retention(elapsed_hours=1.0, initial_weight=1.0)
    r_24h = dm.memory_retention(elapsed_hours=24.0, initial_weight=1.0)
    r_168h = dm.memory_retention(elapsed_hours=168.0, initial_weight=1.0)
    assert r_1h > r_24h > r_168h > 0


def test_power_law_decay_tail():
    """Power law: retention never reaches zero (拖尾效应)."""
    dm = DecayModel()
    r_8760h = dm.memory_retention(elapsed_hours=8760.0, initial_weight=1.0)
    assert r_8760h > 0.05  # After 1 year, still > 5% (tail effect)


def test_exponential_decay_basic():
    """Exponential: temperature decays toward zero."""
    dm = DecayModel()
    t = dm.thermal_decay(elapsed_seconds=0, initial_temp=1.0, mass=0.5)
    assert abs(t - 1.0) < 0.01


def test_exponential_decay_decreases():
    """Exponential: temperature decreases over time."""
    dm = DecayModel()
    t_0 = dm.thermal_decay(elapsed_seconds=0, initial_temp=1.0, mass=0.5)
    t_1h = dm.thermal_decay(elapsed_seconds=3600, initial_temp=1.0, mass=0.5)
    t_2h = dm.thermal_decay(elapsed_seconds=7200, initial_temp=1.0, mass=0.5)
    assert t_0 > t_1h > t_2h > 0


def test_mass_slows_thermal_decay():
    """Higher mass -> slower cooling."""
    dm = DecayModel()
    t_low_mass = dm.thermal_decay(elapsed_seconds=3600, initial_temp=1.0, mass=0.1)
    t_high_mass = dm.thermal_decay(elapsed_seconds=3600, initial_temp=1.0, mass=0.9)
    assert t_high_mass > t_low_mass


def test_ghost_no_thermal_decay():
    """Ghost memories have zero thermal decay."""
    dm = DecayModel()
    t = dm.thermal_decay(elapsed_seconds=86400, initial_temp=1.0, mass=0.5, is_ghost=True)
    assert abs(t - 1.0) < 0.01


def test_clamp_utility():
    """clamp() restricts values to [lo, hi]."""
    dm = DecayModel()
    assert dm.clamp(1.5, 0, 1) == 1.0
    assert dm.clamp(-0.5, 0, 1) == 0.0
    assert dm.clamp(0.5, 0, 1) == 0.5
