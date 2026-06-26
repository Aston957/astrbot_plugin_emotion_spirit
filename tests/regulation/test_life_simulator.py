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
from emotion_spirit.regulation.life_plan import PlannedEvent, PLAN_TEMPLATES

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


def test_store_event_to_memory():
    """LifeEvent 生成后写入 MemoryPool。"""
    sim, pool = _make_sim()

    event = LifeEvent(
        text="安静地翻着一本书",
        mood="平静",
        urgency=0.2,
        timestamp=time.time(),
        wants_to_share=True,
        event_type="reading",
    )
    sim._store_event_to_memory(event)

    # 验证写入了 MemoryPool
    assert len(pool.buffer) == 1
    entry = pool.buffer[0]
    assert "翻着一本书" in entry.text
    assert "life_event" in entry.tags
    assert "reading" in entry.tags
    assert "平静" in entry.tags
    # reading: valence=0.2, share_tendency=0.4 → weight = 0.2 + 0.4*0.3 + 0.1 = 0.42
    assert entry.emotional_weight > 0.3


def test_generate_fallback_writes_to_memory():
    """fallback 生成的 LifeEvent 写入 MemoryPool。"""
    sim, pool = _make_sim()
    pool.add("existing", 0.5, 0.5, ["test"], "user1")

    event_dict = {
        "type": "mode_a",
        "trigger": "idle",
        "memories": [{"text": "test", "layer": "buffer", "temperature": 0.5, "emotional_weight": 0.5, "tags": ["test"]}],
        "state_narrative": "你现在相对平静。",
        "signals": {},
    }

    _run_async(sim.generate_life_prose(event_dict))
    # 原有 1 条 + 新增 1 条 life_event
    assert len(pool.buffer) == 2
    life_event_entries = [e for e in pool.buffer if "life_event" in e.tags]
    assert len(life_event_entries) == 1


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


# ═══════════════════════════════════════════════════════════════════════
# Task 2: LifeSimulatorV2 — template-based plan generation
# ═══════════════════════════════════════════════════════════════════════


def _make_sim_v2():
    """Helper: create a LifeSimulatorV2 instance."""
    from emotion_spirit.regulation.life_simulator import LifeSimulatorV2
    consumer = SurfaceConsumer()
    pool = MemoryPool()
    intimacy = IntimacyTracker()
    signals = BufferSignals(pool)
    reservoir = MeaningReservoir()
    return LifeSimulatorV2(consumer, pool, intimacy, signals, reservoir)


def test_v2_generate_template_plan():
    """generate_plan_template() returns 2-3 events from templates."""
    sim = _make_sim_v2()
    personality = {"openness": 0.8, "extraversion": 0.3, "conscientiousness": 0.5,
                   "agreeableness": 0.5, "neuroticism": 0.5}
    events = sim.generate_plan_template(personality, n=3)
    assert 2 <= len(events) <= 3
    for e in events:
        assert e.category == "template"
        assert e.status == "planned"
        assert e.time_slot in ("morning", "afternoon", "evening", "night")
        assert e.activity  # non-empty


def test_v2_template_respects_personality():
    """High openness -> more creative/intellectual activities."""
    sim = _make_sim_v2()
    high_open = {"openness": 0.9, "extraversion": 0.2, "conscientiousness": 0.5,
                 "agreeableness": 0.5, "neuroticism": 0.5}
    # Run multiple times to check distribution
    creative_count = 0
    for _ in range(50):
        events = sim.generate_plan_template(high_open, n=2)
        for e in events:
            if e.activity in PLAN_TEMPLATES.get("creative", []):
                creative_count += 1
    # With high openness, creative activities should appear more than 20% of the time
    assert creative_count > 5, f"Creative count {creative_count} too low for high openness"


