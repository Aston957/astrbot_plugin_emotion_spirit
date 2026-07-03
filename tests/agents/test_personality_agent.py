"""Tests for PersonalityAgent (axis 2: superego + drift)."""

import asyncio
import pytest
from unittest.mock import MagicMock

from emotion_spirit.agents.base import PRE, POST, RULE, SKIP, LLM, AgentIntent
from emotion_spirit.agents.personality_agent import PersonalityAgent


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    """Run async coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── perceive tests ───────────────────────────────────────────────────────────

def test_perceive_extracts_expected_keys():
    agent = PersonalityAgent()

    surface = {
        "_phase": PRE,
        "safety_level": "warning",
        "valence": -0.5,
        "arousal": 0.7,
        "sentinel_result": {"level": "warning"},
        "current_personality": {"deep": {}, "surface": {}},
        "session_key": "sk1",
    }
    p = agent.perceive(surface)
    assert p["phase"] == PRE
    assert p["safety_level"] == "warning"
    assert p["valence"] == -0.5
    assert p["arousal"] == 0.7
    assert p["sentinel_result"] == {"level": "warning"}
    assert p["current_personality"] == {"deep": {}, "surface": {}}
    assert p["session_key"] == "sk1"


def test_perceive_defaults():
    agent = PersonalityAgent()

    p = agent.perceive({})
    assert p["phase"] == POST
    assert p["safety_level"] == "normal"
    assert p["valence"] == 0.0
    assert p["arousal"] == 0.0
    assert p["sentinel_result"] == {}
    assert p["current_personality"] is None
    assert p["session_key"] == ""


# ── gate tests ───────────────────────────────────────────────────────────────

def test_gate_pre_normal_safety_returns_skip():
    agent = PersonalityAgent()
    assert agent.gate({"phase": PRE, "safety_level": "normal"}) == SKIP


def test_gate_pre_caution_returns_rule():
    agent = PersonalityAgent()
    assert agent.gate({"phase": PRE, "safety_level": "caution"}) == RULE


def test_gate_pre_warning_returns_llm():
    agent = PersonalityAgent()
    assert agent.gate({"phase": PRE, "safety_level": "warning"}) == LLM


def test_gate_pre_critical_returns_llm():
    agent = PersonalityAgent()
    assert agent.gate({"phase": PRE, "safety_level": "critical"}) == LLM


def test_gate_post_high_valence_returns_rule():
    agent = PersonalityAgent()
    # valence=-0.5, abs=0.5 >= 0.2
    assert agent.gate({"phase": POST, "valence": -0.5, "arousal": 0.0}) == RULE


def test_gate_post_high_arousal_returns_rule():
    agent = PersonalityAgent()
    # arousal=0.3 >= 0.2
    assert agent.gate({"phase": POST, "valence": 0.0, "arousal": 0.3}) == RULE


def test_gate_post_low_intensity_returns_skip():
    agent = PersonalityAgent()
    # both below 0.2
    assert agent.gate({"phase": POST, "valence": 0.1, "arousal": 0.1}) == SKIP


def test_gate_post_boundary_intensity():
    """0.2 exactly should pass (>= 0.2)."""
    agent = PersonalityAgent()
    assert agent.gate({"phase": POST, "valence": 0.2, "arousal": 0.0}) == RULE


def test_gate_post_just_below_boundary():
    """0.19 is just below the 0.2 threshold."""
    agent = PersonalityAgent()
    assert agent.gate({"phase": POST, "valence": 0.19, "arousal": 0.0}) == SKIP


def test_gate_post_defaults_returns_skip():
    """Default POST (no valence/arousal) should skip."""
    agent = PersonalityAgent()
    assert agent.gate({"phase": POST}) == SKIP


# ── act PRE (superego) tests ─────────────────────────────────────────────────

def test_act_pre_normal_safety_returns_safe_flag():
    agent = PersonalityAgent()

    result = _run(agent.act("sk", RULE, {"safety_level": "normal", "session_key": "sk"}, PRE))
    assert result is not None
    assert isinstance(result, AgentIntent)
    assert result.source == "personality"
    assert "safe" in result.flags
    assert result.priority == 0.6
    assert result.payload["safety_level"] == "normal"


def test_act_pre_warning_safety_returns_hurt_flag():
    agent = PersonalityAgent()

    result = _run(agent.act("sk", RULE, {"safety_level": "warning", "session_key": "sk"}, PRE))
    assert result is not None
    assert "hurt" in result.flags


def test_act_pre_critical_safety_returns_hurt_flag():
    agent = PersonalityAgent()

    result = _run(agent.act("sk", LLM, {"safety_level": "critical", "session_key": "sk"}, PRE))
    assert result is not None
    assert "hurt" in result.flags


def test_act_pre_with_superego_guard():
    """When superego_guard is available, it should be consulted."""
    mock_guard = MagicMock()
    mock_guard.assess.return_value = MagicMock(level="warning")

    agent = PersonalityAgent( superego_guard=mock_guard)

    result = _run(agent.act("sk", RULE, {
        "safety_level": "normal",
        "sentinel_result": {"level": "normal"},
        "current_personality": {"deep": {}, "surface": {}},
        "session_key": "sk",
    }, PRE))

    assert result is not None
    mock_guard.assess.assert_called_once()
    assert result.payload["safety_level"] == "warning"


def test_act_pre_superego_exception_falls_through():
    """If superego_guard.assess() raises, fall back to surface safety_level."""
    mock_guard = MagicMock()
    mock_guard.assess.side_effect = RuntimeError("boom")

    agent = PersonalityAgent( superego_guard=mock_guard)

    result = _run(agent.act("sk", RULE, {
        "safety_level": "caution",
        "session_key": "sk",
    }, PRE))

    assert result is not None
    assert result.payload["safety_level"] == "caution"


# ── act POST (drift) tests ───────────────────────────────────────────────────

def test_post_no_drift_returns_none():
    agent = PersonalityAgent( personality_drift=None)

    result = _run(agent.act("sk", RULE, {}, POST))
    assert result is None


def test_post_drift_no_drifts_returns_none():
    """When drift detector finds no drifts, returns None."""
    mock_drift = MagicMock()
    mock_drift.check_drift.return_value = []

    agent = PersonalityAgent( personality_drift=mock_drift)
    result = _run(agent.act("sk", RULE, {}, POST))

    assert result is None


def test_post_drift_returns_intent_with_drifts():
    """When drift detector finds drifts, returns AgentIntent with drift data."""
    drift_data = [
        {"dimension": "warmth_bias", "direction": "increasing", "slope": 0.015, "cap": 0.05, "source": "surface"},
        {"dimension": "expression_drive", "direction": "decreasing", "slope": -0.012, "cap": 0.05, "source": "deep"},
    ]
    mock_drift = MagicMock()
    mock_drift.check_drift.return_value = drift_data

    agent = PersonalityAgent( personality_drift=mock_drift)
    result = _run(agent.act("sk", RULE, {}, POST))

    assert result is not None
    assert isinstance(result, AgentIntent)
    assert result.source == "personality"
    assert result.priority == 0.3
    assert result.payload["drifts"] == drift_data


def test_post_drift_exception_returns_none():
    """If drift.check_drift() raises, returns None."""
    mock_drift = MagicMock()
    mock_drift.check_drift.side_effect = RuntimeError("boom")

    agent = PersonalityAgent( personality_drift=mock_drift)
    result = _run(agent.act("sk", RULE, {}, POST))

    assert result is None


# ── integration: perceive -> gate -> act ─────────────────────────────────────

def test_full_pipeline_pre_warning():
    """Warning safety: perceive -> gate(LLM) -> act returns hurt intent."""
    agent = PersonalityAgent()

    surface = {"_phase": PRE, "safety_level": "warning", "session_key": "sk"}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == LLM

    result = _run(agent.act("sk", gate_result, perceived, PRE))
    assert result is not None
    assert "hurt" in result.flags


def test_full_pipeline_pre_normal():
    """Normal safety: perceive -> gate(SKIP) -> act is never called."""
    agent = PersonalityAgent()

    surface = {"_phase": PRE, "safety_level": "normal"}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == SKIP


def test_full_pipeline_post_high_intensity():
    """High emotional intensity: perceive -> gate(RULE) -> drift check."""
    drift_data = [{"dimension": "warmth_bias", "direction": "increasing", "slope": 0.02, "cap": 0.05, "source": "surface"}]
    mock_drift = MagicMock()
    mock_drift.check_drift.return_value = drift_data

    agent = PersonalityAgent( personality_drift=mock_drift)

    surface = {"_phase": POST, "valence": 0.5, "arousal": 0.3}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == RULE

    result = _run(agent.act("sk", gate_result, perceived, POST))
    assert result is not None
    assert "drifts" in result.payload


def test_full_pipeline_post_low_intensity():
    """Low emotional intensity: perceive -> gate(SKIP) -> act is never called."""
    mock_drift = MagicMock()
    mock_drift.check_drift.return_value = [{"dimension": "x", "direction": "increasing", "slope": 0.02, "cap": 0.05, "source": "surface"}]

    agent = PersonalityAgent( personality_drift=mock_drift)

    surface = {"_phase": POST, "valence": 0.05, "arousal": 0.05}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == SKIP
