"""v1.3.0 rc.5 Bug-I: schedule cron 一致性 + 6am 逻辑日边界测试.

验证:
- plan.date = date.today() (不是 today+1)
- _last_plan_date = plan.date (双路径统一, 防 cron/setup_init 不一致)
- cron 跨日重生成 (dedup 不自锁)
- logical_today 6am 边界
- plan_date_label 今天/明天
- catch-up: _life_sim_v2 未就绪时跳过
"""
import asyncio
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


def _run_async(coro):
    """新 event loop 跑 async (避免全量测试时 loop 冲突)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ═══ time_utils 直接测试 (最稳, 无 mock) ═══

def test_logical_today_6am_boundary():
    """6am 前 = 昨天, 6am (含) 后 = 今天."""
    from emotion_spirit.utils.time_utils import logical_today
    assert logical_today(datetime(2026, 7, 5, 3, 0)) == date(2026, 7, 4)   # 03:00 → 昨天
    assert logical_today(datetime(2026, 7, 5, 6, 0)) == date(2026, 7, 5)   # 06:00 → 今天
    assert logical_today(datetime(2026, 7, 5, 14, 0)) == date(2026, 7, 5)  # 14:00 → 今天
    assert logical_today(datetime(2026, 7, 5, 23, 59)) == date(2026, 7, 5)


def test_plan_date_label_today_tomorrow():
    """plan_date_label: 14:00 plan.date=today → 今天; 03:00 plan.date=today → 明天."""
    from emotion_spirit.utils.time_utils import plan_date_label
    # 14:00, plan.date = today (2026-07-05) → 今天日程
    assert plan_date_label("2026-07-05", datetime(2026, 7, 5, 14, 0)) == "今天日程 (2026-07-05)"
    # 03:00 (6am 前), plan.date = 2026-07-05 (02:00 生成) → logical_today=7/4 → 明天日程
    assert plan_date_label("2026-07-05", datetime(2026, 7, 5, 3, 0)) == "明天日程 (2026-07-05)"
    # 次日 01:00 (仍 6am 前, 还在过 day D), plan.date = D → 今天日程
    assert plan_date_label("2026-07-05", datetime(2026, 7, 6, 1, 0)) == "今天日程 (2026-07-05)"


# ═══ plan.date = today (Bug-I 核心) ═══

def test_plan_date_is_today_not_tomorrow():
    """generate_daily_plan 设 plan.date = date.today() (不是 today+1)."""
    from emotion_spirit.output.surface_consumer import SurfaceConsumer
    from emotion_spirit.memory.memory_pool import MemoryPool
    from emotion_spirit.memory.intimacy import IntimacyTracker
    from emotion_spirit.output.buffer_signals import BufferSignals
    from emotion_spirit.memory.meaning_reservoir import MeaningReservoir
    from emotion_spirit.regulation.life_simulator import LifeSimulatorV2
    pool = MemoryPool()
    sim = LifeSimulatorV2(SurfaceConsumer(), pool, IntimacyTracker(),
                          BufferSignals(pool), MeaningReservoir())
    personality = {"warmth_bias": 0.6, "patience": 0.7, "expression_drive": 0.5,
                   "curiosity": 0.5, "inner_coherence": 0.6}
    plan = _run_async(sim.generate_daily_plan(
        personality=personality, recent_memories=[], yesterday_events=[]
    ))
    assert plan.date == date.today().isoformat(), (
        f"plan.date 应为今天 {date.today().isoformat()}, 实际 {plan.date}"
    )
    assert plan.date != (date.today() + timedelta(days=1)).isoformat(), "plan.date 不应是明天"


# ═══ _maybe_generate_plan (用 stub, 不实例化整个 plugin) ═══

class _StubPlugin:
    """最小 stub: 只含 _maybe_generate_plan 用到的属性 + rc.5 抽出的 helper.

    其余 (defense_modulator / dream_generator / pool 等) 在 _maybe_generate_plan 里
    被 try/except 或 hasattr 兜住, stub 不提供也不会崩. rc.5 抽出的两个 helper
    (_apply_suppression_l2_after_plan / _generate_deep_sleep_dream_after_plan) 在
    stub 里作 no-op (本测试聚焦 dedup/统一逻辑, 不测 suppression/dream 副作用).
    """
    def __init__(self, life_sim, last_plan_date):
        self._life_sim_v2 = life_sim
        self._last_plan_date = last_plan_date
    def _get_current_personality_dict(self): return {}
    def _get_recent_memory_texts(self, limit=5): return []
    def _get_yesterday_events(self): return []
    def _save_if_dirty(self): pass
    def _apply_suppression_l2_after_plan(self, personality): pass
    async def _generate_deep_sleep_dream_after_plan(self, personality, plan): pass


def _make_plan_mock(date_str):
    plan = MagicMock()
    plan.date = date_str
    plan.events = []
    plan.dream_seed = ""
    return plan


def test_maybe_generate_plan_unifies_last_plan_date():
    """_last_plan_date = plan.date (与 commands.py setup_init 路径统一, 不是 today_str)."""
    from main import EmotionSpiritPlugin
    life_sim = MagicMock()
    life_sim.generate_daily_plan = AsyncMock(return_value=_make_plan_mock("2026-07-05"))
    stub = _StubPlugin(life_sim, last_plan_date="")
    with patch("main.date") as m:
        m.today.return_value = date(2026, 7, 5)
        _run_async(EmotionSpiritPlugin._maybe_generate_plan(stub))
    assert stub._last_plan_date == "2026-07-05", (
        f"_last_plan_date 应 = plan.date, 实际 {stub._last_plan_date!r}"
    )


def test_maybe_generate_plan_dedup_skips_same_day():
    """_last_plan_date == today → 跳过, 不再生成."""
    from main import EmotionSpiritPlugin
    life_sim = MagicMock()
    life_sim.generate_daily_plan = AsyncMock(return_value=_make_plan_mock("2026-07-05"))
    stub = _StubPlugin(life_sim, last_plan_date="2026-07-05")  # 当天已生成
    with patch("main.date") as m:
        m.today.return_value = date(2026, 7, 5)
        _run_async(EmotionSpiritPlugin._maybe_generate_plan(stub))
    assert life_sim.generate_daily_plan.call_count == 0, "dedup 应跳过当天重复生成"


def test_cron_regenerates_across_day_rollover():
    """Bug-I 核心: 跨日 _last=昨天 != today → 重新生成 (不自锁)."""
    from main import EmotionSpiritPlugin
    life_sim = MagicMock()
    life_sim.generate_daily_plan = AsyncMock(
        side_effect=[_make_plan_mock("2026-07-05"), _make_plan_mock("2026-07-06")]
    )
    stub = _StubPlugin(life_sim, last_plan_date="")
    # Day 1: 7/5
    with patch("main.date") as m:
        m.today.return_value = date(2026, 7, 5)
        _run_async(EmotionSpiritPlugin._maybe_generate_plan(stub))
    assert stub._last_plan_date == "2026-07-05"
    # Day 2: 7/6 (跨日, _last=7/5 != today=7/6 → 重新生成)
    with patch("main.date") as m:
        m.today.return_value = date(2026, 7, 6)
        _run_async(EmotionSpiritPlugin._maybe_generate_plan(stub))
    assert stub._last_plan_date == "2026-07-06", (
        f"跨日应重新生成, _last={stub._last_plan_date!r}"
    )
    assert life_sim.generate_daily_plan.call_count == 2


def test_catch_up_skips_when_life_sim_not_ready():
    """catch-up: _life_sim_v2 未就绪 → 跳过, 不抛错 (防 init race)."""
    from main import EmotionSpiritPlugin
    stub = _StubPlugin(None, last_plan_date="")
    _run_async(EmotionSpiritPlugin._maybe_generate_plan(stub))  # 不应抛异常
