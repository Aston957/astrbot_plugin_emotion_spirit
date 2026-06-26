"""Tests for dream_generator.py"""

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

from emotion_spirit.memory.memory_pool import MemoryPool
from emotion_spirit.memory.memory_sampler import MemorySampler
from emotion_spirit.regulation.dream_generator import DreamGenerator


DEFAULT_PERSONALITY = {
    "openness": 0.5,
    "extraversion": 0.5,
    "agreeableness": 0.5,
    "neuroticism": 0.5,
    "conscientiousness": 0.5,
    "emotional_stability": 0.5,
}


def _make_dream_gen():
    """Helper: create DreamGenerator with MemoryPool + MemorySampler."""
    pool = MemoryPool()
    sampler = MemorySampler(pool)
    dg = DreamGenerator(pool, sampler)
    return dg, pool, sampler


def _add_memories(pool: MemoryPool, n: int = 5):
    """Helper: add n memories to the buffer pool."""
    for i in range(n):
        pool.add(
            text=f"memory_{i}: some event happened",
            raw_weight=0.5 + i * 0.05,
            phi=0.5,
            tags=[f"tag_{i}"],
            source_user="user1",
        )


# ═══════════════════════════════════════════════════════════════════
# compute_dream_rounds
# ═══════════════════════════════════════════════════════════════════


def test_compute_dream_rounds_basic():
    """Basic: 6 hours / 3 = 2 rounds."""
    dg, _, _ = _make_dream_gen()
    rounds = dg.compute_dream_rounds(6.0, DEFAULT_PERSONALITY)
    assert rounds == 2


def test_compute_dream_rounds_short_sleep():
    """Short sleep (2h) yields minimum 1 round."""
    dg, _, _ = _make_dream_gen()
    rounds = dg.compute_dream_rounds(2.0, DEFAULT_PERSONALITY)
    assert rounds == 1


def test_compute_dream_rounds_long_sleep():
    """Long sleep (12h) yields 4 rounds (clamped at 5)."""
    dg, _, _ = _make_dream_gen()
    rounds = dg.compute_dream_rounds(12.0, DEFAULT_PERSONALITY)
    assert rounds == 4


def test_compute_dream_rounds_openness_bonus():
    """High openness adds +1 round."""
    dg, _, _ = _make_dream_gen()
    p = {**DEFAULT_PERSONALITY, "openness": 0.9}
    rounds = dg.compute_dream_rounds(6.0, p)
    assert rounds == 3  # base 2 + 1


def test_compute_dream_rounds_conscientiousness_penalty():
    """High conscientiousness subtracts -1 round."""
    dg, _, _ = _make_dream_gen()
    p = {**DEFAULT_PERSONALITY, "conscientiousness": 0.9}
    rounds = dg.compute_dream_rounds(6.0, p)
    assert rounds == 1  # base 2 - 1


def test_compute_dream_rounds_clamped_max():
    """Rounds clamped at 5."""
    dg, _, _ = _make_dream_gen()
    p = {**DEFAULT_PERSONALITY, "openness": 0.9}
    rounds = dg.compute_dream_rounds(20.0, p)  # base 6 + 1 = 7, clamped to 5
    assert rounds == 5


def test_compute_dream_rounds_clamped_min():
    """Rounds clamped at minimum 1."""
    dg, _, _ = _make_dream_gen()
    p = {**DEFAULT_PERSONALITY, "conscientiousness": 0.9, "openness": 0.1}
    rounds = dg.compute_dream_rounds(1.0, p)  # base 0 -> 1, -1 -> 0, clamped to 1
    assert rounds == 1


# ═══════════════════════════════════════════════════════════════════
# _personality_tone
# ═══════════════════════════════════════════════════════════════════


def test_personality_tone_neutral():
    """Neutral personality yields '平静'."""
    dg, _, _ = _make_dream_gen()
    tone = dg._personality_tone(DEFAULT_PERSONALITY)
    assert tone == "平静"