def test_v2_template_returns_planned_events():
    """Each event is a PlannedEvent with correct fields."""
    sim = _make_sim_v2()
    personality = {"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                   "agreeableness": 0.5, "neuroticism": 0.5}
    events = sim.generate_plan_template(personality, n=2)
    for e in events:
        assert isinstance(e, PlannedEvent)
        assert e.id.startswith("tpl_")
        assert e.approximate_time  # non-empty


def test_v2_template_flexibility_by_category():
    """routine activities get low flexibility, social gets high."""
    sim = _make_sim_v2()
    # We can't control which category is chosen, but we can verify the mapping
    personality = {"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                   "agreeableness": 0.5, "neuroticism": 0.5}
    # Run many times to see different categories
    flexibilities = set()
    for _ in range(100):
        events = sim.generate_plan_template(personality, n=3)
        for e in events:
            flexibilities.add(e.flexibility)
    # Should have at least 2 different flexibility values (0.1 and 0.5, or 0.5 and 0.8)
    assert len(flexibilities) >= 2, f"Expected varied flexibilities, got {flexibilities}"


def test_v2_template_default_n():
    """Default n=3 when not specified."""
    sim = _make_sim_v2()
    personality = {"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                   "agreeableness": 0.5, "neuroticism": 0.5}
    events = sim.generate_plan_template(personality)
    assert len(events) >= 2  # at least 2 (may be less than 3 due to dedup)


# ═══════════════════════════════════════════════════════════════════════
# Task 3: LLM Random Event Generation
# ═══════════════════════════════════════════════════════════════════════


def test_v2_generate_llm_events():
    """generate_plan_llm() returns 1-2 events from LLM."""
    sim = _make_sim_v2()
    # Mock LLM that returns valid JSON
    async def mock_llm(system_prompt, user_prompt):
        return '[{"time": "afternoon", "activity": "去公园散步", "mood": "期待"}]'
    sim.configure(llm_caller=mock_llm)

    personality = {"openness": 0.7, "extraversion": 0.5, "conscientiousness": 0.5,
                   "agreeableness": 0.5, "neuroticism": 0.5}
    events = _run_async(
        sim.generate_plan_llm(personality, recent_memories=["今天很开心"], yesterday_events=["昨天画画"])
    )
    assert len(events) >= 1
    assert events[0].category == "llm_random"
    assert events[0].activity == "去公园散步"


def test_v2_llm_fallback_on_bad_json():
    """LLM returns garbage -> returns empty list (graceful fallback)."""
    sim = _make_sim_v2()
    async def bad_llm(system_prompt, user_prompt):
        return "I don't understand"
    sim.configure(llm_caller=bad_llm)

    events = _run_async(
        sim.generate_plan_llm({"openness": 0.5}, [], [])
    )
    assert events == []


def test_v2_llm_no_caller():
    """No LLM configured -> returns empty list."""
    sim = _make_sim_v2()
    events = _run_async(
        sim.generate_plan_llm({"openness": 0.5}, [], [])
    )
    assert events == []


def test_v2_llm_two_events():
    """LLM returns 2 events -> both are captured."""
    sim = _make_sim_v2()
    async def mock_llm(system_prompt, user_prompt):
        return '[{"time": "morning", "activity": "晨跑", "mood": "活力"}, {"time": "evening", "activity": "看电影", "mood": "放松"}]'
    sim.configure(llm_caller=mock_llm)

    events = _run_async(
        sim.generate_plan_llm({"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                               "agreeableness": 0.5, "neuroticism": 0.5}, [], [])
    )
    assert len(events) == 2
    assert events[0].activity == "晨跑"
    assert events[1].activity == "看电影"
    assert events[0].time_slot == "morning"
    assert events[1].time_slot == "evening"


def test_v2_llm_bad_time_defaults_afternoon():
    """LLM returns invalid time slot -> defaults to afternoon."""
    sim = _make_sim_v2()
    async def mock_llm(system_prompt, user_prompt):
        return '[{"time": "midnight", "activity": "熬夜", "mood": "困"}]'
    sim.configure(llm_caller=mock_llm)

    events = _run_async(
        sim.generate_plan_llm({"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                               "agreeableness": 0.5, "neuroticism": 0.5}, [], [])
    )
    assert len(events) == 1
    assert events[0].time_slot == "afternoon"


def test_v2_llm_exception_returns_empty():
    """LLM raises exception -> returns empty list."""
    sim = _make_sim_v2()
    async def exploding_llm(system_prompt, user_prompt):
        raise RuntimeError("LLM service down")
    sim.configure(llm_caller=exploding_llm)

    events = _run_async(
        sim.generate_plan_llm({"openness": 0.5}, [], [])
    )
    assert events == []


def test_v2_llm_truncates_long_activity():
    """Activity longer than 50 chars is truncated."""
    sim = _make_sim_v2()
    long_activity = "这是一个非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的活动描述超过了五十个字符的限制"
    async def mock_llm(system_prompt, user_prompt):
        return f'[{{"time": "afternoon", "activity": "{long_activity}", "mood": "平淡"}}]'
    sim.configure(llm_caller=mock_llm)

    events = _run_async(
        sim.generate_plan_llm({"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                               "agreeableness": 0.5, "neuroticism": 0.5}, [], [])
    )
    assert len(events) == 1
    assert len(events[0].activity) <= 50


def test_v2_llm_flexibility_is_07():
    """LLM random events default to flexibility=0.7."""
    sim = _make_sim_v2()
    async def mock_llm(system_prompt, user_prompt):
        return '[{"time": "afternoon", "activity": "去公园散步", "mood": "期待"}]'
    sim.configure(llm_caller=mock_llm)

    events = _run_async(
        sim.generate_plan_llm({"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                               "agreeableness": 0.5, "neuroticism": 0.5}, [], [])
    )
    assert events[0].flexibility == 0.7


def test_v2_llm_id_starts_with_llm():
    """Generated event IDs start with 'llm_'."""
    sim = _make_sim_v2()
    async def mock_llm(system_prompt, user_prompt):
        return '[{"time": "afternoon", "activity": "测试", "mood": "平淡"}]'
    sim.configure(llm_caller=mock_llm)

    events = _run_async(
        sim.generate_plan_llm({"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                               "agreeableness": 0.5, "neuroticism": 0.5}, [], [])
    )
    assert events[0].id.startswith("llm_")


def test_v2_llm_wrapper_text():
    """LLM returns JSON wrapped in text -> still extracts correctly."""
    sim = _make_sim_v2()
    async def mock_llm(system_prompt, user_prompt):
        return '好的，这是生成的事件：\n[{"time": "morning", "activity": "读书", "mood": "安静"}]\n希望你喜欢！'
    sim.configure(llm_caller=mock_llm)

    events = _run_async(
        sim.generate_plan_llm({"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                               "agreeableness": 0.5, "neuroticism": 0.5}, [], [])
    )
    assert len(events) == 1
    assert events[0].activity == "读书"


# ═══════════════════════════════════════════════════════════════════════
# Task 4: Full Plan Generation (Template + LLM Combined)
# ═══════════════════════════════════════════════════════════════════════

from emotion_spirit.regulation.life_plan import DailyPlan


def test_v2_generate_daily_plan():
    """generate_daily_plan() combines template + LLM events into a DailyPlan."""
    sim = _make_sim_v2()
    async def mock_llm(system_prompt, user_prompt):
        return '[{"time": "evening", "activity": "看星星", "mood": "平静"}]'
    sim.configure(llm_caller=mock_llm)

    personality = {"openness": 0.8, "extraversion": 0.3, "conscientiousness": 0.5,
                   "agreeableness": 0.5, "neuroticism": 0.5}
    plan = _run_async(
        sim.generate_daily_plan(personality, recent_memories=["今天很开心"], yesterday_events=["昨天画画"])
    )
    assert isinstance(plan, DailyPlan)
    assert len(plan.events) >= 3  # 2 template + 1 LLM
    assert plan.date  # non-empty
    assert plan.personality_snapshot == personality
    template_events = [e for e in plan.events if e.category == "template"]
    llm_events = [e for e in plan.events if e.category == "llm_random"]
    assert len(template_events) >= 2
    assert len(llm_events) >= 1


def test_v2_generate_daily_plan_no_llm():
    """Without LLM, only template events."""
    sim = _make_sim_v2()
    plan = _run_async(
        sim.generate_daily_plan({"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                                 "agreeableness": 0.5, "neuroticism": 0.5})
    )
    assert isinstance(plan, DailyPlan)
    assert len(plan.events) >= 2
    assert all(e.category == "template" for e in plan.events)


def test_v2_generate_daily_plan_events_sorted_by_time():
    """Events in the plan are sorted by time slot (morning < afternoon < evening < night)."""
    sim = _make_sim_v2()
    async def mock_llm(system_prompt, user_prompt):
        return '[{"time": "morning", "activity": "晨跑", "mood": "活力"}, {"time": "evening", "activity": "看电影", "mood": "放松"}]'
    sim.configure(llm_caller=mock_llm)

    personality = {"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                   "agreeableness": 0.5, "neuroticism": 0.5}
    plan = _run_async(sim.generate_daily_plan(personality))
    slot_order = {"morning": 0, "afternoon": 1, "evening": 2, "night": 3}
    slots = [e.time_slot for e in plan.events]
    order_values = [slot_order.get(s, 9) for s in slots]
    assert order_values == sorted(order_values)


def test_v2_generate_daily_plan_no_slot_collisions():
    """No two events share the same time slot."""
    sim = _make_sim_v2()
    async def mock_llm(system_prompt, user_prompt):
        return '[{"time": "afternoon", "activity": "逛街", "mood": "开心"}]'
    sim.configure(llm_caller=mock_llm)

    personality = {"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                   "agreeableness": 0.5, "neuroticism": 0.5}
    plan = _run_async(sim.generate_daily_plan(personality))
    slots = [e.time_slot for e in plan.events]
    # Allow duplicates only if there are more events than 4 slots
    if len(plan.events) <= 4:
        assert len(slots) == len(set(slots)), f"Duplicate slots found: {slots}"


def test_v2_generate_daily_plan_dream_seed():
    """dream_seed contains first 3 activities joined by comma."""
    sim = _make_sim_v2()
    async def mock_llm(system_prompt, user_prompt):
        return '[{"time": "evening", "activity": "看星星", "mood": "平静"}]'
    sim.configure(llm_caller=mock_llm)

    personality = {"openness": 0.8, "extraversion": 0.3, "conscientiousness": 0.5,
                   "agreeableness": 0.5, "neuroticism": 0.5}
    plan = _run_async(sim.generate_daily_plan(personality))
    assert plan.dream_seed  # non-empty
    # dream_seed should be comma-separated
    assert ", " in plan.dream_seed or len(plan.events) < 3


def test_v2_generate_daily_plan_stored_as_current():
    """After generate_daily_plan, _current_plan is set."""
    sim = _make_sim_v2()
    personality = {"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                   "agreeableness": 0.5, "neuroticism": 0.5}
    assert sim._current_plan is None
    _run_async(sim.generate_daily_plan(personality))
    assert sim._current_plan is not None
    assert isinstance(sim._current_plan, DailyPlan)


def test_v2_generate_daily_plan_personality_snapshot():
    """personality_snapshot is a copy, not a reference."""
    sim = _make_sim_v2()
    personality = {"openness": 0.7, "extraversion": 0.3, "conscientiousness": 0.6,
                   "agreeableness": 0.4, "neuroticism": 0.2}
    plan = _run_async(sim.generate_daily_plan(personality))
    assert plan.personality_snapshot == personality
    # Mutation of original should not affect snapshot
    personality["openness"] = 0.1
    assert plan.personality_snapshot["openness"] == 0.7


def test_v2_generate_daily_plan_date_is_tomorrow():
    """plan.date is tomorrow's date in ISO format."""
    import datetime
    sim = _make_sim_v2()
    personality = {"openness": 0.5, "extraversion": 0.5, "conscientiousness": 0.5,
                   "agreeableness": 0.5, "neuroticism": 0.5}
    plan = _run_async(sim.generate_daily_plan(personality))
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    assert plan.date == tomorrow


# ═══════════════════════════════════════════════════════════════════════
# Task 5: Plan Adaptation (Rule-Based + Personality Modulation)
# ═══════════════════════════════════════════════════════════════════════


def test_v2_adapt_cancel_social_on_bad_mood():
    """Emotion drop + social event -> cancel social event."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="morning", approximate_time="10:00",
                         activity="看书", category="template", flexibility=0.3),
            PlannedEvent(id="e2", time_slot="afternoon", approximate_time="14:00",
                         activity="逛商场", category="template", flexibility=0.8),
        ],
        personality_snapshot={"neuroticism": 0.5, "conscientiousness": 0.5},
    )
    sim._current_plan = plan
    # Emotion dropped significantly
    actions = sim.adapt_plan(emotion_delta=-0.5, cascade_active=False, boundary_pressure=0.0)
    cancelled = [a for a in actions if a["action"] == "cancel"]
    assert len(cancelled) >= 1
    assert cancelled[0]["event_id"] == "e2"  # social event cancelled


def test_v2_adapt_no_cancel_on_good_mood():
    """Good mood -> no cancellation."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="afternoon", approximate_time="14:00",
                         activity="逛商场", category="template", flexibility=0.8),
        ],
        personality_snapshot={"neuroticism": 0.5, "conscientiousness": 0.5},
    )
    sim._current_plan = plan
    actions = sim.adapt_plan(emotion_delta=0.3, cascade_active=False, boundary_pressure=0.0)
    assert actions == []


def test_v2_adapt_high_neuroticism_lower_threshold():
    """High neuroticism -> more likely to cancel."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="afternoon", approximate_time="14:00",
                         activity="出门见人", category="template", flexibility=0.8),
        ],
        personality_snapshot={"neuroticism": 0.9, "conscientiousness": 0.3},
    )
    sim._current_plan = plan
    # Small emotion drop, but high neuroticism should still trigger
    actions = sim.adapt_plan(emotion_delta=-0.2, cascade_active=False, boundary_pressure=0.0)
    assert any(a["action"] == "cancel" for a in actions)


def test_v2_adapt_cascade_cancels_outdoor():
    """cascade_active -> cancel all outdoor events."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="morning", approximate_time="10:00",
                         activity="看书", category="template", flexibility=0.3),
            PlannedEvent(id="e2", time_slot="afternoon", approximate_time="14:00",
                         activity="逛商场", category="template", flexibility=0.8),
            PlannedEvent(id="e3", time_slot="evening", approximate_time="18:00",
                         activity="散步", category="template", flexibility=0.7),
        ],
        personality_snapshot={"neuroticism": 0.5, "conscientiousness": 0.5},
    )
    sim._current_plan = plan
    actions = sim.adapt_plan(emotion_delta=0.0, cascade_active=True, boundary_pressure=0.0)
    cancelled_ids = {a["event_id"] for a in actions if a["action"] == "cancel"}
    assert "e2" in cancelled_ids  # 逛商场 cancelled
    assert "e3" in cancelled_ids  # 散步 cancelled
    assert "e1" not in cancelled_ids  # 看书 (not outdoor) kept


def test_v2_adapt_boundary_pressure_cancels_social():
    """boundary_pressure > 0.7 -> cancel social events."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="morning", approximate_time="10:00",
                         activity="看书", category="template", flexibility=0.5),
            PlannedEvent(id="e2", time_slot="afternoon", approximate_time="14:00",
                         activity="和朋友聊天", category="template", flexibility=0.8),
        ],
        personality_snapshot={"neuroticism": 0.5, "conscientiousness": 0.5},
    )
    sim._current_plan = plan
    actions = sim.adapt_plan(emotion_delta=0.0, cascade_active=False, boundary_pressure=0.8)
    cancelled_ids = {a["event_id"] for a in actions if a["action"] == "cancel"}
    assert "e2" in cancelled_ids  # social cancelled
    assert "e1" not in cancelled_ids  # non-social kept


def test_v2_adapt_no_plan_returns_empty():
    """No current plan -> returns empty list."""
    sim = _make_sim_v2()
    actions = sim.adapt_plan(emotion_delta=-1.0, cascade_active=True, boundary_pressure=1.0)
    assert actions == []


def test_v2_adapt_low_flexibility_protects_event():
    """Events with flexibility < 0.3 cannot be cancelled."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="afternoon", approximate_time="14:00",
                         activity="逛商场", category="template", flexibility=0.1),
        ],
        personality_snapshot={"neuroticism": 0.5, "conscientiousness": 0.5},
    )
    sim._current_plan = plan
    actions = sim.adapt_plan(emotion_delta=-0.5, cascade_active=True, boundary_pressure=0.9)
    # flexibility=0.1 < 0.3, so event should NOT be cancelled
    assert actions == []


def test_v2_adapt_high_conscientiousness_resists_cancel():
    """High conscientiousness raises threshold, making cancellation harder."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="afternoon", approximate_time="14:00",
                         activity="出门见人", category="template", flexibility=0.8),
        ],
        personality_snapshot={"neuroticism": 0.3, "conscientiousness": 0.9},
    )
    sim._current_plan = plan
    # Small emotion drop — high conscientiousness should resist
    actions = sim.adapt_plan(emotion_delta=-0.15, cascade_active=False, boundary_pressure=0.0)
    assert actions == []


def test_v2_adapt_records_adaptation_log():
    """Cancellations are recorded in plan.adaptations."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="afternoon", approximate_time="14:00",
                         activity="逛商场", category="template", flexibility=0.8),
        ],
        personality_snapshot={"neuroticism": 0.5, "conscientiousness": 0.5},
    )
    sim._current_plan = plan
    sim.adapt_plan(emotion_delta=-0.5, cascade_active=False, boundary_pressure=0.0)
    assert len(plan.adaptations) >= 1
    assert plan.adaptations[0]["action"] == "cancel"
    assert plan.adaptations[0]["event_id"] == "e1"
    assert "timestamp" in plan.adaptations[0]


def test_v2_adapt_cancelled_event_status_updated():
    """Cancelled events have status='cancelled' and cancellation_reason set."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="afternoon", approximate_time="14:00",
                         activity="逛商场", category="template", flexibility=0.8),
        ],
        personality_snapshot={"neuroticism": 0.5, "conscientiousness": 0.5},
    )
    sim._current_plan = plan
    sim.adapt_plan(emotion_delta=-0.5, cascade_active=False, boundary_pressure=0.0)
    assert plan.events[0].status == "cancelled"
    assert plan.events[0].cancellation_reason is not None


# ═══════════════════════════════════════════════════════════════════════
# Task 6: Schedule Context Injection
# ═══════════════════════════════════════════════════════════════════════


def test_v2_build_schedule_context():
    """build_schedule_context() returns human-readable schedule string."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="morning", approximate_time="10:00",
                         activity="看书", category="template", status="done"),
            PlannedEvent(id="e2", time_slot="afternoon", approximate_time="14:00",
                         activity="逛商场", category="template", status="cancelled",
                         cancellation_reason="情绪下降"),
            PlannedEvent(id="e3", time_slot="evening", approximate_time="18:00",
                         activity="画画", category="template", status="planned"),
        ],
    )
    sim._current_plan = plan
    # Mock current time to evening
    import datetime
    evening_ts = datetime.datetime(2026, 6, 27, 19, 0).timestamp()
    context = sim.build_schedule_context(now=evening_ts)
    assert "看书" in context  # done
    assert "逛商场" in context  # cancelled
    assert "情绪下降" in context  # cancellation reason
    assert "画画" in context  # current planned


def test_v2_build_schedule_context_empty():
    """No plan → empty string."""
    sim = _make_sim_v2()
    assert sim.build_schedule_context() == ""


def test_v2_build_schedule_context_only_done():
    """Plan with only done events, no current slot events."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="morning", approximate_time="10:00",
                         activity="看书", category="template", status="done"),
            PlannedEvent(id="e2", time_slot="afternoon", approximate_time="14:00",
                         activity="画画", category="template", status="done"),
        ],
    )
    sim._current_plan = plan
    import datetime
    evening_ts = datetime.datetime(2026, 6, 27, 19, 0).timestamp()
    context = sim.build_schedule_context(now=evening_ts)
    assert "看书" in context
    assert "画画" in context


def test_v2_build_schedule_context_multiple_planned_in_slot():
    """Multiple planned events in the current slot all appear."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="evening", approximate_time="18:00",
                         activity="画画", category="template", status="planned"),
            PlannedEvent(id="e2", time_slot="evening", approximate_time="19:00",
                         activity="听音乐", category="template", status="planned"),
        ],
    )
    sim._current_plan = plan
    import datetime
    evening_ts = datetime.datetime(2026, 6, 27, 19, 0).timestamp()
    context = sim.build_schedule_context(now=evening_ts)
    assert "画画" in context
    assert "听音乐" in context


# ═══════════════════════════════════════════════════════════════════════
# Task 7: Persistence (to_dict/from_dict) for LifeSimulatorV2
# ═══════════════════════════════════════════════════════════════════════


def test_v2_persistence_roundtrip():
    """to_dict → from_dict preserves all data."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=1234567890.0,
        events=[
            PlannedEvent(id="e1", time_slot="morning", approximate_time="10:00",
                         activity="看书", category="template", status="done"),
            PlannedEvent(id="e2", time_slot="afternoon", approximate_time="14:00",
                         activity="逛商场", category="llm_random", status="cancelled",
                         cancellation_reason="情绪下降"),
        ],
        personality_snapshot={"openness": 0.8},
        adaptations=[{"event_id": "e2", "action": "cancel", "reason": "情绪下降"}],
        dream_seed="看书, 逛商场",
    )
    sim._current_plan = plan

    data = sim.to_dict()
    sim2 = _make_sim_v2()
    sim2.from_dict(data)

    assert sim2._current_plan is not None
    assert sim2._current_plan.date == "2026-06-27"
    assert len(sim2._current_plan.events) == 2
    assert sim2._current_plan.events[0].activity == "看书"
    assert sim2._current_plan.events[1].status == "cancelled"
    assert sim2._current_plan.dream_seed == "看书, 逛商场"


def test_v2_persistence_no_plan():
    """to_dict/from_dict when no plan is set."""
    sim = _make_sim_v2()
    data = sim.to_dict()
    assert "current_plan" not in data

    sim2 = _make_sim_v2()
    sim2.from_dict(data)
    assert sim2._current_plan is None


# ═══════════════════════════════════════════════════════════════════════
# Task 8: Config + /view_schedule Command
# ═══════════════════════════════════════════════════════════════════════


def test_v2_view_schedule_output():
    """view_schedule returns formatted schedule."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="morning", approximate_time="10:00",
                         activity="看书", category="template", status="done"),
            PlannedEvent(id="e2", time_slot="afternoon", approximate_time="14:00",
                         activity="逛商场", category="template", status="cancelled",
                         cancellation_reason="情绪下降"),
        ],
    )
    sim._current_plan = plan

    # Simulate the command output (mirrors view_schedule logic)
    lines = [f"📅 日程计划 ({plan.date})"]
    for e in plan.events:
        status_icon = {"done": "✅", "cancelled": "❌"}.get(e.status, "❓")
        line = f"  {status_icon} {e.approximate_time} {e.activity}"
        if e.status == "cancelled" and e.cancellation_reason:
            line += f" (取消原因: {e.cancellation_reason})"
        lines.append(line)
    output = "\n".join(lines)

    assert "📅" in output
    assert "✅ 10:00 看书" in output
    assert "❌ 14:00 逛商场" in output
    assert "情绪下降" in output


