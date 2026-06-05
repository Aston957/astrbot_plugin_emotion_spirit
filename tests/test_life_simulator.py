"""Tests for life_simulator.py"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock astrbot.api.logger
import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.surface_consumer import SurfaceConsumer, SemanticSignals
from emotion_spirit.memory_pool import MemoryPool
from emotion_spirit.intimacy import IntimacyTracker
from emotion_spirit.buffer_signals import BufferSignals
from emotion_spirit.meaning_reservoir import MeaningReservoir
from emotion_spirit.life_simulator import LifeSimulator


def _make_signals(**overrides) -> SemanticSignals:
    signals = SemanticSignals()
    for k, v in overrides.items():
        setattr(signals, k, v)
    return signals


def test_mode_a_trigger():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)

    # Add some entries
    pool.add("test", 0.5, 0.5, ["test"], "user1")

    # Force idle time
    sim._last_interaction = time.time() - 120  # 2 minutes ago

    result = sim.check_mode_a(_make_signals())
    assert result is not None
    assert result["type"] == "mode_a"


def test_mode_b_trigger():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)

    pool.add("test", 0.5, 0.5, ["test"], "user1")
    reservoir.level = 0.5
    sim._last_interaction = time.time() - 5 * 3600  # 5 hours ago
    sim._last_mode_b = time.time() - 10 * 3600

    sig = _make_signals(
        needs_expression=0.7,
        boundary_budget=0.5,
        boundary_cooldown=0,
        capacity_exhaustion=0.2,
        needs_quiet=0.1,
        body_criticality=0.2,
    )
    result = sim.check_mode_b(sig, "default")
    assert result is not None
    assert result["type"] == "mode_b"


def test_mode_b_blocked_cascade():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)

    sim._last_interaction = time.time() - 5 * 3600
    sim._last_mode_b = time.time() - 10 * 3600

    sig = _make_signals(
        needs_expression=0.7,
        boundary_budget=0.5,
        cascade_active=True,
        body_criticality=0.2,
    )
    result = sim.check_mode_b(sig, "default")
    assert result is None


def test_mode_b_blocked_exhaustion():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)

    sim._last_interaction = time.time() - 5 * 3600
    sim._last_mode_b = time.time() - 10 * 3600

    sig = _make_signals(
        needs_expression=0.7,
        boundary_budget=0.5,
        capacity_exhaustion=0.8,
        body_criticality=0.2,
    )
    result = sim.check_mode_b(sig, "default")
    assert result is None


def test_mode_b_interval_xiaofu():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)

    interval_low = sim._mode_b_interval("xiaofu", 0.1)
    interval_high = sim._mode_b_interval("xiaofu", 0.9)
    assert interval_low < interval_high  # Low density → faster


def test_mode_b_interval_xiaotian():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)

    interval_low = sim._mode_b_interval("xiaotian", 0.1)
    interval_high = sim._mode_b_interval("xiaotian", 0.9)
    assert interval_low < interval_high  # Low density → faster (same formula as xiaofu)


def test_serialization():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)
    data = sim.to_dict()
    sim2 = LifeSimulator(consumer, pool, intimacy, signals, reservoir)
    sim2.from_dict(data)
    assert sim2._turn_count == sim._turn_count


if __name__ == "__main__":
    test_mode_a_trigger()
    test_mode_b_trigger()
    test_mode_b_blocked_cascade()
    test_mode_b_blocked_exhaustion()
    test_mode_b_interval_xiaofu()
    test_mode_b_interval_xiaotian()
    test_serialization()
    print("All life_simulator tests passed!")
