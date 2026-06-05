"""Tests for diary_writer.py"""

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

from emotion_spirit.memory_pool import MemoryPool
from emotion_spirit.pattern_extractor import PatternExtractor
from emotion_spirit.buffer_signals import BufferSignals
from emotion_spirit.superego import ValueAlignment, ConscienceTracker
from emotion_spirit.diary_writer import DiaryWriter


def test_diary_type_escalating():
    pool = MemoryPool()
    pool.add("high", 0.9, 0.5, ["test"], "user1")
    pool.add("higher", 0.95, 0.5, ["test"], "user1")
    pool.add("highest", 1.0, 0.5, ["test"], "user1")

    signals = BufferSignals(pool)
    patterns = PatternExtractor(pool)
    alignment = ValueAlignment("default")
    conscience = ConscienceTracker()

    diary = DiaryWriter(pool, patterns, signals, alignment, conscience)
    diary_type = diary.determine_diary_type()
    assert diary_type in ["上升型", "下降型", "停滞型", "循环型"]


def test_diary_prompt_includes_patterns():
    pool = MemoryPool()
    signals = BufferSignals(pool)
    patterns = PatternExtractor(pool)
    alignment = ValueAlignment("default")
    conscience = ConscienceTracker()

    diary = DiaryWriter(pool, patterns, signals, alignment, conscience)
    prompt = diary.build_diary_prompt("停滞型")
    assert "日记" in prompt or "平静" in prompt


def test_record_diary():
    pool = MemoryPool()
    signals = BufferSignals(pool)
    patterns = PatternExtractor(pool)
    alignment = ValueAlignment("default")
    conscience = ConscienceTracker()

    diary = DiaryWriter(pool, patterns, signals, alignment, conscience)
    entry = diary.record_diary("今天很平静", "停滞型")
    assert entry["text"] == "今天很平静"
    assert entry["type"] == "停滞型"
    assert len(diary.get_recent_diary()) == 1


def test_serialization():
    pool = MemoryPool()
    signals = BufferSignals(pool)
    patterns = PatternExtractor(pool)
    alignment = ValueAlignment("default")
    conscience = ConscienceTracker()

    diary = DiaryWriter(pool, patterns, signals, alignment, conscience)
    diary.record_diary("test", "停滞型")
    data = diary.to_dict()
    diary2 = DiaryWriter(pool, patterns, signals, alignment, conscience)
    diary2.from_dict(data)
    assert len(diary2.get_recent_diary()) == 1


# ═══ 超我反思日记测试 ═══

def test_superego_reflection_prompt():
    pool = MemoryPool()
    signals = BufferSignals(pool)
    patterns = PatternExtractor(pool)
    alignment = ValueAlignment("xiaofu")
    conscience = ConscienceTracker()

    diary = DiaryWriter(pool, patterns, signals, alignment, conscience)

    # 模拟高压力
    for _ in range(5):
        conscience.record_value_conflict(0.9, ["真诚"], "guilt", 0.5, 0.8)

    prompt = diary.build_superego_reflection_prompt("guilt", ["真诚"])
    assert "内在冲突" in prompt or "冲突" in prompt
    assert "真诚" in prompt


def test_superego_reflection_record():
    pool = MemoryPool()
    signals = BufferSignals(pool)
    patterns = PatternExtractor(pool)
    alignment = ValueAlignment("xiaofu")
    conscience = ConscienceTracker()

    diary = DiaryWriter(pool, patterns, signals, alignment, conscience)

    # 模拟高压力
    for _ in range(5):
        conscience.record_value_conflict(0.9, ["真诚"], "guilt", 0.5, 0.8)

    prompt = diary.build_superego_reflection_prompt("guilt", ["真诚"])
    entry = diary.record_diary(prompt, "superego_reflection")
    assert entry["type"] == "superego_reflection"
    assert len(diary.get_recent_diary()) == 1


def test_superego_reflection_tension_types():
    pool = MemoryPool()
    signals = BufferSignals(pool)
    patterns = PatternExtractor(pool)
    alignment = ValueAlignment("xiaofu")
    conscience = ConscienceTracker()

    diary = DiaryWriter(pool, patterns, signals, alignment, conscience)

    # 测试不同 tension_type
    for tension_type in ["guilt", "shame", "doubt", "righteous"]:
        prompt = diary.build_superego_reflection_prompt(tension_type, ["warmth_bias", "autonomy_guard"])
        assert len(prompt) > 0


if __name__ == "__main__":
    test_diary_type_escalating()
    test_diary_prompt_includes_patterns()
    test_record_diary()
    test_serialization()
    test_superego_reflection_prompt()
    test_superego_reflection_record()
    test_superego_reflection_tension_types()
    print("All diary_writer tests passed!")
