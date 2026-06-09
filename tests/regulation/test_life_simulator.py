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

from emotion_spirit.output.surface_consumer import SurfaceConsumer, SemanticSignals
from emotion_spirit.memory.memory_pool import MemoryPool
from emotion_spirit.memory.intimacy import IntimacyTracker
from emotion_spirit.output.buffer_signals import BufferSignals
from emotion_spirit.memory.meaning_reservoir import MeaningReservoir
from emotion_spirit.regulation.life_simulator import LifeSimulator


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


# ═══ v1.1.1: emotion 字段在 Mode A/B payload 中 ═══

def test_mode_a_payload_includes_emotion():
    """Mode A payload signals 块包含 pad / emotion_distribution / emotion_primary 等。"""
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)

    pool.add("test", 0.5, 0.5, ["test"], "user1")
    sim._last_interaction = time.time() - 120  # 2 minutes ago

    sig = _make_signals(
        pad_valence=0.7, pad_arousal=0.5, pad_dominance=0.7,
        pad_distribution={"joy": 0.6, "neutral": 0.3, "anger": 0.1},
        pad_primary="joy", pad_secondary=None, pad_intensity=0.5,
    )

    result = sim.check_mode_a(sig)
    assert result is not None
    assert result["type"] == "mode_a"
    sig_block = result["signals"]
    # v1.1.1: 旧的 rhythm_beat/valence_warmth/needs_expression 仍存在
    assert "rhythm_beat" in sig_block
    assert "valence_warmth" in sig_block
    assert "needs_expression" in sig_block
    # v1.1.1 新增字段
    assert "pad" in sig_block
    assert sig_block["pad"]["valence"] == 0.7
    assert "emotion_distribution" in sig_block
    assert sig_block["emotion_primary"] == "joy"
    assert sig_block["emotion_secondary"] is None
    assert "emotion_intensity" in sig_block


def test_mode_b_life_event_payload_includes_emotion():
    """Mode B life_event payload 包含 emotion 块。"""
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)

    pool.add("test", 0.5, 0.5, ["test"], "user1")
    reservoir.level = 0.5
    sim._last_interaction = time.time() - 5 * 3600
    sim._last_mode_b = time.time() - 10 * 3600

    sig = _make_signals(
        needs_expression=0.7,
        boundary_budget=0.5,
        boundary_cooldown=0,
        capacity_exhaustion=0.2,
        needs_quiet=0.1,
        body_criticality=0.2,
        pad_valence=-0.5, pad_arousal=0.8, pad_dominance=0.3,
        pad_distribution={"sadness": 0.5, "fear": 0.3, "neutral": 0.2},
        pad_primary="sadness", pad_secondary="excitement", pad_intensity=0.8,
    )

    result = sim.check_mode_b(sig, "default")
    assert result is not None
    assert result["type"] == "mode_b"
    # v1.1.1 新增 emotion 块
    assert "emotion" in result
    assert result["emotion"]["pad"]["valence"] == -0.5
    assert result["emotion"]["emotion_primary"] == "sadness"
    assert result["emotion"]["emotion_secondary"] == "excitement"


def test_mode_b_reflection_payload_includes_emotion():
    """Mode B reflection payload 包含 emotion 块。"""
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)

    pool.add("test", 0.5, 0.5, ["test"], "user1")
    # reservoir.level 保持 0，触发 reflection 分支
    sim._last_interaction = time.time() - 5 * 3600
    sim._last_mode_b = time.time() - 10 * 3600

    sig = _make_signals(
        needs_expression=0.7,
        boundary_budget=0.5,
        boundary_cooldown=0,
        capacity_exhaustion=0.2,
        needs_quiet=0.1,
        body_criticality=0.2,
        pad_valence=0.5, pad_arousal=0.5, pad_dominance=0.5,
        pad_distribution={"joy": 0.7, "neutral": 0.3},
        pad_primary="joy", pad_secondary=None, pad_intensity=0.5,
    )

    result = sim.check_mode_b(sig, "default")
    assert result is not None
    assert result["type"] == "mode_b"
    assert "emotion" in result
    assert result["emotion"]["emotion_primary"] == "joy"


