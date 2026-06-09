"""Tests for memory_pool.py"""

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
astrbot_api_mock.logger.info = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.memory.memory_pool import MemoryPool


def test_add_to_buffer():
    pool = MemoryPool()
    entry = pool.add(text="今天很开心", raw_weight=0.7, phi=0.5, tags=["positive"], source_user="user1")
    assert entry is not None
    assert len(pool.buffer) == 1
    assert entry.raw_weight == 0.7


def test_phi_gate_confirm():
    pool = MemoryPool()
    pool.add(text="test", raw_weight=0.5, phi=0.6, tags=["test"], source_user="user1")
    confirmed = pool.confirm_check()
    assert len(confirmed) == 1  # phi=0.6 > threshold=0.4
    assert len(pool.warm) == 1
    assert len(pool.buffer) == 0


def test_phi_gate_reject():
    pool = MemoryPool()
    pool.add(text="test", raw_weight=0.01, phi=0.1, tags=["test"], source_user="user1")
    # Low phi AND low weight -> below noise threshold
    confirmed = pool.confirm_check()
    # phi_avg=0.1, meaning_gate=0.3+0.7*0.1=0.37, confirmed_weight=0.01*0.37=0.0037 < 0.05
    assert len(confirmed) == 0


def test_bypass_ghost():
    pool = MemoryPool()
    pool.add(text="betrayal!", raw_weight=0.95, phi=0.3, tags=["betrayal"], source_user="user1")
    assert len(pool.ghosts) == 1
    assert pool.ghosts[0].is_ghost


def test_recall_by_keyword():
    pool = MemoryPool()
    pool.add(text="今天很开心", raw_weight=0.5, phi=0.6, tags=["positive"], source_user="user1")
    pool.add(text="实验报告好难", raw_weight=0.6, phi=0.6, tags=["stress"], source_user="user1")
    pool.confirm_check()  # Move to warm
    results = pool.recall("开心")
    assert len(results) == 1
    assert "开心" in results[0].text


def test_buffer_max_size():
    pool = MemoryPool()
    for i in range(35):
        pool.add(f"text {i}", 0.5, 0.5, ["test"], "user1")
    assert len(pool.buffer) <= 30


def test_sample_for_mode_b():
    pool = MemoryPool()
    pool.add("high weight", 0.9, 0.5, ["test"], "user1")
    pool.add("low weight", 0.1, 0.5, ["test"], "user1")
    samples = pool.sample_for_mode_b(k=1)
    assert len(samples) == 1
    assert samples[0].text == "high weight"


def test_serialization():
    pool = MemoryPool()
    pool.add("test", 0.5, 0.6, ["tag1"], "user1")
    data = pool.to_dict()
    pool2 = MemoryPool.from_dict(data)
    assert len(pool2.buffer) == 1
    assert pool2.buffer[0].text == "test"


if __name__ == "__main__":
    test_add_to_buffer()
    test_phi_gate_confirm()
    test_phi_gate_reject()
    test_bypass_ghost()
    test_recall_by_keyword()
    test_buffer_max_size()
    test_sample_for_mode_b()
    test_serialization()
    print("All memory_pool tests passed!")
