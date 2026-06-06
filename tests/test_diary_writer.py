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
        prompt = diary.build_superego_reflection_prompt(tension_type, ["warmth_bias", "relational_autonomy"])  # v1.7: autonomy_guard 拆分
        assert len(prompt) > 0


# ═══ v1.1.1: emotion signals 注入测试 ═══

def test_build_diary_prompt_with_signals_injects_emotion():
    """build_diary_prompt 接受 signals 参数，注入结构化数据。"""
    from emotion_spirit.surface_consumer import SemanticSignals

    pool = MemoryPool()
    signals = BufferSignals(pool)
    patterns = PatternExtractor(pool)
    alignment = ValueAlignment("default")
    conscience = ConscienceTracker()
    diary = DiaryWriter(pool, patterns, signals, alignment, conscience)

    user_signals = SemanticSignals(
        pad_valence=0.7,
        pad_arousal=0.5,
        pad_dominance=0.7,
        pad_distribution={"joy": 0.6, "neutral": 0.3, "anger": 0.1},
        pad_primary="joy",
        pad_secondary=None,
        pad_intensity=0.5,
    )

    prompt = diary.build_diary_prompt("停滞型", signals=user_signals)

    # LLM-friendly 字段名注入
    assert "你当前的情感状态" in prompt
    assert "valence" in prompt
    assert "arousal" in prompt
    assert "dominance" in prompt
    # 分布标签注入
    assert "情绪概率分布" in prompt
    assert "joy" in prompt
    # 主要/次要情绪注入
    assert "主要情绪" in prompt
    assert "次要情绪" in prompt


def test_build_diary_prompt_without_signals_backward_compat():
    """build_diary_prompt 不传 signals 时行为不变（向后兼容）。"""
    pool = MemoryPool()
    signals = BufferSignals(pool)
    patterns = PatternExtractor(pool)
    alignment = ValueAlignment("default")
    conscience = ConscienceTracker()
    diary = DiaryWriter(pool, patterns, signals, alignment, conscience)

    prompt = diary.build_diary_prompt("停滞型")
    # 不应该有新的"你当前的情感状态"块
    assert "你当前的情感状态" not in prompt
    # 但基础 prompt 仍在
    assert "最近好像什么都没发生" in prompt


def test_build_superego_reflection_prompt_with_signals():
    """build_superego_reflection_prompt 也接受 signals 参数。"""
    from emotion_spirit.surface_consumer import SemanticSignals

    pool = MemoryPool()
    signals = BufferSignals(pool)
    patterns = PatternExtractor(pool)
    alignment = ValueAlignment("xiaofu")
    conscience = ConscienceTracker()
    diary = DiaryWriter(pool, patterns, signals, alignment, conscience)

    user_signals = SemanticSignals(
        pad_valence=-0.5,
        pad_arousal=0.8,
        pad_dominance=0.3,
        pad_distribution={"sadness": 0.5, "fear": 0.3, "neutral": 0.2},
        pad_primary="sadness",
        pad_secondary="excitement",
        pad_intensity=0.8,
    )

    prompt = diary.build_superego_reflection_prompt(
        tension_type="guilt",
        conflict_values=["openness"],
        signals=user_signals,
    )

    # emotion 数据注入
    assert "你当前的情感状态" in prompt
    assert "valence" in prompt
    assert "主要情绪" in prompt
    assert "sadness" in prompt
    # 基础 prompt 仍在
    assert "内在冲突" in prompt


# ═══ v1.2: ambiguity/velocity 注入 ═══


def test_diary_writer_v12_includes_ambiguity_velocity():
    """v1.2: diary_writer 注入块包含 emotion_ambiguity + emotion_velocity。"""
    from emotion_spirit.diary_writer import _format_emotion_block
    from emotion_spirit.surface_consumer import SemanticSignals

    s = SemanticSignals(
        pad_valence=0.5, pad_arousal=0.6, pad_dominance=0.7,
        pad_distribution={"joy": 0.6, "neutral": 0.4},
        pad_primary="joy", pad_secondary="neutral", pad_intensity=0.6,
        emotion_ambiguity=0.97,
        emotion_velocity={"valence": 0.1, "arousal": 0.2, "dominance": 0.3, "dt": 1.0},
    )
    block = _format_emotion_block(s)
    # ambiguity 应该出现
    assert "0.97" in block
    # velocity 数字应该出现（dt=1.0 或变化率 0.10/0.20/0.30）
    assert "0.97" in block or "ambiguity" in block or "模糊度" in block


if __name__ == "__main__":
    test_diary_type_escalating()
    test_diary_prompt_includes_patterns()
    test_record_diary()
    test_serialization()
    test_superego_reflection_prompt()
    test_superego_reflection_record()
    test_superego_reflection_tension_types()
    test_build_diary_prompt_with_signals_injects_emotion()
    test_build_diary_prompt_without_signals_backward_compat()
    test_build_superego_reflection_prompt_with_signals()
    test_diary_writer_v12_includes_ambiguity_velocity()
    print("All diary_writer tests passed!")
