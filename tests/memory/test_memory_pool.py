"""Tests for memory_pool.py (Phase D: UnifiedEntry 统一架构)"""

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
    assert entry.emotional_weight == 0.7


def test_bypass_ghost():
    pool = MemoryPool()
    pool.add(text="betrayal!", raw_weight=0.95, phi=0.3, tags=["betrayal"], source_user="user1")
    assert len(pool.ghosts) == 1
    assert pool.ghosts[0].is_ghost


def test_recall_by_keyword():
    pool = MemoryPool()
    pool.add(text="今天很开心", raw_weight=0.5, phi=0.6, tags=["positive"], source_user="user1")
    pool.add(text="实验报告好难", raw_weight=0.6, phi=0.6, tags=["stress"], source_user="user1")
    # Phase D: confirm_check uses temperature-based gating
    # Set temperature high enough for promotion
    for e in pool.buffer:
        e.temperature = 0.6
    pool.confirm_check()
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


def test_confirm_check_temperature_gating():
    """Phase D: confirm_check 使用温度判定，不用 Φ 门控。"""
    pool = MemoryPool()
    # 高温度条目 → 提升到 warm
    pool.add(text="hot", raw_weight=0.8, phi=0.5, tags=["test"], source_user="user1")
    # 低温度条目 → 保留 buffer
    pool.add(text="cold", raw_weight=0.1, phi=0.5, tags=["test"], source_user="user1")
    # 手动设置温度
    pool.buffer[0].temperature = 0.6  # >= 0.5 → promote
    pool.buffer[1].temperature = 0.3  # < 0.5 → stay buffer

    promoted = pool.confirm_check()
    assert len(promoted) == 1
    assert promoted[0].text == "hot"
    assert len(pool.warm) == 1
    assert len(pool.buffer) == 1
    assert pool.buffer[0].text == "cold"


def test_entry_is_unified_entry():
    """Phase D: 所有 entry 都是 UnifiedEntry 实例。"""
    from emotion_spirit.memory.unified_entry import UnifiedEntry
    pool = MemoryPool()
    entry = pool.add("test", 0.5, 0.5, ["tag"], "user1")
    assert isinstance(entry, UnifiedEntry)
    # 通过 confirm_check 到 warm 的也是 UnifiedEntry
    entry.temperature = 0.6
    promoted = pool.confirm_check()
    assert len(promoted) == 1
    assert isinstance(promoted[0], UnifiedEntry)


if __name__ == "__main__":
    test_add_to_buffer()
    test_bypass_ghost()
    test_recall_by_keyword()
    test_buffer_max_size()
    test_sample_for_mode_b()
    test_serialization()
    test_confirm_check_temperature_gating()
    test_entry_is_unified_entry()
    print("All memory_pool tests passed!")