def test_personality_tone_neuroticism():
    """High neuroticism yields '焦虑'."""
    dg, _, _ = _make_dream_gen()
    p = {**DEFAULT_PERSONALITY, "neuroticism": 0.9}
    tone = dg._personality_tone(p)
    assert "焦虑" in tone


def test_personality_tone_multiple():
    """Multiple high dimensions yield multiple tones."""
    dg, _, _ = _make_dream_gen()
    p = {**DEFAULT_PERSONALITY, "neuroticism": 0.9, "openness": 0.9, "agreeableness": 0.9}
    tone = dg._personality_tone(p)
    assert "焦虑" in tone
    assert "奇幻" in tone
    assert "温暖" in tone


def test_personality_tone_all_high():
    """All dimensions high yields all tones."""
    dg, _, _ = _make_dream_gen()
    p = {k: 0.9 for k in DEFAULT_PERSONALITY}
    tone = dg._personality_tone(p)
    assert "焦虑" in tone
    assert "奇幻" in tone
    assert "规律" in tone
    assert "社交场景" in tone
    assert "温暖" in tone


# ═══════════════════════════════════════════════════════════════════
# compute_sleep_deprivation_chance
# ═══════════════════════════════════════════════════════════════════


def test_sleep_deprivation_chance_base():
    """Base probability is 0.1."""
    dg, _, _ = _make_dream_gen()
    p = dg.compute_sleep_deprivation_chance(DEFAULT_PERSONALITY)
    assert abs(p - 0.1) < 1e-6


def test_sleep_deprivation_chance_high_temperature():
    """High temperature doubles probability."""
    dg, _, _ = _make_dream_gen()
    p = dg.compute_sleep_deprivation_chance(DEFAULT_PERSONALITY, temperature=0.8)
    assert abs(p - 0.2) < 1e-6


def test_sleep_deprivation_chance_cascade():
    """Cascade active multiplies by 1.5."""
    dg, _, _ = _make_dream_gen()
    p = dg.compute_sleep_deprivation_chance(DEFAULT_PERSONALITY, cascade_active=True)
    assert abs(p - 0.15) < 1e-6


def test_sleep_deprivation_chance_neuroticism():
    """High neuroticism multiplies by 1.5."""
    dg, _, _ = _make_dream_gen()
    personality = {**DEFAULT_PERSONALITY, "neuroticism": 0.9}
    p = dg.compute_sleep_deprivation_chance(personality)
    assert abs(p - 0.15) < 1e-6


def test_sleep_deprivation_chance_conscientiousness():
    """High conscientiousness multiplies by 0.8."""
    dg, _, _ = _make_dream_gen()
    personality = {**DEFAULT_PERSONALITY, "conscientiousness": 0.9}
    p = dg.compute_sleep_deprivation_chance(personality)
    assert abs(p - 0.08) < 1e-6


def test_sleep_deprivation_chance_combined():
    """All factors combined, capped at 1.0."""
    dg, _, _ = _make_dream_gen()
    personality = {**DEFAULT_PERSONALITY, "neuroticism": 0.9}
    p = dg.compute_sleep_deprivation_chance(
        personality, temperature=0.8, cascade_active=True,
    )
    # 0.1 * 2.0 * 1.5 * 1.5 = 0.45
    assert abs(p - 0.45) < 1e-6


def test_sleep_deprivation_chance_capped():
    """Probability capped at 1.0 even with extreme multipliers."""
    dg, _, _ = _make_dream_gen()
    # High neuroticism (x1.5), high temp (x2.0), cascade (x1.5),
    # low conscientiousness (no 0.8 penalty): 0.1 * 2 * 1.5 * 1.5 = 0.45
    # To exceed 1.0 we'd need even more multipliers; with current formula
    # max is 0.1 * 2.0 * 1.5 * 1.5 = 0.45 (no conscientiousness penalty).
    # Verify it stays within [0, 1] and that min(1.0, p) works.
    personality = {**DEFAULT_PERSONALITY, "neuroticism": 0.99, "conscientiousness": 0.1}
    p = dg.compute_sleep_deprivation_chance(
        personality, temperature=0.99, cascade_active=True,
    )
    assert 0.0 <= p <= 1.0
    # With all non-conscientiousness multipliers: 0.1 * 2.0 * 1.5 * 1.5 = 0.45
    assert abs(p - 0.45) < 1e-6


