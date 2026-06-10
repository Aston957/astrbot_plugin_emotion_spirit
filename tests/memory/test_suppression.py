"""Tests for suppression.py — dynamic suppression system."""

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

from emotion_spirit.memory.suppression import SuppressionState


def _personality(**overrides):
    defaults = {"neuroticism": 0.5, "extraversion": 0.5, "openness": 0.5,
                "agreeableness": 0.5, "conscientiousness": 0.5}
    defaults.update(overrides)
    return defaults


def test_compute_basic():
    """compute() returns a value between 0 and 1."""
    sup = SuppressionState()
    level = sup.compute(_personality(), {}, 0.0, 0.5)
    assert 0 <= level <= 1


def test_high_neuroticism_increases_suppression():
    """High neuroticism -> higher suppression."""
    sup = SuppressionState()
    high = sup.compute(_personality(neuroticism=0.9), {}, 0.0, 0.5)
    low = sup.compute(_personality(neuroticism=0.1), {}, 0.0, 0.5)
    assert high > low


def test_high_extraversion_decreases_suppression():
    """High extraversion -> lower suppression."""
    sup = SuppressionState()
    high = sup.compute(_personality(extraversion=0.9), {}, 0.0, 0.5)
    low = sup.compute(_personality(extraversion=0.1), {}, 0.0, 0.5)
    assert high < low


def test_intimacy_reduces_suppression():
    """High intimacy -> lower suppression."""
    sup = SuppressionState()
    high_intimacy = sup.compute(_personality(), {}, 0.0, 0.9)
    low_intimacy = sup.compute(_personality(), {}, 0.0, 0.1)
    assert high_intimacy < low_intimacy


def test_authority_increases_suppression():
    """Authority present -> higher suppression."""
    sup = SuppressionState()
    with_auth = sup.compute(_personality(), {"authority_present": 1}, 0.0, 0.5)
    without_auth = sup.compute(_personality(), {}, 0.0, 0.5)
    assert with_auth > without_auth


def test_rebound_basic():
    """check_rebound returns positive value after suppression."""
    sup = SuppressionState()
    rebound = sup.check_rebound(0.8, 48.0)
    assert rebound > 0


def test_rebound_scales_with_duration():
    """Longer suppression -> larger rebound."""
    sup = SuppressionState()
    short = sup.check_rebound(0.5, 1.0)
    long = sup.check_rebound(0.5, 168.0)
    assert long > short


def test_rebound_capped_at_one():
    """Rebound is capped at 1.0."""
    sup = SuppressionState()
    rebound = sup.check_rebound(1.0, 8760.0)
    assert rebound <= 1.0


def test_cost_basic():
    """compute_cost returns positive value."""
    sup = SuppressionState()
    cost = sup.compute_cost(0.5, 24.0)
    assert cost > 0


def test_cost_increases_with_duration():
    """Longer suppression -> higher cost (exponential)."""
    sup = SuppressionState()
    short = sup.compute_cost(0.5, 1.0)
    long = sup.compute_cost(0.5, 168.0)
    assert long > short


def test_cost_higher_for_higher_suppression():
    """Higher suppression level -> higher cost."""
    sup = SuppressionState()
    high = sup.compute_cost(0.9, 24.0)
    low = sup.compute_cost(0.1, 24.0)
    assert high > low
