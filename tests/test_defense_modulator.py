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


# === Task 4: KB defense_deltas.json + loader ===

def test_defense_deltas_kb_loads():
    """KB defense_deltas.json 应能被加载"""
    from emotion_spirit.core.persona_labels_db import get_defense_deltas
    deltas = get_defense_deltas()
    assert deltas["_version"] >= 1
    assert "silence" in deltas
    assert "collapse" in deltas
    assert "suppression" in deltas


def test_defense_deltas_silence_clamped():
    """silence.delta 必在 [-1, 1]"""
    from emotion_spirit.core.persona_labels_db import get_defense_deltas
    deltas = get_defense_deltas()
    for axis in ["individual", "natural", "social"]:
        assert -1.0 <= deltas["silence"][axis] <= 1.0


def test_defense_deltas_have_source_doc():
    """每个事件类型应有 _doc 字段 (handbook §1.1 文献背书)"""
    from emotion_spirit.core.persona_labels_db import get_defense_deltas
    deltas = get_defense_deltas()
    for event in ["silence", "collapse", "suppression"]:
        assert "_doc" in deltas[event], f"{event} 缺 _doc 字段"