# ═══════════════════════════════════════════════════════════════════
# generate_deep_sleep_dream
# ═══════════════════════════════════════════════════════════════════


def test_deep_sleep_dream_no_llm():
    """Returns None when no LLM configured."""
    dg, pool, _ = _make_dream_gen()
    _add_memories(pool)
    result = asyncio.run(dg.generate_deep_sleep_dream(DEFAULT_PERSONALITY))
    assert result is None


def test_deep_sleep_dream_with_llm():
    """Calls LLM when configured."""
    dg, pool, _ = _make_dream_gen()
    _add_memories(pool)

    async def fake_llm(system: str, prompt: str) -> str:
        return "在梦中，我看到了一座金色的城堡..."

    dg.configure(fake_llm)
    result = asyncio.run(dg.generate_deep_sleep_dream(DEFAULT_PERSONALITY))
    assert result is not None
    assert "金色" in result


def test_deep_sleep_dream_with_events():
    """LLM receives recent events in prompt."""
    dg, pool, _ = _make_dream_gen()
    _add_memories(pool)
    captured_prompts: list[str] = []

    async def fake_llm(system: str, prompt: str) -> str:
        captured_prompts.append(prompt)
        return "梦境内容"

    dg.configure(fake_llm)
    events = ["今天去了公园", "吃了一顿美味的晚餐"]
    asyncio.run(dg.generate_deep_sleep_dream(DEFAULT_PERSONALITY, recent_events=events))
    assert len(captured_prompts) == 1
    assert "公园" in captured_prompts[0]
    assert "晚餐" in captured_prompts[0]


def test_deep_sleep_dream_no_memories():
    """Works even with empty memory pool."""
    dg, pool, _ = _make_dream_gen()

    async def fake_llm(system: str, prompt: str) -> str:
        return "空白的梦"

    dg.configure(fake_llm)
    result = asyncio.run(dg.generate_deep_sleep_dream(DEFAULT_PERSONALITY))
    assert result == "空白的梦"


def test_deep_sleep_dream_llm_exception():
    """Returns None when LLM raises exception."""
    dg, pool, _ = _make_dream_gen()
    _add_memories(pool)

    async def bad_llm(system: str, prompt: str) -> str:
        raise RuntimeError("LLM failure")

    dg.configure(bad_llm)
    result = asyncio.run(dg.generate_deep_sleep_dream(DEFAULT_PERSONALITY))
    assert result is None


def test_deep_sleep_dream_personality_tone():
    """High openness produces '奇幻' in prompt."""
    dg, pool, _ = _make_dream_gen()
    _add_memories(pool)
    captured_prompts: list[str] = []

    async def fake_llm(system: str, prompt: str) -> str:
        captured_prompts.append(prompt)
        return "梦"

    dg.configure(fake_llm)
    p = {**DEFAULT_PERSONALITY, "openness": 0.9}
    asyncio.run(dg.generate_deep_sleep_dream(p))
    assert "奇幻" in captured_prompts[0]


def test_deep_sleep_dream_events_truncated():
    """Only first 3 events are used."""
    dg, pool, _ = _make_dream_gen()
    _add_memories(pool)
    captured_prompts: list[str] = []

    async def fake_llm(system: str, prompt: str) -> str:
        captured_prompts.append(prompt)
        return "梦"

    dg.configure(fake_llm)
    events = [f"event_{i}" for i in range(10)]
    asyncio.run(dg.generate_deep_sleep_dream(DEFAULT_PERSONALITY, recent_events=events))
    # event_0, event_1, event_2 should be present; event_3 should not
    assert "event_0" in captured_prompts[0]
    assert "event_2" in captured_prompts[0]
    assert "event_3" not in captured_prompts[0]


