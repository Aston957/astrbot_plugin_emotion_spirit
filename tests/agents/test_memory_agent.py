"""Tests for MemoryAgent (axis 1: recall + shadow detection)."""

import asyncio
import pytest
from unittest.mock import MagicMock

from emotion_spirit.agents.base import PRE, POST, RULE, SKIP, AgentIntent
from emotion_spirit.agents.event_bus import EventBus, ShadowDetected
from emotion_spirit.agents.memory_agent import MemoryAgent
from emotion_spirit.memory.memory_pool import MemoryPool


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    """Run async coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_pool_with_memory(text="今天很开心", weight=0.8):
    pool = MemoryPool()
    pool.add(text, weight, 0.5, ["mood"], "user")
    return pool


# ── perceive tests ───────────────────────────────────────────────────────────

def test_perceive_extracts_expected_keys():
    bus = EventBus()
    pool = MemoryPool()
    agent = MemoryAgent(bus, pool)

    surface = {
        "_phase": PRE,
        "intimacy_gravity": 0.7,
        "user_text": "hello",
        "echo_count": 3,
    }
    p = agent.perceive(surface)
    assert p["phase"] == PRE
    assert p["intimacy_gravity"] == 0.7
    assert p["user_text"] == "hello"
    assert p["echo_count"] == 3


def test_perceive_defaults():
    bus = EventBus()
    pool = MemoryPool()
    agent = MemoryAgent(bus, pool)

    p = agent.perceive({})
    assert p["phase"] == POST
    assert p["intimacy_gravity"] == 0.5
    assert p["user_text"] == ""
    assert p["echo_count"] == 0


# ── gate tests ───────────────────────────────────────────────────────────────

def test_gate_pre_high_intimacy_returns_rule():
    bus = EventBus()
    pool = MemoryPool()
    agent = MemoryAgent(bus, pool)
    assert agent.gate({"phase": PRE, "intimacy_gravity": 0.6}) == RULE


def test_gate_pre_low_intimacy_returns_skip():
    bus = EventBus()
    pool = MemoryPool()
    agent = MemoryAgent(bus, pool)
    assert agent.gate({"phase": PRE, "intimacy_gravity": 0.1}) == SKIP


def test_gate_pre_boundary_intimacy():
    """0.35 is the base threshold; 0.35 should pass (>=)."""
    bus = EventBus()
    pool = MemoryPool()
    agent = MemoryAgent(bus, pool)
    assert agent.gate({"phase": PRE, "intimacy_gravity": 0.35}) == RULE


def test_gate_pre_just_below_boundary():
    """0.34 is just below the 0.35 threshold."""
    bus = EventBus()
    pool = MemoryPool()
    agent = MemoryAgent(bus, pool)
    assert agent.gate({"phase": PRE, "intimacy_gravity": 0.34}) == SKIP


def test_gate_post_always_rule():
    bus = EventBus()
    pool = MemoryPool()
    agent = MemoryAgent(bus, pool)
    assert agent.gate({"phase": POST}) == RULE
    assert agent.gate({}) == RULE


def test_gate_pre_with_evo_delta():
    """Evolution delta shifts the threshold up."""
    bus = EventBus()
    pool = MemoryPool()
    agent = MemoryAgent(bus, pool)
    # threshold = 0.35 + 0.1 = 0.45
    evo_fn = lambda k: 0.1 if k == "intimacy_recall_threshold" else 0.0
    perceived = {"phase": PRE, "intimacy_gravity": 0.4, "_evo_delta": evo_fn}
    assert agent.gate(perceived) == SKIP  # 0.4 < 0.45

    perceived2 = {"phase": PRE, "intimacy_gravity": 0.5, "_evo_delta": evo_fn}
    assert agent.gate(perceived2) == RULE  # 0.5 >= 0.45


# ── act PRE (recall) tests ──────────────────────────────────────────────────

def test_recall_returns_intent_with_memories():
    bus = EventBus()
    pool = _make_pool_with_memory()
    agent = MemoryAgent(bus, pool)

    result = _run(agent.act("sk", RULE, {"user_text": "开心", "intimacy_gravity": 0.6}, PRE))
    assert result is not None
    assert isinstance(result, AgentIntent)
    assert result.source == "memory"
    assert "recalled_memories" in result.payload
    assert len(result.payload["recalled_memories"]) > 0


def test_recall_priority():
    bus = EventBus()
    pool = _make_pool_with_memory()
    agent = MemoryAgent(bus, pool)

    result = _run(agent.act("sk", RULE, {"user_text": "开心"}, PRE))
    assert result is not None
    assert result.priority == 0.4


def test_recall_empty_text_returns_none():
    bus = EventBus()
    pool = MemoryPool()
    agent = MemoryAgent(bus, pool)

    result = _run(agent.act("sk", RULE, {"user_text": ""}, PRE))
    assert result is None


def test_recall_no_match_returns_none():
    bus = EventBus()
    pool = _make_pool_with_memory(text="悲伤的事")
    agent = MemoryAgent(bus, pool)

    result = _run(agent.act("sk", RULE, {"user_text": "无关内容xyz"}, PRE))
    assert result is None


def test_recall_missing_user_text_returns_none():
    bus = EventBus()
    pool = MemoryPool()
    agent = MemoryAgent(bus, pool)

    result = _run(agent.act("sk", RULE, {}, PRE))
    assert result is None


# ── act POST (shadow detection) tests ────────────────────────────────────────

def test_post_no_shadow_returns_none():
    bus = EventBus()
    pool = MemoryPool()
    agent = MemoryAgent(bus, pool, shadow_detector=None)

    result = _run(agent.act("sk", RULE, {}, POST))
    assert result is None


def test_post_shadow_emits_event():
    """When shadow_detector detects shadows, a ShadowDetected event is emitted."""
    bus = EventBus()
    pool = MemoryPool()
    mock_shadow = MagicMock()
    mock_shadow.detect.return_value = [
        {"tag": "loneliness", "evidence": "echo_pattern", "confidence": 0.8},
        {"tag": "fear", "evidence": "avoidance_pattern", "confidence": 0.5},
    ]

    captured = []
    bus.subscribe(ShadowDetected, lambda e: captured.append(e))

    agent = MemoryAgent(bus, pool, shadow_detector=mock_shadow)
    result = _run(agent.act("session1", RULE, {}, POST))

    assert result is None  # POST act returns None
    assert len(captured) == 1
    assert captured[0].tags == ["loneliness", "fear"]
    assert captured[0].session_key == "session1"


def test_post_shadow_no_shadows_no_event():
    """When shadow_detector returns empty, no event is emitted."""
    bus = EventBus()
    pool = MemoryPool()
    mock_shadow = MagicMock()
    mock_shadow.detect.return_value = []

    captured = []
    bus.subscribe(ShadowDetected, lambda e: captured.append(e))

    agent = MemoryAgent(bus, pool, shadow_detector=mock_shadow)
    _run(agent.act("sk", RULE, {}, POST))

    assert len(captured) == 0


def test_post_shadow_exception_is_swallowed():
    """If shadow_detector.detect() raises, the exception is swallowed."""
    bus = EventBus()
    pool = MemoryPool()
    mock_shadow = MagicMock()
    mock_shadow.detect.side_effect = RuntimeError("boom")

    agent = MemoryAgent(bus, pool, shadow_detector=mock_shadow)
    # Should not raise
    result = _run(agent.act("sk", RULE, {}, POST))
    assert result is None


# ── integration: perceive -> gate -> act ─────────────────────────────────────

def test_full_pipeline_pre_high_intimacy():
    """High intimacy: perceive -> gate(RULE) -> recall returns intent."""
    bus = EventBus()
    pool = _make_pool_with_memory(text="今天特别开心的事")
    agent = MemoryAgent(bus, pool)

    surface = {"_phase": PRE, "intimacy_gravity": 0.7, "user_text": "开心"}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == RULE

    result = _run(agent.act("sk", gate_result, perceived, PRE))
    assert result is not None
    assert "recalled_memories" in result.payload


def test_full_pipeline_pre_low_intimacy():
    """Low intimacy: perceive -> gate(SKIP) -> act is never called."""
    bus = EventBus()
    pool = _make_pool_with_memory()
    agent = MemoryAgent(bus, pool)

    surface = {"_phase": PRE, "intimacy_gravity": 0.1}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == SKIP


def test_full_pipeline_post():
    """POST phase: perceive -> gate(RULE) -> shadow detection."""
    bus = EventBus()
    pool = MemoryPool()
    mock_shadow = MagicMock()
    mock_shadow.detect.return_value = [{"tag": "test_shadow"}]

    captured = []
    bus.subscribe(ShadowDetected, lambda e: captured.append(e))

    agent = MemoryAgent(bus, pool, shadow_detector=mock_shadow)
    surface = {"_phase": POST}
    perceived = agent.perceive(surface)
    gate_result = agent.gate(perceived)
    assert gate_result == RULE

    result = _run(agent.act("sk", gate_result, perceived, POST))
    assert result is None
    assert len(captured) == 1