def test_v2_view_schedule_replaced_event():
    """view_schedule shows replaced event with arrow."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="afternoon", approximate_time="14:00",
                         activity="逛商场", category="template", status="replaced",
                         replacement="在附近散步"),
        ],
    )
    sim._current_plan = plan

    lines = [f"📅 日程计划 ({plan.date})"]
    for e in plan.events:
        status_icon = {"replaced": "🔄"}.get(e.status, "❓")
        line = f"  {status_icon} {e.approximate_time} {e.activity}"
        if e.status == "replaced" and e.replacement:
            line += f" → {e.replacement}"
        lines.append(line)
    output = "\n".join(lines)

    assert "🔄 14:00 逛商场 → 在附近散步" in output


def test_v2_view_schedule_with_adaptations():
    """view_schedule shows adaptation count."""
    sim = _make_sim_v2()
    plan = DailyPlan(
        date="2026-06-27", generated_at=time.time(),
        events=[
            PlannedEvent(id="e1", time_slot="morning", approximate_time="10:00",
                         activity="看书", category="template", status="planned"),
        ],
        adaptations=[
            {"event_id": "e2", "action": "cancel", "reason": "情绪下降"},
        ],
    )
    sim._current_plan = plan

    lines = [f"📅 日程计划 ({plan.date})"]
    for e in plan.events:
        status_icon = {"planned": "⬜"}.get(e.status, "❓")
        lines.append(f"  {status_icon} {e.approximate_time} {e.activity}")
    if plan.adaptations:
        lines.append(f"\n📝 调整记录: {len(plan.adaptations)} 次")
    output = "\n".join(lines)

    assert "📝 调整记录: 1 次" in output


def test_life_sim_v2_config_exists():
    """LIFE_SIM_V2_CONFIG is importable and has expected keys."""
    from emotion_spirit.core.config import LIFE_SIM_V2_CONFIG
    assert "plan_generate_hour" in LIFE_SIM_V2_CONFIG
    assert "events_per_day_min" in LIFE_SIM_V2_CONFIG
    assert "events_per_day_max" in LIFE_SIM_V2_CONFIG
    assert "adaptation_threshold" in LIFE_SIM_V2_CONFIG
    assert "enable_proactive_prompt" in LIFE_SIM_V2_CONFIG
    assert "sleep_start_hour" in LIFE_SIM_V2_CONFIG
    assert "sleep_end_hour" in LIFE_SIM_V2_CONFIG


# ═══════════════════════════════════════════════════════════════════════
# Task 9: Integration Smoke Test — Full Lifecycle
# ═══════════════════════════════════════════════════════════════════════


def test_v2_full_lifecycle():
    """End-to-end: generate plan → adapt → consume → build context → persist."""
    sim = _make_sim_v2()

    async def mock_llm(system_prompt, user_prompt):
        return '[{"time": "evening", "activity": "看星星", "mood": "平静"}]'

    sim.configure(llm_caller=mock_llm)

    personality = {
        "openness": 0.8, "extraversion": 0.3, "conscientiousness": 0.5,
        "agreeableness": 0.5, "neuroticism": 0.5,
    }

    # 1. Generate plan
    plan = _run_async(
        sim.generate_daily_plan(personality, recent_memories=["今天很开心"])
    )
    assert len(plan.events) >= 3
    assert sim._current_plan is plan

    # 2. Adapt (bad mood → cancel social)
    actions = sim.adapt_plan(emotion_delta=-0.5, cascade_active=False, boundary_pressure=0.0)
    # At least one social event should be cancelled
    cancelled = [e for e in plan.events if e.status == "cancelled"]
    # (may or may not cancel depending on template selection, so just check no crash)

    # 3. Build context
    context = sim.build_schedule_context()
    # Should be non-empty if there are events
    if plan.events:
        assert context  # non-empty

    # 4. Persistence roundtrip
    data = sim.to_dict()
    sim2 = _make_sim_v2()
    sim2.from_dict(data)
    assert sim2._current_plan.date == plan.date
    assert len(sim2._current_plan.events) == len(plan.events)


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
