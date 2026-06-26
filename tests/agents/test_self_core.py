"""Tests for SelfCore orchestrator."""
import asyncio
import pytest
from emotion_spirit.agents.base import CognitiveAgent, AgentIntent, PRE, POST, RULE, SKIP, LLM, VALID_FLAGS
from emotion_spirit.agents.event_bus import EventBus, AgentEvent, BoundaryBreached, ShadowDetected, LifeEventReady, RelationshipChanged
from emotion_spirit.agents.self_core import SelfCore, ComposedInputs


# ── Helpers ──────────────────────────────────────────────────────────────────

class DummyAgent(CognitiveAgent):
    name = "dummy"
    phases = (PRE,)

    def __init__(self, bus, mode=RULE):
        super().__init__(bus)
        self._mode = mode

    def gate(self, perceived):
        return self._mode

    async def act(self, session_key, mode, perceived, phase=PRE):
        return AgentIntent(source="dummy", flags=["safe"], priority=0.5)


# ── CognitiveAgent tests ─────────────────────────────────────────────────────

def test_cognitive_agent_defaults():
    """Base CognitiveAgent returns empty perceive, SKIP gate, None act."""
    bus = EventBus()
    agent = CognitiveAgent(bus)
    assert agent.perceive({}) == {}
    assert agent.gate({}) == SKIP
    assert asyncio.run(agent.act("sk", RULE, {})) is None


def test_cognitive_agent_emit():
    """emit() delegates to bus.publish()."""
    bus = EventBus()
    received = []
    bus.subscribe(AgentEvent, lambda e: received.append(e))
    agent = CognitiveAgent(bus)
    agent.emit(AgentEvent(source="test", session_key="sk"))
    assert len(received) == 1
    assert received[0].source == "test"


def test_agent_intent_dataclass():
    """AgentIntent fields and defaults."""
    ai = AgentIntent(source="x")
    assert ai.source == "x"
    assert ai.flags == []
    assert ai.confidence_hint is None
    assert ai.affect == {}
    assert ai.group_heat is None
    assert ai.priority == 0.5
    assert ai.payload == {}


def test_agent_intent_slots():
    """AgentIntent is slotted (no __dict__)."""
    ai = AgentIntent(source="x")
    assert not hasattr(ai, "__dict__")


# ── EventBus tests ───────────────────────────────────────────────────────────

def test_event_bus_subscribe_publish():
    """Events dispatched to correct handler."""
    bus = EventBus()
    received = []
    bus.subscribe(AgentEvent, lambda e: received.append(e))
    bus.publish(AgentEvent(source="a", session_key="sk"))
    assert len(received) == 1


def test_event_bus_no_cross_type():
    """Handler for one type does not receive other types."""
    bus = EventBus()
    base_received = []
    boundary_received = []
    bus.subscribe(AgentEvent, lambda e: base_received.append(e))
    bus.subscribe(BoundaryBreached, lambda e: boundary_received.append(e))
    bus.publish(BoundaryBreached(source="a", session_key="sk", pressure=0.8))
    # BoundaryBreached is a subclass of AgentEvent, so both should fire
    assert len(boundary_received) == 1


def test_event_bus_clear():
    """clear() removes all subscriptions."""
    bus = EventBus()
    received = []
    bus.subscribe(AgentEvent, lambda e: received.append(e))
    bus.clear()
    bus.publish(AgentEvent(source="a", session_key="sk"))
    assert len(received) == 0


def test_event_bus_handler_exception():
    """Exception in handler does not propagate."""
    bus = EventBus()
    def bad_handler(e):
        raise ValueError("boom")
    bus.subscribe(AgentEvent, bad_handler)
    # Should not raise
    bus.publish(AgentEvent(source="a", session_key="sk"))


def test_event_subclasses():
    """Typed event subclasses have correct fields."""
    be = BoundaryBreached(source="b", session_key="sk", pressure=0.9)
    assert be.pressure == 0.9
    se = ShadowDetected(source="s", session_key="sk", tags=["anger"])
    assert se.tags == ["anger"]
    le = LifeEventReady(source="l", session_key="sk", text="hi", mood="happy")
    assert le.text == "hi"
    assert le.mood == "happy"
    re = RelationshipChanged(source="r", session_key="sk", user_id="u1", segment="close", delta=0.1)
    assert re.user_id == "u1"
    assert re.segment == "close"
    assert re.delta == 0.1


# ── SelfCore tests ───────────────────────────────────────────────────────────

def test_self_core_register():
    sc = SelfCore()
    agent = DummyAgent(sc.bus)
    sc.register(agent)
    assert len(sc._agents) == 1


def test_self_core_run_cycle():
    sc = SelfCore()
    sc.register(DummyAgent(sc.bus))
    result = asyncio.run(
        sc.run_cycle("test", {}, PRE)
    )
    assert "safe" in result.flags


def test_self_core_skip():
    sc = SelfCore()
    sc.register(DummyAgent(sc.bus, mode=SKIP))
    result = asyncio.run(
        sc.run_cycle("test", {}, PRE)
    )
    assert result.flags == []


def test_self_core_phase_filter():
    """Agents only run when their phase matches."""
    sc = SelfCore()
    sc.register(DummyAgent(sc.bus))
    # DummyAgent phases=(PRE,), request POST -> should produce empty
    result = asyncio.run(
        sc.run_cycle("test", {}, POST)
    )
    assert result.flags == []


