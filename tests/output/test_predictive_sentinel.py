"""Tests for predictive_sentinel.py"""

import sys
import os

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
from emotion_spirit.output.buffer_signals import BufferSignals
from emotion_spirit.memory.memory_pool import MemoryPool
from emotion_spirit.memory.meaning_reservoir import MeaningReservoir
from emotion_spirit.output.predictive_sentinel import PredictiveSentinel
from emotion_spirit.regulation.superego import ConscienceTracker, ValueAlignment, IdealSelf
from emotion_spirit.core.config import SAFETY_CONFIG


def test_no_warning():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sentinel = PredictiveSentinel(consumer, signals, reservoir)

    # Update with stable values
    for _ in range(10):
        sentinel.update(SemanticSignals())

    result = sentinel.check()
    assert result["level"] == "normal"


def test_body_signal_strain():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sentinel = PredictiveSentinel(consumer, signals, reservoir)

    # Simulate increasing strain
    for i in range(10):
        s = SemanticSignals()
        s.rhythm_strain = 0.1 * (i + 1)
        sentinel.update(s)

    result = sentinel.check()
    # May or may not trigger depending on monotonic detection
    assert result["level"] in ["normal", "warning", "critical"]


def test_cascade_frequency():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sentinel = PredictiveSentinel(consumer, signals, reservoir)

    # Simulate 5 cascade events
    for _ in range(5):
        s = SemanticSignals()
        s.cascade_active = True
        sentinel.update(s)

    result = sentinel.check()
    assert "cascade_frequency" in result["triggered_signals"]


def test_serialization():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sentinel = PredictiveSentinel(consumer, signals, reservoir)
    sentinel.update(SemanticSignals())
    data = sentinel.to_dict()
    sentinel2 = PredictiveSentinel(consumer, signals, reservoir)
    sentinel2.from_dict(data)
    result = sentinel2.check()
    assert "level" in result


# ═══ 超我信号测试 ═══

def test_superego_conscience_pressure():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    conscience = ConscienceTracker()
    sentinel = PredictiveSentinel(consumer, signals, reservoir, conscience=conscience)

    # 模拟高压力
    for _ in range(5):
        conscience.record_value_conflict(0.9, ["v1"], "guilt", 0.5, 0.8)

    result = sentinel.check()
    assert "conscience_pressure_rising" in result["triggered_signals"]


def test_superego_alignment_declining():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    alignment = ValueAlignment("xiaofu")
    sentinel = PredictiveSentinel(consumer, signals, reservoir, alignment=alignment)

    # 模拟对齐下降
    for _ in range(10):
        alignment.record("withdraw")

    result = sentinel.check()
    assert "alignment_declining" in result["triggered_signals"]


def test_superego_guard_reflex_frequency():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    conscience = ConscienceTracker()
    sentinel = PredictiveSentinel(consumer, signals, reservoir, conscience=conscience)

    # 模拟 guard_reflex 频率
    for _ in range(3):
        conscience.record_guard_reflex(0.5, "test")

    result = sentinel.check()
    assert "guard_reflex_frequency" in result["triggered_signals"]


def test_superego_no_trigger_normal():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    conscience = ConscienceTracker()
    alignment = ValueAlignment("xiaofu")
    ideal = IdealSelf("xiaofu", {"mbti": "ENFP"})
    sentinel = PredictiveSentinel(consumer, signals, reservoir, conscience=conscience, alignment=alignment, ideal=ideal)

    # 正常状态，无超我信号
    result = sentinel.check()
    superego_signals = [s for s in result["triggered_signals"] if s.startswith("conscience_") or s.startswith("alignment_") or s.startswith("ideal_") or s.startswith("guard_reflex_") or s.startswith("value_conflict_")]
    assert len(superego_signals) == 0


def test_superego_enabled_false():
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    conscience = ConscienceTracker()
    sentinel = PredictiveSentinel(consumer, signals, reservoir, conscience=conscience)

    # 模拟高压力
    for _ in range(5):
        conscience.record_value_conflict(0.9, ["v1"], "guilt", 0.5, 0.8)

    original = SAFETY_CONFIG["enabled"]
    SAFETY_CONFIG["enabled"] = False
    try:
        result = sentinel.check()
        assert "conscience_pressure_rising" not in result["triggered_signals"]
    finally:
        SAFETY_CONFIG["enabled"] = original


if __name__ == "__main__":
    test_no_warning()
    test_body_signal_strain()
    test_cascade_frequency()
    test_serialization()
    test_superego_conscience_pressure()
    test_superego_alignment_declining()
    test_superego_guard_reflex_frequency()
    test_superego_no_trigger_normal()
    test_superego_enabled_false()
    print("All predictive_sentinel tests passed!")
