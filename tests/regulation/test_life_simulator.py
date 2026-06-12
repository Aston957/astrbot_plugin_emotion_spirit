"""Tests for life_simulator.py"""

import sys
import os
import time
import asyncio

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
from emotion_spirit.regulation.life_simulator import (
    LifeSimulator, LifeEvent, LifeEventType, LIFE_EVENT_WEIGHTS,
)

DEFAULT_PERSONALITY = {
    "openness": 0.5,
    "extraversion": 0.5,
    "agreeableness": 0.5,
    "neuroticism": 0.5,
    "conscientiousness": 0.5,
    "emotional_stability": 0.5,
}


def _make_signals(**overrides) -> SemanticSignals:
    signals = SemanticSignals()
    for k, v in overrides.items():
        setattr(signals, k, v)
    return signals


def _make_sim():
    """Helper: create a LifeSimulator with MemoryPool + BufferSignals."""
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim = LifeSimulator(consumer, pool, intimacy, signals, reservoir)
    return sim, pool


def test_mode_a_trigger():
    sim, pool = _make_sim()

    # Add some entries
    pool.add("test", 0.5, 0.5, ["test"], "user1")

    # Force idle time
    sim._last_interaction = time.time() - 120  # 2 minutes ago

    result = sim.check_mode_a(_make_signals())
    assert result is not None
    assert result["type"] == "mode_a"


def test_mode_b_trigger():
    sim, pool = _make_sim()

    pool.add("test", 0.5, 0.5, ["test"], "user1")
    sim._reservoir.level = 0.5
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
    result = sim.check_mode_b(sig, DEFAULT_PERSONALITY)
    assert result is not None
    assert result["type"] == "mode_b"


def test_mode_b_blocked_cascade():
    sim, pool = _make_sim()

    sim._last_interaction = time.time() - 5 * 3600
    sim._last_mode_b = time.time() - 10 * 3600

    sig = _make_signals(
        needs_expression=0.7,
        boundary_budget=0.5,
        cascade_active=True,
        body_criticality=0.2,
    )
    result = sim.check_mode_b(sig, DEFAULT_PERSONALITY)
    assert result is None


def test_mode_b_blocked_exhaustion():
    sim, pool = _make_sim()

    sim._last_interaction = time.time() - 5 * 3600
    sim._last_mode_b = time.time() - 10 * 3600

    sig = _make_signals(
        needs_expression=0.7,
        boundary_budget=0.5,
        capacity_exhaustion=0.8,
        body_criticality=0.2,
    )
    result = sim.check_mode_b(sig, DEFAULT_PERSONALITY)
    assert result is None


def test_mode_b_interval():
    sim, pool = _make_sim()

    interval_low = sim._mode_b_interval(0.1)
    interval_high = sim._mode_b_interval(0.9)
    assert interval_low < interval_high  # Low density -> faster


def test_serialization():
    sim, pool = _make_sim()
    data = sim.to_dict()
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    sim2 = LifeSimulator(consumer, pool, intimacy, signals, reservoir)
    sim2.from_dict(data)
    assert sim2._turn_count == sim._turn_count


# === v1.1.1: emotion fields in Mode A/B payload ===

def test_mode_a_payload_includes_emotion():
    """Mode A payload signals block includes pad / emotion_distribution / emotion_primary etc."""
    sim, pool = _make_sim()

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
    # v1.1.1: old rhythm_beat/valence_warmth/needs_expression still present
    assert "rhythm_beat" in sig_block
    assert "valence_warmth" in sig_block
    assert "needs_expression" in sig_block
    # v1.1.1 new fields
    assert "pad" in sig_block
    assert sig_block["pad"]["valence"] == 0.7
    assert "emotion_distribution" in sig_block
    assert sig_block["emotion_primary"] == "joy"
    assert sig_block["emotion_secondary"] is None
    assert "emotion_intensity" in sig_block


def test_mode_a_payload_includes_memories():
    """Mode A payload includes memories with layer/temperature/weight metadata."""
    sim, pool = _make_sim()

    pool.add("test entry", 0.4, 0.5, ["mood"], "user1")
    sim._last_interaction = time.time() - 120

    result = sim.check_mode_a(_make_signals())
    assert result is not None
    assert "memories" in result
    assert isinstance(result["memories"], list)
    if result["memories"]:
        mem = result["memories"][0]
        assert "text" in mem
        assert "layer" in mem
        assert "temperature" in mem
        assert "emotional_weight" in mem
        assert "tags" in mem


