"""Tests for RelationshipAgent (axis 3: intimacy + social graph)."""

import asyncio
import pytest
from unittest.mock import MagicMock

from emotion_spirit.agents.base import PRE, POST, RULE, SKIP, AgentIntent
from emotion_spirit.agents.relationship_agent import RelationshipAgent


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    """Run async coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_mock_intimacy(intimacy_score=0.5, segment="acquaintance", tone=None):
    """Create a mock IntimacyTracker with configurable returns."""
    mock = MagicMock()
    mock.get_intimacy.return_value = intimacy_score
    mock.get_segment.return_value = segment
    mock.get_relationship_tone.return_value = tone or {"warmth_bias": 0.0}
    return mock


# ── perceive tests ───────────────────────────────────────────────────────────

def test_perceive_extracts_expected_keys():
    agent = RelationshipAgent()

    surface = {
        "_phase": PRE,
        "has_interaction": True,
        "user_id": "user1",
        "persona": "default",
        "intimacy_delta": 0.1,
        "session_key": "sk1",
    }
    p = agent.perceive(surface)
    assert p["phase"] == PRE
    assert p["has_interaction"] is True
    assert p["user_id"] == "user1"
    assert p["persona"] == "default"
    assert p["intimacy_delta"] == 0.1
    assert p["session_key"] == "sk1"


def test_perceive_defaults():
    agent = RelationshipAgent()

    p = agent.perceive({})
    assert p["phase"] == POST
    assert p["has_interaction"] is False
    assert p["user_id"] == ""
    assert p["persona"] == ""
    assert p["intimacy_delta"] == 0.0
    assert p["session_key"] == ""


# ── gate tests ───────────────────────────────────────────────────────────────

def test_gate_pre_with_user_id_and_tracker_returns_rule():
    mock_intimacy = _make_mock_intimacy()
    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)
    assert agent.gate({"phase": PRE, "user_id": "user1"}) == RULE


def test_gate_pre_without_user_id_returns_skip():
    mock_intimacy = _make_mock_intimacy()
    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)
    assert agent.gate({"phase": PRE, "user_id": ""}) == SKIP


def test_gate_pre_without_tracker_returns_skip():
    agent = RelationshipAgent( intimacy_tracker=None)
    assert agent.gate({"phase": PRE, "user_id": "user1"}) == SKIP


def test_gate_pre_missing_user_id_returns_skip():
    mock_intimacy = _make_mock_intimacy()
    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)
    assert agent.gate({"phase": PRE}) == SKIP


def test_gate_post_with_interaction_and_delta_returns_rule():
    agent = RelationshipAgent()
    assert agent.gate({"phase": POST, "has_interaction": True, "intimacy_delta": 0.1}) == RULE


def test_gate_post_with_interaction_no_delta_returns_skip():
    agent = RelationshipAgent()
    assert agent.gate({"phase": POST, "has_interaction": True, "intimacy_delta": 0.0}) == SKIP


def test_gate_post_no_interaction_returns_skip():
    agent = RelationshipAgent()
    assert agent.gate({"phase": POST, "has_interaction": False, "intimacy_delta": 0.1}) == SKIP


def test_gate_post_defaults_returns_skip():
    agent = RelationshipAgent()
    assert agent.gate({"phase": POST}) == SKIP


# ── act PRE (context) tests ──────────────────────────────────────────────────

def test_act_pre_returns_intimacy_context():
    mock_intimacy = _make_mock_intimacy(
        intimacy_score=0.65,
        segment="friend",
        tone={"warmth_bias": 0.10, "intimacy_pull": 0.10},
    )
    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)

    result = _run(agent.act("sk", RULE, {"user_id": "user1", "persona": "default"}, PRE))

    assert result is not None
    assert isinstance(result, AgentIntent)
    assert result.source == "relationship"
    assert result.priority == 0.5
    assert result.payload["intimacy_score"] == 0.65
    assert result.payload["segment"] == "friend"
    assert result.payload["tone"] == {"warmth_bias": 0.10, "intimacy_pull": 0.10}

    mock_intimacy.get_intimacy.assert_called_once_with("user1", "default")
    mock_intimacy.get_segment.assert_called_once_with("user1")
    mock_intimacy.get_relationship_tone.assert_called_once_with("user1")


def test_act_pre_no_user_id_returns_none():
    mock_intimacy = _make_mock_intimacy()
    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)

    result = _run(agent.act("sk", RULE, {"user_id": "", "persona": "default"}, PRE))
    assert result is None


def test_act_pre_no_tracker_returns_none():
    agent = RelationshipAgent( intimacy_tracker=None)

    result = _run(agent.act("sk", RULE, {"user_id": "user1", "persona": "default"}, PRE))
    assert result is None


def test_act_pre_tracker_exception_returns_none():
    mock_intimacy = MagicMock()
    mock_intimacy.get_intimacy.side_effect = RuntimeError("boom")
    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)

    result = _run(agent.act("sk", RULE, {"user_id": "user1", "persona": "default"}, PRE))
    assert result is None


# ── act POST (update) tests ──────────────────────────────────────────────────

def test_act_post_with_delta_returns_intent():
    """POST with positive delta updates intimacy and returns intent."""
    mock_intimacy = _make_mock_intimacy(segment="acquaintance")
    # After update, segment changes to "friend"
    mock_intimacy.get_segment.side_effect = ["acquaintance", "friend"]

    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)

    result = _run(agent.act("sk", RULE, {
        "user_id": "user1",
        "persona": "default",
        "has_interaction": True,
        "intimacy_delta": 0.15,
        "session_key": "sk",
    }, POST))

    assert result is not None
    assert isinstance(result, AgentIntent)
    assert result.source == "relationship"
    assert result.priority == 0.4
    assert result.payload["intimacy_delta"] == 0.15
    assert result.payload["old_segment"] == "acquaintance"
    assert result.payload["new_segment"] == "friend"

    mock_intimacy.update.assert_called_once_with("user1", vulnerability_delta=0.15)


def test_act_post_segment_unchanged_no_event():
    """When segment stays the same, no event is emitted."""
    mock_intimacy = _make_mock_intimacy(segment="friend")
    mock_intimacy.get_segment.return_value = "friend"

    captured = []
def test_act_post_no_user_id_returns_none():
    mock_intimacy = _make_mock_intimacy()
    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)

    result = _run(agent.act("sk", RULE, {"user_id": "", "intimacy_delta": 0.1}, POST))
    assert result is None


def test_act_post_no_tracker_returns_none():
    agent = RelationshipAgent( intimacy_tracker=None)

    result = _run(agent.act("sk", RULE, {"user_id": "user1", "intimacy_delta": 0.1}, POST))
    assert result is None


def test_act_post_zero_delta_returns_none():
    mock_intimacy = _make_mock_intimacy()
    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)

    result = _run(agent.act("sk", RULE, {"user_id": "user1", "intimacy_delta": 0.0}, POST))
    assert result is None


def test_act_post_update_exception_returns_none():
    """If intimacy.update() raises, returns None."""
    mock_intimacy = MagicMock()
    mock_intimacy.get_segment.return_value = "friend"
    mock_intimacy.update.side_effect = RuntimeError("boom")

    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)
    result = _run(agent.act("sk", RULE, {
        "user_id": "user1",
        "intimacy_delta": 0.1,
    }, POST))

    assert result is None


# ── integration: perceive -> gate -> act ─────────────────────────────────────

def test_full_pipeline_pre_with_user():
    """PRE with valid user: perceive -> gate(RULE) -> context intent."""
    mock_intimacy = _make_mock_intimacy(intimacy_score=0.3, segment="stranger")
    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)

    surface = {"_phase": PRE, "user_id": "user1", "persona": "default"}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == RULE

    result = _run(agent.act("sk", gate_result, perceived, PRE))
    assert result is not None
    assert result.payload["segment"] == "stranger"


def test_full_pipeline_pre_no_user():
    """PRE without user: perceive -> gate(SKIP)."""
    mock_intimacy = _make_mock_intimacy()
    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)

    surface = {"_phase": PRE, "user_id": ""}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == SKIP


def test_full_pipeline_post_with_interaction():
    """POST with interaction and delta: perceive -> gate(RULE) -> update."""
    mock_intimacy = _make_mock_intimacy(segment="acquaintance")
    mock_intimacy.get_segment.side_effect = ["acquaintance", "friend"]

    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)

    surface = {
        "_phase": POST,
        "has_interaction": True,
        "user_id": "user1",
        "persona": "default",
        "intimacy_delta": 0.15,
        "session_key": "sk",
    }
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == RULE

    result = _run(agent.act("sk", gate_result, perceived, POST))
    assert result is not None
    assert result.payload["new_segment"] == "friend"


def test_full_pipeline_post_no_interaction():
    """POST without interaction: perceive -> gate(SKIP)."""
    mock_intimacy = _make_mock_intimacy()
    agent = RelationshipAgent( intimacy_tracker=mock_intimacy)

    surface = {"_phase": POST, "has_interaction": False}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == SKIP