# ═══════════════════════════════════════════════════════════════════
# generate_sleep_deprivation_dream
# ═══════════════════════════════════════════════════════════════════


def test_sleep_deprivation_dream_with_memories():
    """Returns template with memory text when memories exist."""
    dg, pool, _ = _make_dream_gen()
    _add_memories(pool)
    result = dg.generate_sleep_deprivation_dream(DEFAULT_PERSONALITY)
    assert result.startswith("碎片梦境:")
    assert len(result) > 10


def test_sleep_deprivation_dream_no_memories():
    """Returns fallback template when no memories."""
    dg, _, _ = _make_dream_gen()
    result = dg.generate_sleep_deprivation_dream(DEFAULT_PERSONALITY)
    assert result == "碎片梦境: 无法入睡，脑海中闪过模糊的画面"


def test_sleep_deprivation_dream_text_truncated():
    """Memory text is truncated to 50 chars."""
    dg, pool, _ = _make_dream_gen()
    # Add a memory with long text
    long_text = "x" * 200
    pool.add(long_text, 0.5, 0.5, ["test"], "user1")
    result = dg.generate_sleep_deprivation_dream(DEFAULT_PERSONALITY)
    # The text portion should be at most 50 chars + "..."
    assert "..." in result
    # "碎片梦境: " is 5 chars + 50 chars + "..." = 58 chars
    assert len(result) <= 58 + 5


# ═══════════════════════════════════════════════════════════════════
# persistence (to_dict / from_dict)
# ═══════════════════════════════════════════════════════════════════


def test_to_dict_default():
    """Default to_dict has last_dream_time = 0.0."""
    dg, _, _ = _make_dream_gen()
    data = dg.to_dict()
    assert data == {"last_dream_time": 0.0}


def test_from_dict_restores():
    """from_dict restores last_dream_time."""
    dg, _, _ = _make_dream_gen()
    dg.from_dict({"last_dream_time": 12345.0})
    assert dg._last_dream_time == 12345.0


def test_from_dict_missing_key():
    """from_dict with missing key defaults to 0.0."""
    dg, _, _ = _make_dream_gen()
    dg._last_dream_time = 999.0
    dg.from_dict({})
    assert dg._last_dream_time == 0.0


def test_to_dict_after_dream():
    """to_dict reflects last_dream_time after deep sleep dream."""
    dg, pool, _ = _make_dream_gen()
    _add_memories(pool)

    async def fake_llm(system: str, prompt: str) -> str:
        return "梦"

    dg.configure(fake_llm)
    before = time.time()
    asyncio.run(dg.generate_deep_sleep_dream(DEFAULT_PERSONALITY))
    after = time.time()

    data = dg.to_dict()
    assert before <= data["last_dream_time"] <= after


def test_roundtrip_persistence():
    """to_dict -> from_dict roundtrip preserves state."""
    dg1, _, _ = _make_dream_gen()
    dg1._last_dream_time = 42.0
    data = dg1.to_dict()

    dg2, _, _ = _make_dream_gen()
    dg2.from_dict(data)
    assert dg2._last_dream_time == 42.0


# ═══════════════════════════════════════════════════════════════════
# configure
# ═══════════════════════════════════════════════════════════════════


def test_configure_sets_llm():
    """configure() sets the LLM callable."""
    dg, _, _ = _make_dream_gen()
    assert dg._llm is None

    async def my_llm(s: str, p: str) -> str:
        return "test"

    dg.configure(my_llm)
    assert dg._llm is my_llm


def test_configure_none():
    """configure(None) clears the LLM."""
    dg, _, _ = _make_dream_gen()

    async def my_llm(s: str, p: str) -> str:
        return "test"

    dg.configure(my_llm)
    dg.configure(None)
    assert dg._llm is None
