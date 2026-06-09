"""Tests for buffer_signals.py"""

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

from emotion_spirit.memory.memory_pool import MemoryPool
from emotion_spirit.output.buffer_signals import BufferSignals


def test_momentum_escalating():
    pool = MemoryPool()
    pool.add("low", 0.1, 0.5, ["test"], "user1")
    time.sleep(0.01)
    pool.add("mid", 0.5, 0.5, ["test"], "user1")
    time.sleep(0.01)
    pool.add("high", 0.9, 0.5, ["test"], "user1")
    signals = BufferSignals(pool)
    momentum = signals.emotional_momentum()
    assert momentum["direction"] == "escalating"


def test_temperature_empty():
    pool = MemoryPool()
    signals = BufferSignals(pool)
    assert signals.buffer_temperature() == 0.0


def test_temperature_nonempty():
    pool = MemoryPool()
    for i in range(20):
        pool.add(f"test {i}", 0.5, 0.5, ["test"], "user1")
    signals = BufferSignals(pool)
    temp = signals.buffer_temperature()
    assert temp > 0


def test_echo_detection():
    pool = MemoryPool()
    for i in range(4):
        pool.add(f"test {i}", 0.5, 0.5, ["hurt"], "user1")
    signals = BufferSignals(pool)
    echoes = signals.echo_patterns()
    assert any(e["tag"] == "hurt" for e in echoes)


def test_mode_b_strategy_empty():
    pool = MemoryPool()
    signals = BufferSignals(pool)
    assert signals.mode_b_strategy() == "exploratory"


def test_confirmation_velocity_default():
    pool = MemoryPool()
    signals = BufferSignals(pool)
    assert signals.confirmation_velocity() == 0.5  # Default when no history


if __name__ == "__main__":
    test_momentum_escalating()
    test_temperature_empty()
    test_temperature_nonempty()
    test_echo_detection()
    test_mode_b_strategy_empty()
    test_confirmation_velocity_default()
    print("All buffer_signals tests passed!")
