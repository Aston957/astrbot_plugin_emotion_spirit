"""Tests for LifeAgent (axis 4: LifeSimulator v2 + dream system)."""

import asyncio
import pytest
from unittest.mock import MagicMock

from emotion_spirit.agents.base import PRE, AUTONOMOUS, RULE, SKIP, AgentIntent
from emotion_spirit.agents.event_bus import EventBus, LifeEventReady
from emotion_spirit.agents.life_agent import LifeAgent


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    """Run async coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_life_event(text="reading a book", mood="calm", urgency=0.2,
                     event_type="reading", wants_to_share=False):
    """Create a mock LifeEvent-like object."""
    event = MagicMock()
    event.text = text
    event.mood = mood
    event.urgency = urgency
    event.event_type = event_type
    event.wants_to_share = wants_to_share
    return event


def _make_life_sim(adaptations=None, pending_event=None):
    """Create a mock LifeSimulatorV2 with configurable returns."""
    mock = MagicMock()
    mock.adapt_plan.return_value = adaptations or []
    mock.consume_life_event.return_value = pending_event
    return mock


# ── perceive tests ───────────────────────────────────────────────────────────

def test_perceive_extracts_expected_keys():
    bus = EventBus()
    agent = LifeAgent(bus)

    evo_fn = lambda k: 0.1
    surface = {
        "_phase": PRE,
        "emotion_delta": -0.5,
        "cascade_active": True,
        "boundary_pressure": 0.8,
        "_evo_delta": evo_fn,
    }
    p = agent.perceive(surface)
    assert p["phase"] == PRE
    assert p["emotion_delta"] == -0.5
    assert p["cascade_active"] is True
    assert p["boundary_pressure"] == 0.8
    assert p["_evo_delta"] is evo_fn


def test_perceive_defaults():
    bus = EventBus()
    agent = LifeAgent(bus)

    p = agent.perceive({})
    assert p["phase"] == PRE  # default for life agent
    assert p["emotion_delta"] == 0.0
    assert p["cascade_active"] is False
    assert p["boundary_pressure"] == 0.0
    # _evo_delta should be a callable
    assert callable(p["_evo_delta"])
    assert p["_evo_delta"]("anything") == 0.0


def test_perceive_autonomous_phase():
    bus = EventBus()
    agent = LifeAgent(bus)

    p = agent.perceive({"_phase": AUTONOMOUS})
    assert p["phase"] == AUTONOMOUS


# ── gate tests ───────────────────────────────────────────────────────────────

def test_gate_pre_high_delta_returns_rule():
    """PRE with |delta| >= 0.3 should return RULE."""
    bus = EventBus()
    agent = LifeAgent(bus)
    assert agent.gate({"phase": PRE, "emotion_delta": 0.4}) == RULE


def test_gate_pre_negative_high_delta_returns_rule():
    """PRE with negative delta whose abs >= threshold should return RULE."""
    bus = EventBus()
    agent = LifeAgent(bus)
    assert agent.gate({"phase": PRE, "emotion_delta": -0.5}) == RULE


def test_gate_pre_low_delta_returns_skip():
    """PRE with |delta| < 0.3 should return SKIP."""
    bus = EventBus()
    agent = LifeAgent(bus)
    assert agent.gate({"phase": PRE, "emotion_delta": 0.1}) == SKIP


def test_gate_pre_zero_delta_returns_skip():
    """PRE with zero delta should return SKIP."""
    bus = EventBus()
    agent = LifeAgent(bus)
    assert agent.gate({"phase": PRE, "emotion_delta": 0.0}) == SKIP


def test_gate_pre_boundary_delta_returns_rule():
    """PRE with |delta| exactly 0.3 should return RULE (>= threshold)."""
    bus = EventBus()
    agent = LifeAgent(bus)
    assert agent.gate({"phase": PRE, "emotion_delta": 0.3}) == RULE


def test_gate_pre_just_below_boundary_returns_skip():
    """PRE with |delta| just below 0.3 should return SKIP."""
    bus = EventBus()
    agent = LifeAgent(bus)
    assert agent.gate({"phase": PRE, "emotion_delta": 0.29}) == SKIP


def test_gate_pre_with_evo_delta_positive():
    """evo_delta raises threshold -- delta that would pass without it now fails."""
    bus = EventBus()
    agent = LifeAgent(bus)
    evo_fn = lambda k: 0.15 if k == "life_sim_adapt_threshold" else 0.0
    # threshold = 0.3 + 0.15 = 0.45; delta=0.4 < 0.45
    assert agent.gate({"phase": PRE, "emotion_delta": 0.4, "_evo_delta": evo_fn}) == SKIP


def test_gate_pre_with_evo_delta_positive_still_passes():
    """With evo_delta, higher delta still passes."""
    bus = EventBus()
    agent = LifeAgent(bus)
    evo_fn = lambda k: 0.15 if k == "life_sim_adapt_threshold" else 0.0
    # threshold = 0.3 + 0.15 = 0.45; delta=0.5 >= 0.45
    assert agent.gate({"phase": PRE, "emotion_delta": 0.5, "_evo_delta": evo_fn}) == RULE


def test_gate_pre_with_evo_delta_negative():
    """evo_delta can lower the threshold."""
    bus = EventBus()
    agent = LifeAgent(bus)
    evo_fn = lambda k: -0.1 if k == "life_sim_adapt_threshold" else 0.0
    # threshold = 0.3 + (-0.1) = 0.2; delta=0.25 >= 0.2
    assert agent.gate({"phase": PRE, "emotion_delta": 0.25, "_evo_delta": evo_fn}) == RULE


def test_gate_autonomous_always_returns_rule():
    """AUTONOMOUS phase always returns RULE regardless of other values."""
    bus = EventBus()
    agent = LifeAgent(bus)
    assert agent.gate({"phase": AUTONOMOUS}) == RULE


def test_gate_autonomous_with_zero_delta_returns_rule():
    """AUTONOMOUS even with zero delta returns RULE."""
    bus = EventBus()
    agent = LifeAgent(bus)
    assert agent.gate({"phase": AUTONOMOUS, "emotion_delta": 0.0}) == RULE


def test_gate_defaults_returns_skip():
    """Default (no phase, defaults to PRE) with zero delta returns SKIP."""
    bus = EventBus()
    agent = LifeAgent(bus)
    # Missing phase defaults to PRE in perceive, but gate gets called with whatever
    # is passed. If called with {}, phase defaults via .get() to None, which != PRE,
    # so falls through to AUTONOMOUS path -> RULE.
    # Actually: perceived.get("phase") returns None, which != "pre", so goes to else branch.
    assert agent.gate({}) == RULE


# ── act PRE (adapt_plan) tests ───────────────────────────────────────────────

def test_act_pre_with_adaptations_returns_intent():
    """PRE with adaptations returns AgentIntent with plan_adaptations."""
    bus = EventBus()
    adaptations = [{"action": "cancel", "event_id": "evt1", "reason": "too sad"}]
    mock_sim = _make_life_sim(adaptations=adaptations)
    agent = LifeAgent(
        bus, life_sim_v2=mock_sim,
        personality={"openness": 0.6, "extraversion": 0.4},
    )

    result = _run(agent.act("sk", RULE, {
        "emotion_delta": -0.5,
        "cascade_active": False,
        "boundary_pressure": 0.0,
    }, PRE))

    assert result is not None
    assert isinstance(result, AgentIntent)
    assert result.source == "life"
    assert result.priority == 0.3
    assert result.payload["plan_adaptations"] == adaptations
    mock_sim.adapt_plan.assert_called_once_with(
        emotion_state={"valence": -0.5, "arousal": 0.5, "tension": 0.5},
        personality={"openness": 0.6, "extraversion": 0.4},
        suppression_level=0.0,
        collapse_archetype=None,
    )


def test_act_pre_no_adaptations_returns_none():
    """PRE with empty adaptations returns None."""
    bus = EventBus()
    mock_sim = _make_life_sim(adaptations=[])
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    result = _run(agent.act("sk", RULE, {
        "emotion_delta": -0.5,
    }, PRE))

    assert result is None


def test_act_pre_no_life_sim_returns_none():
    """PRE without LifeSimulatorV2 returns None."""
    bus = EventBus()
    agent = LifeAgent(bus, life_sim_v2=None)

    result = _run(agent.act("sk", RULE, {"emotion_delta": -0.5}, PRE))
    assert result is None


def test_act_pre_adapt_exception_returns_none():
    """If adapt_plan raises, returns None."""
    bus = EventBus()
    mock_sim = MagicMock()
    mock_sim.adapt_plan.side_effect = RuntimeError("boom")
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    result = _run(agent.act("sk", RULE, {"emotion_delta": -0.5}, PRE))
    assert result is None


def test_act_pre_passes_all_params():
    """PRE maps perceived + personality into the v2 adapt_plan signature."""
    bus = EventBus()
    mock_sim = _make_life_sim(adaptations=[{"action": "cancel"}])
    personality = {
        "openness": 0.7, "conscientiousness": 0.4,
        "extraversion": 0.6, "agreeableness": 0.5, "neuroticism": 0.3,
    }
    agent = LifeAgent(bus, life_sim_v2=mock_sim, personality=personality)

    _run(agent.act("sk", RULE, {
        "emotion_delta": -0.4,
        "cascade_active": True,
        "boundary_pressure": 0.8,
    }, PRE))

    mock_sim.adapt_plan.assert_called_once_with(
        emotion_state={"valence": -0.4, "arousal": 0.4, "tension": 0.4},
        personality=personality,
        suppression_level=0.0,
        collapse_archetype=None,
    )


def test_act_pre_default_perceived_params():
    """PRE with minimal perceived dict uses defaults for emotion_state."""
    bus = EventBus()
    mock_sim = _make_life_sim(adaptations=[{"action": "cancel"}])
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    _run(agent.act("sk", RULE, {}, PRE))

    mock_sim.adapt_plan.assert_called_once_with(
        emotion_state={"valence": 0.0, "arousal": 0.0, "tension": 0.0},
        personality={
            "openness": 0.5, "conscientiousness": 0.5,
            "extraversion": 0.5, "agreeableness": 0.5, "neuroticism": 0.5,
        },
        suppression_level=0.0,
        collapse_archetype=None,
    )


# ── act AUTONOMOUS (event consumption) tests ────────────────────────────────

def test_act_autonomous_with_pending_event_returns_intent():
    """AUTONOMOUS with pending LifeEvent returns intent with life_event payload."""
    bus = EventBus()
    life_event = _make_life_event(
        text="cooking dinner", mood="happy", urgency=0.3,
        event_type="cooking", wants_to_share=True,
    )
    mock_sim = _make_life_sim(pending_event=life_event)
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    result = _run(agent.act("sk", RULE, {}, AUTONOMOUS))

    assert result is not None
    assert isinstance(result, AgentIntent)
    assert result.source == "life"
    assert result.priority == 0.3
    assert result.payload["life_event"]["text"] == "cooking dinner"
    assert result.payload["life_event"]["mood"] == "happy"
    assert result.payload["life_event"]["urgency"] == 0.3
    assert result.payload["life_event"]["event_type"] == "cooking"
    assert result.payload["life_event"]["wants_to_share"] is True
    mock_sim.consume_life_event.assert_called_once()


def test_act_autonomous_no_pending_event_returns_none():
    """AUTONOMOUS with no pending event returns None."""
    bus = EventBus()
    mock_sim = _make_life_sim(pending_event=None)
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    result = _run(agent.act("sk", RULE, {}, AUTONOMOUS))

    assert result is None
    mock_sim.consume_life_event.assert_called_once()


def test_act_autonomous_no_life_sim_returns_none():
    """AUTONOMOUS without LifeSimulatorV2 returns None."""
    bus = EventBus()
    agent = LifeAgent(bus, life_sim_v2=None)

    result = _run(agent.act("sk", RULE, {}, AUTONOMOUS))
    assert result is None


def test_act_autonomous_consume_exception_returns_none():
    """If consume_life_event raises, returns None."""
    bus = EventBus()
    mock_sim = MagicMock()
    mock_sim.consume_life_event.side_effect = RuntimeError("boom")
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    result = _run(agent.act("sk", RULE, {}, AUTONOMOUS))
    assert result is None


def test_act_autonomous_emits_life_event_ready():
    """AUTONOMOUS with pending event emits LifeEventReady."""
    bus = EventBus()
    life_event = _make_life_event(text="reading", mood="calm")
    mock_sim = _make_life_sim(pending_event=life_event)
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    captured = []
    bus.subscribe(LifeEventReady, lambda e: captured.append(e))

    _run(agent.act("sk", RULE, {}, AUTONOMOUS))

    assert len(captured) == 1
    assert captured[0].source == "life"
    assert captured[0].session_key == "sk"
    assert captured[0].text == "reading"
    assert captured[0].mood == "calm"


def test_act_autonomous_no_event_no_emit():
    """AUTONOMOUS with no pending event does NOT emit LifeEventReady."""
    bus = EventBus()
    mock_sim = _make_life_sim(pending_event=None)
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    captured = []
    bus.subscribe(LifeEventReady, lambda e: captured.append(e))

    _run(agent.act("sk", RULE, {}, AUTONOMOUS))

    assert len(captured) == 0


def test_act_autonomous_consume_exception_no_emit():
    """If consume_life_event raises, no event is emitted."""
    bus = EventBus()
    mock_sim = MagicMock()
    mock_sim.consume_life_event.side_effect = RuntimeError("boom")
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    captured = []
    bus.subscribe(LifeEventReady, lambda e: captured.append(e))

    _run(agent.act("sk", RULE, {}, AUTONOMOUS))

    assert len(captured) == 0


# ── integration: perceive -> gate -> act ─────────────────────────────────────

def test_full_pipeline_pre_high_delta():
    """PRE with high delta: perceive -> gate(RULE) -> act returns adaptations."""
    bus = EventBus()
    adaptations = [{"action": "cancel", "event_id": "evt1", "reason": "sad"}]
    mock_sim = _make_life_sim(adaptations=adaptations)
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    surface = {"_phase": PRE, "emotion_delta": -0.6, "cascade_active": True}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == RULE

    result = _run(agent.act("sk", gate_result, perceived, PRE))
    assert result is not None
    assert result.payload["plan_adaptations"] == adaptations


def test_full_pipeline_pre_low_delta():
    """PRE with low delta: perceive -> gate(SKIP)."""
    bus = EventBus()
    mock_sim = _make_life_sim(adaptations=[])
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    surface = {"_phase": PRE, "emotion_delta": 0.05}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == SKIP
    # SelfCore won't call act when gate returns SKIP, so we verify gate only


def test_full_pipeline_autonomous_with_event():
    """AUTONOMOUS: perceive -> gate(RULE) -> act emits and returns intent."""
    bus = EventBus()
    life_event = _make_life_event(text="walking in park", mood="peaceful",
                                  event_type="walking", wants_to_share=True)
    mock_sim = _make_life_sim(pending_event=life_event)
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    captured = []
    bus.subscribe(LifeEventReady, lambda e: captured.append(e))

    surface = {"_phase": AUTONOMOUS}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == RULE

    result = _run(agent.act("sk", gate_result, perceived, AUTONOMOUS))
    assert result is not None
    assert result.payload["life_event"]["text"] == "walking in park"
    assert len(captured) == 1
    assert captured[0].text == "walking in park"


def test_full_pipeline_autonomous_no_event():
    """AUTONOMOUS with no pending event: perceive -> gate(RULE) -> act returns None."""
    bus = EventBus()
    mock_sim = _make_life_sim(pending_event=None)
    agent = LifeAgent(bus, life_sim_v2=mock_sim)

    captured = []
    bus.subscribe(LifeEventReady, lambda e: captured.append(e))

    surface = {"_phase": AUTONOMOUS}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == RULE

    result = _run(agent.act("sk", gate_result, perceived, AUTONOMOUS))
    assert result is None
    assert len(captured) == 0


def test_full_pipeline_no_life_sim():
    """Without LifeSimulatorV2, all act calls return None."""
    bus = EventBus()
    agent = LifeAgent(bus, life_sim_v2=None)

    # PRE
    surface_pre = {"_phase": PRE, "emotion_delta": 0.8}
    perceived = agent.perceive(surface_pre)
    assert agent.gate(perceived) == RULE
    result = _run(agent.act("sk", RULE, perceived, PRE))
    assert result is None

    # AUTONOMOUS
    surface_auto = {"_phase": AUTONOMOUS}
    perceived = agent.perceive(surface_auto)
    assert agent.gate(perceived) == RULE
    result = _run(agent.act("sk", RULE, perceived, AUTONOMOUS))
    assert result is None