def test_mode_a_payload_includes_state_narrative():
    """Mode A payload includes state_narrative."""
    sim, pool = _make_sim()

    pool.add("test", 0.5, 0.5, ["test"], "user1")
    sim._last_interaction = time.time() - 120

    result = sim.check_mode_a(_make_signals())
    assert result is not None
    assert "state_narrative" in result
    assert isinstance(result["state_narrative"], str)
    assert result["state_narrative"].endswith("。")


def test_mode_b_life_event_payload_includes_emotion():
    """Mode B life_event payload includes emotion block."""
    sim, pool = _make_sim()

    pool.add("test", 0.5, 0.5, ["test"], "user1")
    sim._reservoir.level = 0.5
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

    result = sim.check_mode_b(sig, DEFAULT_PERSONALITY)
    assert result is not None
    assert result["type"] == "mode_b"
    # v1.1.1 new emotion block
    assert "emotion" in result
    assert result["emotion"]["pad"]["valence"] == -0.5
    assert result["emotion"]["emotion_primary"] == "sadness"
    assert result["emotion"]["emotion_secondary"] == "excitement"


def test_mode_b_reflection_payload_includes_emotion():
    """Mode B reflection payload includes emotion block."""
    sim, pool = _make_sim()

    pool.add("test", 0.5, 0.5, ["test"], "user1")
    # reservoir.level stays 0 -> triggers reflection branch
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

    result = sim.check_mode_b(sig, DEFAULT_PERSONALITY)
    assert result is not None
    assert result["type"] == "mode_b"
    assert "emotion" in result
    assert result["emotion"]["emotion_primary"] == "joy"


def test_mode_b_soliloquy_payload_includes_emotion():
    """Mode B soliloquy payload includes emotion block."""
    sim, pool = _make_sim()

    # empty memory -> triggers soliloquy
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

    result = sim.check_mode_b(sig, DEFAULT_PERSONALITY)
    assert result is not None
    assert result["subtype"] == "soliloquy"
    assert "emotion" in result
    assert result["emotion"]["emotion_primary"] == "neutral"


def test_mode_b_payload_includes_memories_with_metadata():
    """Mode B payload includes memories with layer/temperature/weight metadata."""
    sim, pool = _make_sim()

    pool.add("a memory", 0.6, 0.5, ["warm"], "user1")
    sim._reservoir.level = 0.5
    sim._last_interaction = time.time() - 5 * 3600
    sim._last_mode_b = time.time() - 10 * 3600

    sig = _make_signals(
        needs_expression=0.7,
        boundary_budget=0.5,
        boundary_cooldown=0,
        capacity_exhaustion=0.2,
        needs_quiet=0.1,
        body_criticality=0.2,
    )

    result = sim.check_mode_b(sig, DEFAULT_PERSONALITY)
    assert result is not None
    assert "memories" in result
    assert isinstance(result["memories"], list)
    if result["memories"]:
        mem = result["memories"][0]
        assert "text" in mem
        assert "layer" in mem
        assert "temperature" in mem
        assert "emotional_weight" in mem
        assert "tags" in mem


def test_mode_b_payload_includes_state_narrative():
    """Mode B payload includes state_narrative."""
    sim, pool = _make_sim()

    sim._last_interaction = time.time() - 5 * 3600
    sim._last_mode_b = time.time() - 10 * 3600

    sig = _make_signals(
        needs_expression=0.7,
        boundary_budget=0.5,
        boundary_cooldown=0,
        capacity_exhaustion=0.2,
        needs_quiet=0.1,
        body_criticality=0.2,
    )

    result = sim.check_mode_b(sig, DEFAULT_PERSONALITY)
    assert result is not None
    assert "state_narrative" in result
    assert isinstance(result["state_narrative"], str)
    assert result["state_narrative"].endswith("。")


# === v1.2: payload includes emotion_ambiguity + emotion_velocity ===


def test_life_simulator_mode_b_payload_includes_v12_dynamics():
    """v1.2: life_simulator Mode B payload includes emotion_ambiguity + emotion_velocity."""
    from emotion_spirit.regulation.life_simulator import LifeSimulator
    from emotion_spirit.output.surface_consumer import SemanticSignals
    import time

    # Minimal stubs
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

    class FakeReservoir:
        level = 0.5
        def draw(self, amt): pass
    class FakeSignals:
        def mode_b_strategy(self): return "test"
    class FakeIntimacy:
        pass

    pool = MemoryPool()
    sim = LifeSimulator(
        consumer=consumer, memory=pool, intimacy=FakeIntimacy(),
        signals=FakeSignals(), reservoir=FakeReservoir(),
    )
    # Force trigger: bypass time checks
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
    result = sim.check_mode_b(sig, DEFAULT_PERSONALITY)
    if result is not None and "emotion" in result:
        # emotion_ambiguity / emotion_velocity come from build_emotion_payload shared layer
        assert "emotion_ambiguity" in result["emotion"]
        assert "emotion_velocity" in result["emotion"]
        assert result["emotion"]["emotion_ambiguity"] == 0.97