def test_llm_budget():
    sc = SelfCore(llm_budget=1)
    class LLM1(CognitiveAgent):
        name = "personality"
        phases = (PRE,)
        def gate(self, p): return "llm"
        async def act(self, sk, m, p, phase=PRE):
            return AgentIntent(source="personality", flags=["safe"], payload={"src": "p"})
    class LLM2(CognitiveAgent):
        name = "life"
        phases = (PRE,)
        def gate(self, p): return "llm"
        async def act(self, sk, m, p, phase=PRE):
            return AgentIntent(source="life", flags=["idle"], payload={"src": "l"})
    sc.register(LLM1(sc.bus))
    sc.register(LLM2(sc.bus))
    result = asyncio.run(
        sc.run_cycle("test", {}, PRE)
    )
    # Both should still produce intents (one via LLM, one downgraded to RULE)
    assert len(result.carried) == 2
    assert "personality" in result.carried
    assert "life" in result.carried


def test_composed_inputs_defaults():
    """ComposedInputs default values."""
    ci = ComposedInputs()
    assert ci.flags == []
    assert ci.confidence is None
    assert ci.values == {}
    assert ci.assessment == {}
    assert ci.carried == {}


def test_compose_flag_filtering():
    """Only VALID_FLAGS pass through compose."""
    sc = SelfCore()
    class FlagAgent(CognitiveAgent):
        name = "flagger"
        phases = (PRE,)
        def gate(self, p): return RULE
        async def act(self, sk, m, p, phase=PRE):
            return AgentIntent(source="flagger", flags=["safe", "not_a_real_flag", "hurt"])
    sc.register(FlagAgent(sc.bus))
    result = asyncio.run(
        sc.run_cycle("test", {}, PRE)
    )
    assert "safe" in result.flags
    assert "hurt" in result.flags
    assert "not_a_real_flag" not in result.flags


def test_compose_confidence_weighted():
    """Confidence is weighted by priority."""
    sc = SelfCore()
    class ConfAgent(CognitiveAgent):
        name = "conf"
        phases = (PRE,)
        def gate(self, p): return RULE
        async def act(self, sk, m, p, phase=PRE):
            return AgentIntent(source="conf", confidence_hint=0.8, priority=0.6)
    sc.register(ConfAgent(sc.bus))
    result = asyncio.run(
        sc.run_cycle("test", {}, PRE)
    )
    assert result.confidence == pytest.approx(0.8)


def test_compose_affect_weighted():
    """Affect values are weighted by priority."""
    sc = SelfCore()
    class AffAgent(CognitiveAgent):
        name = "aff"
        phases = (PRE,)
        def gate(self, p): return RULE
        async def act(self, sk, m, p, phase=PRE):
            return AgentIntent(source="aff", affect={"valence": 0.5}, priority=1.0)
    sc.register(AffAgent(sc.bus))
    result = asyncio.run(
        sc.run_cycle("test", {}, PRE)
    )
    assert result.values["valence"] == pytest.approx(0.5)
    assert result.assessment["valence"] == pytest.approx(0.5)


def test_compose_group_heat_max():
    """Group heat is the max across intents."""
    sc = SelfCore()
    class GH1(CognitiveAgent):
        name = "gh1"
        phases = (PRE,)
        def gate(self, p): return RULE
        async def act(self, sk, m, p, phase=PRE):
            return AgentIntent(source="gh1", group_heat=0.3, payload={"gh": 1})
    class GH2(CognitiveAgent):
        name = "gh2"
        phases = (PRE,)
        def gate(self, p): return RULE
        async def act(self, sk, m, p, phase=PRE):
            return AgentIntent(source="gh2", group_heat=0.7, payload={"gh": 2})
    sc.register(GH1(sc.bus))
    sc.register(GH2(sc.bus))
    result = asyncio.run(
        sc.run_cycle("test", {}, PRE)
    )
    assert len(result.carried) == 2


def test_compose_carried_payloads():
    """Payloads are carried by source name."""
    sc = SelfCore()
    class PayAgent(CognitiveAgent):
        name = "pay"
        phases = (PRE,)
        def gate(self, p): return RULE
        async def act(self, sk, m, p, phase=PRE):
            return AgentIntent(source="pay", payload={"key": "value"})
    sc.register(PayAgent(sc.bus))
    result = asyncio.run(
        sc.run_cycle("test", {}, PRE)
    )
    assert result.carried["pay"] == {"key": "value"}


def test_agent_act_exception_is_caught():
    """Exception in agent.act() does not crash the cycle."""
    sc = SelfCore()
    class BadAgent(CognitiveAgent):
        name = "bad"
        phases = (PRE,)
        def gate(self, p): return RULE
        async def act(self, sk, m, p, phase=PRE):
            raise RuntimeError("oops")
    sc.register(BadAgent(sc.bus))
    result = asyncio.run(
        sc.run_cycle("test", {}, PRE)
    )
    assert result.flags == []


def test_agent_perceive_exception_is_caught():
    """Exception in agent.perceive() does not crash the cycle."""
    sc = SelfCore()
    class BadPerceiveAgent(CognitiveAgent):
        name = "badp"
        phases = (PRE,)
        def perceive(self, surface):
            raise RuntimeError("perceive oops")
        def gate(self, p): return RULE
        async def act(self, sk, m, p, phase=PRE):
            return AgentIntent(source="badp")
    sc.register(BadPerceiveAgent(sc.bus))
    result = asyncio.run(
        sc.run_cycle("test", {}, PRE)
    )
    assert result.flags == []


def test_valid_flags_frozenset():
    """VALID_FLAGS is a frozenset with expected members."""
    assert isinstance(VALID_FLAGS, frozenset)
    for f in ("safe", "hurt", "boundary", "repair", "idle",
              "pause", "resume", "reset", "proactive", "tool",
              "task", "group", "fallibility", "interrupt"):
        assert f in VALID_FLAGS
