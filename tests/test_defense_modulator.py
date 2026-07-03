"""Tests for DefenseModulator (v1.2.5 PR2 §4)"""
import pytest
from emotion_spirit.regulation.defense_modulator import DefenseStates


def test_defense_states_default_values():
    """缺省全 0.0/''/{}"""
    s = DefenseStates()
    assert s.suppression_level == 0.0
    assert s.collapse_tendency == 0.0
    assert s.silence_tendency == 0.0
    assert s.silence_reason == ""
    assert s.silence_components == {}


def test_defense_states_with_values():
    """传值正确保存"""
    s = DefenseStates(
        suppression_level=0.5,
        collapse_tendency=0.3,
        silence_tendency=0.7,
        silence_reason="void_hurt_withdrawing",
        silence_components={"hurt_void": 0.6},
    )
    assert s.suppression_level == 0.5
    assert s.collapse_tendency == 0.3
    assert s.silence_tendency == 0.7
    assert s.silence_reason == "void_hurt_withdrawing"
    assert s.silence_components == {"hurt_void": 0.6}


def test_defense_states_suppression_clamped():
    """suppression_level > 1.0 应被 clamp 到 1.0"""
    s = DefenseStates(suppression_level=1.5)
    assert s.suppression_level == 1.0


def test_defense_states_collapse_clamped():
    """collapse_tendency < 0.0 应被 clamp 到 0.0"""
    s = DefenseStates(collapse_tendency=-0.5)
    assert s.collapse_tendency == 0.0


def test_defense_states_silence_clamped():
    """silence_tendency 越界应 clamp"""
    s = DefenseStates(silence_tendency=1.5)
    assert s.silence_tendency == 1.0
    s = DefenseStates(silence_tendency=-0.5)
    assert s.silence_tendency == 0.0