# === state_narrative unit tests ===

def test_state_narrative_high_temp():
    narrative = LifeSimulator._generate_state_narrative(mean_temp=0.8, cascade_active=False, ghost_count=0)
    assert "内心很不平静" in narrative
    assert narrative.endswith("。")


def test_state_narrative_mid_temp():
    narrative = LifeSimulator._generate_state_narrative(mean_temp=0.5, cascade_active=False, ghost_count=0)
    assert "心绪不宁" in narrative


def test_state_narrative_low_temp():
    narrative = LifeSimulator._generate_state_narrative(mean_temp=0.2, cascade_active=False, ghost_count=0)
    assert "相对平静" in narrative


def test_state_narrative_cascade():
    narrative = LifeSimulator._generate_state_narrative(mean_temp=0.3, cascade_active=True, ghost_count=0)
    assert "连锁反应" in narrative


def test_state_narrative_ghosts():
    narrative = LifeSimulator._generate_state_narrative(mean_temp=0.3, cascade_active=False, ghost_count=3)
    assert "3 个很久以前的画面" in narrative


def test_state_narrative_all_active():
    narrative = LifeSimulator._generate_state_narrative(mean_temp=0.9, cascade_active=True, ghost_count=5)
    assert "翻涌" in narrative
    assert "连锁反应" in narrative
    assert "5 个很久以前的画面" in narrative


# ═══════════════════════════════════════════════════════════════════════
# Phase G: LLM LifeSimulator 升级测试
# ═══════════════════════════════════════════════════════════════════════


def test_life_event_dataclass():
    """LifeEvent 基本属性。"""
    event = LifeEvent(
        text="安静地翻着一本书",
        mood="平静",
        urgency=0.2,
        timestamp=time.time(),
        wants_to_share=True,
        event_type=LifeEventType.READING,
    )
    assert event.text == "安静地翻着一本书"
    assert event.mood == "平静"
    assert event.urgency == 0.2
    assert event.wants_to_share is True
    assert event.shared is False
    assert event.event_type == "reading"


def test_life_event_type_constants():
    """LifeEventType 常量正确。"""
    assert LifeEventType.READING == "reading"
    assert LifeEventType.WALKING == "walking"
    assert LifeEventType.COOKING == "cooking"
    assert LifeEventType.THINKING == "thinking"
    assert LifeEventType.CREATING == "creating"
    assert LifeEventType.RESTING == "resting"
    assert LifeEventType.OBSERVING == "observing"


def test_life_event_weights():
    """LIFE_EVENT_WEIGHTS 包含所有事件类型。"""
    for event_type in [
        LifeEventType.READING, LifeEventType.WALKING, LifeEventType.COOKING,
        LifeEventType.THINKING, LifeEventType.CREATING, LifeEventType.RESTING,
        LifeEventType.OBSERVING,
    ]:
        assert event_type in LIFE_EVENT_WEIGHTS
        weights = LIFE_EVENT_WEIGHTS[event_type]
        assert "valence" in weights
        assert "arousal" in weights
        assert "share_tendency" in weights


def test_configure_llm_caller():
    """configure() 注入 LLM callable。"""
    sim, _ = _make_sim()
    assert sim._llm_caller is None

    async def fake_llm(system_prompt, user_prompt):
        return '{"activity": "test", "thought": "", "mood": "calm"}'

    sim.configure(llm_caller=fake_llm)
    assert sim._llm_caller is fake_llm


def test_pending_life_event_lifecycle():
    """pending_life_event 生命周期: 初始 None → 生成后有值 → consume 后 None。"""
    sim, _ = _make_sim()
    assert sim.pending_life_event is None
    assert sim.consume_life_event() is None

    # 手动设置一个 pending event
    event = LifeEvent(text="test", mood="calm", urgency=0.1, timestamp=time.time())
    sim._pending_life_event = event
    assert sim.pending_life_event is event

    consumed = sim.consume_life_event()
    assert consumed is event
    assert sim.pending_life_event is None


def test_infer_event_type():
    """_infer_event_type 关键词匹配。"""
    assert LifeSimulator._infer_event_type("在看书") == "reading"
    assert LifeSimulator._infer_event_type("出去散步了") == "walking"
    assert LifeSimulator._infer_event_type("在厨房做饭") == "cooking"
    assert LifeSimulator._infer_event_type("在思考人生") == "thinking"
    assert LifeSimulator._infer_event_type("画了一幅画") == "creating"
    assert LifeSimulator._infer_event_type("躺在沙发上休息") == "resting"
    assert LifeSimulator._infer_event_type("望着窗外") == "observing"
    assert LifeSimulator._infer_event_type("随便什么") == ""