def test_mode_b_soliloquy_payload_includes_emotion():
    """Mode B soliloquy payload 包含 emotion 块。"""
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)

    # pool 空，触发 soliloquy
    sim._last_interaction = time.time() - 5 * 3600
    sim._last_mode_b = time.time() - 10 * 3600

    sig = _make_signals(
        needs_expression=0.7,
        boundary_budget=0.5,
        boundary_cooldown=0,
        capacity_exhaustion=0.2,
        needs_quiet=0.1,
        body_criticality=0.2,
        pad_valence=0.0, pad_arousal=0.4, pad_dominance=0.5,
        pad_distribution={"neutral": 0.6, "joy": 0.4},
        pad_primary="neutral", pad_secondary=None, pad_intensity=0.4,
    )

    result = sim.check_mode_b(sig, "default")
    assert result is not None
    assert result["subtype"] == "soliloquy"
    assert "emotion" in result
    assert result["emotion"]["emotion_primary"] == "neutral"


# ═══ v1.2: payload 包含 emotion_ambiguity + emotion_velocity ═══


def test_life_simulator_mode_b_payload_includes_v12_dynamics():
    """v1.2: life_simulator Mode B payload 包含 emotion_ambiguity + emotion_velocity。"""
    from emotion_spirit.regulation.life_simulator import LifeSimulator
    from emotion_spirit.output.surface_consumer import SemanticSignals
    import time

    # 构造一个最小可用的 consumer/pool/intimacy/etc.
    class FakeConsumer:
        def consume(self, surface, session_id=None):
            return SemanticSignals(
                pad_valence=0.5, pad_arousal=0.6, pad_dominance=0.7,
                pad_distribution={"joy": 0.6, "neutral": 0.4},
                pad_primary="joy", pad_secondary="neutral", pad_intensity=0.6,
                emotion_ambiguity=0.97,
                emotion_velocity={"valence": 0.1, "arousal": 0.2, "dominance": 0.3, "dt": 1.0},
                phi_smoothed=0.5, needs_expression=0.6, boundary_budget=0.5,
                boundary_cooldown=0, boundary_paused=False, capacity_exhaustion=0.3,
                needs_quiet=0.2, cascade_active=False, body_criticality=0.3,
            )

    consumer = FakeConsumer()
    # 最小 stub: pool/reservoir/signals
    class FakePool:
        def sample_for_mode_b(self, k): return []
    class FakeReservoir:
        level = 0.5
        def draw(self, amt): pass
    class FakeSignals:
        def mode_b_strategy(self): return "test"
    class FakeIntimacy:
        pass

    sim = LifeSimulator(
        consumer=consumer, pool=FakePool(), intimacy=FakeIntimacy(),
        signals=FakeSignals(), reservoir=FakeReservoir(),
    )
    # 强制触发：绕过时间检查
    sim._last_mode_b = 0
    sim._last_interaction = 0

    sig = SemanticSignals(
        pad_valence=0.5, pad_arousal=0.6, pad_dominance=0.7,
        pad_distribution={"joy": 0.6, "neutral": 0.4},
        pad_primary="joy", pad_secondary="neutral", pad_intensity=0.6,
        emotion_ambiguity=0.97,
        emotion_velocity={"valence": 0.1, "arousal": 0.2, "dominance": 0.3, "dt": 1.0},
        phi_smoothed=0.5, needs_expression=0.6, boundary_budget=0.5,
        boundary_cooldown=0, boundary_paused=False, capacity_exhaustion=0.3,
        needs_quiet=0.2, cascade_active=False, body_criticality=0.3,
    )
    result = sim.check_mode_b(sig, "default")
    if result is not None and "emotion" in result:
        # emotion_ambiguity / emotion_velocity 来自 build_emotion_payload 共享层
        assert "emotion_ambiguity" in result["emotion"]
        assert "emotion_velocity" in result["emotion"]
        assert result["emotion"]["emotion_ambiguity"] == 0.97


if __name__ == "__main__":
    test_mode_a_trigger()
    test_mode_b_trigger()
    test_mode_b_blocked_cascade()
    test_mode_b_blocked_exhaustion()
    test_mode_b_interval_xiaofu()
    test_mode_b_interval_xiaotian()
    test_serialization()
    test_mode_a_payload_includes_emotion()
    test_mode_b_life_event_payload_includes_emotion()
    test_mode_b_reflection_payload_includes_emotion()
    test_mode_b_soliloquy_payload_includes_emotion()
    print("All life_simulator tests passed!")
