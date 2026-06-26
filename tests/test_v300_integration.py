"""v3.0.0 集成测试 — Phase I 端到端验证 (T2: v1 LifeSimulator 测试已移除)。

测试 v3.0.0 的核心数据流:
1. MemoryPool flat 存储 + participant 过滤
2. LifeSimulator LLM 生活片段生成 + MemoryPool 写入 (T2: removed, v1 deleted)
3. BotDecision proactive 上下文注入 (T2: removed, v1 deleted)
4. on_llm_response 情绪提取
5. 版本一致性
"""

import sys
import os
import time
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.debug = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.memory.memory_pool import MemoryPool
from emotion_spirit.memory.intimacy import IntimacyTracker
from emotion_spirit.output.surface_consumer import SurfaceConsumer, SemanticSignals
from emotion_spirit.output.buffer_signals import BufferSignals
from emotion_spirit.output.bot_decision import BotDecisionMaker
from emotion_spirit.memory.meaning_reservoir import MeaningReservoir
from emotion_spirit.regulation.life_simulator import (
    LifeSimulator, LifeEvent, LifeEventType, LIFE_EVENT_WEIGHTS,
)


def _make_sim():
    """Helper: create LifeSimulator with all deps."""
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)
    return sim, pool, consumer, intimacy, reservoir


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ═══ 1. MemoryPool flat 存储 ═══


class TestMemoryPoolFlat:
    """Phase D: flat 存储 + participant 过滤。"""

    def test_flat_buffer_no_per_user_pools(self):
        """buffer 是 flat 列表, 不按 user 分池。"""
        pool = MemoryPool()
        pool.add("msg1", 0.5, 0.5, ["t"], "user1")
        pool.add("msg2", 0.5, 0.5, ["t"], "user2")
        assert len(pool.buffer) == 2

    def test_participant_filter(self):
        """buffer_in(user_id) 按 participant 过滤。"""
        pool = MemoryPool()
        pool.add("msg1", 0.5, 0.5, ["t"], "user1")
        pool.add("msg2", 0.5, 0.5, ["t"], "user2")
        u1_entries = list(pool.buffer_in("user1"))
        assert len(u1_entries) == 1
        assert u1_entries[0].text == "msg1"


# ═══ 2. LifeSimulator + MemoryPool 写入 (v1 Phase G — removed in T2) ═══
# Tests for v1 generate_life_prose() removed; v1 method bodies deleted from
# emotion_spirit/regulation/life_simulator.py. v2 (LifeSimulatorV2) handles
# daily plan generation separately.


# ═══ 3. BotDecision proactive 上下文 (v1 Phase G — removed in T2) ═══
# TestBotDecisionLifeEvent removed; depends on v1 generate_life_prose which
# no longer exists on LifeSimulator stub.


# ═══ 4. on_llm_response 情绪提取 ═══


class TestBotEmotionExtraction:
    """Phase H: _extract_bot_emotion 规则。"""

    def test_all_tones(self):
        """覆盖所有情绪类型。"""
        from main import EmotionSpiritPlugin
        cases = [
            ("哈哈好的", "warm"),
            ("不好意思", "apologetic"),
            ("你觉得呢？", "curious"),
            ("很长的回复" * 50, "detailed"),
            ("好的", "neutral"),
            ("", "neutral"),
        ]
        for text, expected_tone in cases:
            tone, weight = EmotionSpiritPlugin._extract_bot_emotion(text)
            assert tone == expected_tone, f"text={text!r} expected={expected_tone} got={tone}"
            assert 0.0 < weight <= 1.0


# ═══ 5. 版本一致性 ═══


class TestVersionConsistency:
    """Phase I: 版本号在 _version.py 和 metadata.yaml 一致。"""

    def test_version_string(self):
        from emotion_spirit._version import __version__
        assert __version__ == "1.0.0"

    def test_metadata_version(self):
        import yaml
        meta_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "metadata.yaml",
        )
        with open(meta_path, encoding="utf-8") as f:
            meta = yaml.safe_load(f)
        assert meta["version"] == "1.0.0"


# ═══ 6. LifeEvent 事件类型完整性 ═══


class TestLifeEventTypes:
    """Phase G: 7 种事件类型全部有权重。"""

    def test_all_types_have_weights(self):
        for event_type in [
            LifeEventType.READING, LifeEventType.WALKING, LifeEventType.COOKING,
            LifeEventType.THINKING, LifeEventType.CREATING, LifeEventType.RESTING,
            LifeEventType.OBSERVING,
        ]:
            assert event_type in LIFE_EVENT_WEIGHTS
            w = LIFE_EVENT_WEIGHTS[event_type]
            assert "valence" in w
            assert "arousal" in w
            assert "share_tendency" in w

    def test_weights_in_valid_range(self):
        for event_type, w in LIFE_EVENT_WEIGHTS.items():
            assert -1.0 <= w["valence"] <= 1.0, f"{event_type} valence out of range"
            assert -1.0 <= w["arousal"] <= 1.0, f"{event_type} arousal out of range"
            assert 0.0 <= w["share_tendency"] <= 1.0, f"{event_type} share_tendency out of range"