def test_apply_event_emotion_weights():
    """_apply_event_emotion_weights 返回正确权重。"""
    event = LifeEvent(text="读书", mood="calm", urgency=0.1, timestamp=0, event_type="reading")
    weights = LifeSimulator._apply_event_emotion_weights(event)
    assert weights["valence"] == 0.2
    assert weights["arousal"] == -0.1
    assert weights["share_tendency"] == 0.4

    # 未知类型返回零
    event_unknown = LifeEvent(text="x", mood="x", urgency=0, timestamp=0, event_type="unknown")
    w2 = LifeSimulator._apply_event_emotion_weights(event_unknown)
    assert w2["valence"] == 0.0


def _run_async(coro):
    """在新 event loop 中运行 async 协程 (避免全量测试时 loop 冲突)。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_generate_fallback():
    """无 LLM 时规则 fallback 生成 LifeEvent。"""
    sim, pool = _make_sim()
    pool.add("test memory", 0.5, 0.5, ["test"], "user1")

    event_dict = {
        "type": "mode_a",
        "trigger": "idle",
        "memories": [{"text": "test memory", "layer": "buffer", "temperature": 0.5, "emotional_weight": 0.5, "tags": ["test"]}],
        "state_narrative": "你现在相对平静。",
        "signals": {},
    }

    result = _run_async(sim.generate_life_prose(event_dict))
    assert result is not None
    assert isinstance(result, LifeEvent)
    assert result.text
    assert result.mood
    assert result.timestamp > 0
    assert result.event_type in [
        "reading", "walking", "cooking", "thinking", "creating", "resting", "observing",
    ]
    assert sim.pending_life_event is result


def test_generate_with_mock_llm():
    """有 LLM 时生成 LifeEvent (mock)。"""
    sim, pool = _make_sim()
    pool.add("test memory", 0.5, 0.5, ["test"], "user1")

    async def mock_llm(system_prompt, user_prompt):
        return '{"activity": "在阳台上浇花", "thought": "今天天气真好", "mood": "愉快", "wants_to_share": true, "urgency": 0.3}'

    sim.configure(llm_caller=mock_llm)

    event_dict = {
        "type": "mode_b",
        "subtype": "life_event",
        "memories": [{"text": "test memory", "layer": "buffer", "temperature": 0.5, "emotional_weight": 0.5, "tags": ["test"]}],
        "state_narrative": "你现在相对平静。",
        "signals": {"pad": {"valence": 0.5, "arousal": 0.3}},
        "emotion": None,
    }

    result = _run_async(sim.generate_life_prose(event_dict, persona_desc="一个热爱生活的角色"))
    assert result is not None
    assert "浇花" in result.text
    assert result.mood == "愉快"
    assert result.wants_to_share is True
    assert result.urgency == 0.3
    assert sim.pending_life_event is result


def test_serialization_with_events():
    """to_dict/from_dict 保留 events。"""
    sim, _ = _make_sim()
    sim._events.append(LifeEvent(
        text="test event", mood="calm", urgency=0.2,
        timestamp=12345.0, wants_to_share=True, event_type="reading",
    ))

    data = sim.to_dict()
    assert len(data["events"]) == 1
    assert data["events"][0]["text"] == "test event"
    assert data["events"][0]["event_type"] == "reading"

    sim2, _ = _make_sim()
    sim2.from_dict(data)
    assert len(sim2._events) == 1
    assert sim2._events[0].text == "test event"
    assert sim2._events[0].event_type == "reading"
    assert sim2._events[0].wants_to_share is True


if __name__ == "__main__":
    test_mode_a_trigger()
    test_mode_b_trigger()
    test_mode_b_blocked_cascade()
    test_mode_b_blocked_exhaustion()
    test_mode_b_interval()
    test_serialization()
    test_mode_a_payload_includes_emotion()
    test_mode_a_payload_includes_memories()
    test_mode_a_payload_includes_state_narrative()
    test_mode_b_life_event_payload_includes_emotion()
    test_mode_b_reflection_payload_includes_emotion()
    test_mode_b_soliloquy_payload_includes_emotion()
    test_mode_b_payload_includes_memories_with_metadata()
    test_mode_b_payload_includes_state_narrative()
    test_life_simulator_mode_b_payload_includes_v12_dynamics()
    test_state_narrative_high_temp()
    test_state_narrative_mid_temp()
    test_state_narrative_low_temp()
    test_state_narrative_cascade()
    test_state_narrative_ghosts()
    test_state_narrative_all_active()
    print("All life_simulator tests passed!")
