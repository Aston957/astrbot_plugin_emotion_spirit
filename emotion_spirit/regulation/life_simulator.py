"""Life Simulator — v1 deprecated stub (backward compat) + v2 (active).

v3.0: v1 mode A/B + Phase G LLM prose generation were removed in T2 cleanup
because v2 (LifeSimulatorV2) provides template-based daily plan generation
that fully replaces v1 functionality.

This module preserves the v1 LifeSimulator class as a minimal stub for
backward compat: only __init__/configure/on_user_message/to_dict/from_dict
are kept (for module init wiring and persistence round-trip). v1 trigger
methods (check_mode_a/b), LLM prose (generate_life_prose), and event lifecycle
(pending_life_event/consume_life_event) have been removed.

Active implementation: see ``LifeSimulatorV2`` below.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..memory.memory_pool import MemoryPool
    from ..memory.intimacy import IntimacyTracker
    from ..output.buffer_signals import BufferSignals
    from ..memory.meaning_reservoir import MeaningReservoir
    from ..output.surface_consumer import SurfaceConsumer
    from .life_plan import PlannedEvent, DailyPlan

from ..memory.memory_sampler import MemorySampler

from ..core.registry import register


__all__ = [
    "LifeSimulator",
    "LifeSimulatorV2",
    "LifeEvent",
    "LifeEventType",
    "LIFE_EVENT_WEIGHTS",
]


# ═══════════════════════════════════════════════════════════════════════
# LifeEvent 数据结构 (从 Sylanne 1.4.7 引入, Phase G)
# ═══════════════════════════════════════════════════════════════════════
# Kept here because external consumers (bot_decision, tests, plugins)
# still import them. v1 trigger methods that produced LifeEvents were
# removed; the dataclass/types/weights remain as data definitions.


@dataclass
class LifeEvent:
    """一个生活事件。"""

    text: str  # 事件描述
    mood: str  # 当前心情
    urgency: float  # 紧迫度 [0,1]
    timestamp: float  # 发生时间
    wants_to_share: bool = False  # 是否想分享给朋友
    shared: bool = False  # 是否已经分享过
    event_type: str = ""  # 事件类型 (对应 LifeEventType)


class LifeEventType:
    """生活事件类型枚举。"""

    READING = "reading"
    WALKING = "walking"
    COOKING = "cooking"
    THINKING = "thinking"
    CREATING = "creating"
    RESTING = "resting"
    OBSERVING = "observing"


# 事件类型 → 情绪权重 (valence, arousal, share_tendency)
LIFE_EVENT_WEIGHTS: dict[str, dict[str, float]] = {
    "reading": {"valence": 0.2, "arousal": -0.1, "share_tendency": 0.4},
    "walking": {"valence": 0.3, "arousal": 0.1, "share_tendency": 0.3},
    "cooking": {"valence": 0.2, "arousal": 0.2, "share_tendency": 0.5},
    "thinking": {"valence": 0.0, "arousal": -0.2, "share_tendency": 0.6},
    "creating": {"valence": 0.4, "arousal": 0.3, "share_tendency": 0.7},
    "resting": {"valence": 0.1, "arousal": -0.3, "share_tendency": 0.1},
    "observing": {"valence": 0.1, "arousal": 0.0, "share_tendency": 0.5},
}


# ═══════════════════════════════════════════════════════════════════════
# v1 stub — backward compat only (init/wire/persistence)
# ═══════════════════════════════════════════════════════════════════════


@register(
    name="life_simulator",
    provides=["LifeSimulator"],
    depends_on=[
        "surface_consumer", "memory_pool", "intimacy",
        "buffer_signals", "meaning_reservoir",
    ],
    param_wire={
        "memory_pool": "memory",
        "buffer_signals": "signals",
        "surface_consumer": "consumer",
        "meaning_reservoir": "reservoir",
    },
)
class LifeSimulator:
    """v1 stub for backward compat.

    The v1 Mode A/B trigger logic, Phase G LLM prose generation, and event
    lifecycle have been removed (replaced by ``LifeSimulatorV2``). Only the
    following methods are retained so that module init wiring and persistence
    round-trip continue to work:

    - ``__init__`` (module wiring)
    - ``configure`` (LLM caller injection — kept as no-op signature for compat)
    - ``on_user_message`` (no-op: turn tracking, retained for surface_handler)
    - ``to_dict`` / ``from_dict`` (persistence round-trip with empty payload)
    """

    def __init__(
        self,
        consumer: SurfaceConsumer,
        memory: "MemoryPool",
        intimacy: IntimacyTracker,
        signals: BufferSignals,
        reservoir: MeaningReservoir,
    ) -> None:
        self._consumer = consumer
        self._memory = memory
        self._sampler = MemorySampler(memory)
        self._intimacy = intimacy
        self._signals = signals
        self._reservoir = reservoir
        self._last_mode_b: float = 0.0
        self._mode_b_cooldown: float = 0.0
        self._turn_count: int = 0
        self._last_interaction: float = time.time()
        self._llm_caller: Callable[[str, str], Awaitable[str]] | None = None

    def on_user_message(self) -> None:
        """No-op stub. v1 turn tracking removed; v2 handles interaction state."""
        self._turn_count += 1
        self._last_interaction = time.time()

    def configure(
        self,
        llm_caller: Callable[[str, str], Awaitable[str]] | None = None,
    ) -> None:
        """No-op stub for backward compat. v1 LLM prose generation removed."""
        self._llm_caller = llm_caller

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_mode_b": self._last_mode_b,
            "mode_b_cooldown": self._mode_b_cooldown,
            "turn_count": self._turn_count,
            "last_interaction": self._last_interaction,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self._last_mode_b = data.get("last_mode_b", 0.0)
        self._mode_b_cooldown = data.get("mode_b_cooldown", 0.0)
        self._turn_count = data.get("turn_count", 0)
        self._last_interaction = data.get("last_interaction", time.time())


# ═══════════════════════════════════════════════════════════════════════
# LifeSimulatorV2 — template-based plan generation (zero LLM)
# ═══════════════════════════════════════════════════════════════════════


class LifeSimulatorV2:
    """v2: 主动规划日程 + 实时根据对话调整。"""

    def __init__(
        self,
        consumer: "SurfaceConsumer",
        memory: "MemoryPool",
        intimacy: "IntimacyTracker",
        signals: "BufferSignals",
        reservoir: "MeaningReservoir",
    ) -> None:
        self._consumer = consumer
        self._memory = memory
        self._sampler = MemorySampler(memory)
        self._intimacy = intimacy
        self._signals = signals
        self._reservoir = reservoir
        self._current_plan: "DailyPlan | None" = None
        self._llm_caller: Callable[[str, str], Awaitable[str]] | None = None

    def configure(self, llm_caller: Callable[[str, str], Awaitable[str]] | None = None) -> None:
        self._llm_caller = llm_caller

    _POLISH_PROMPT = """你是一个生活模拟器。把以下简短的活动描述润色成具体的、有画面感的一句话。

人格特征: {personality}
时间: {time_desc}

活动列表:
{activities}

要求:
- 每个活动润色成一句具体的生活场景描述（15-30字）
- 要有细节（地点、感受、天气等）
- 符合角色性格
- 输出 JSON 数组: ["润色后的描述1", "润色后的描述2", ...]
- 只输出 JSON，不要其他文字"""

    def generate_plan_template(
        self,
        personality: dict[str, float],
        n: int = 3,
    ) -> list["PlannedEvent"]:
        """按人格权重从模板库选择 n 个活动。"""
        from .life_plan import PlannedEvent as _PlannedEvent, select_template_activities, _time_to_slot
        import time as _time

        activities = select_template_activities(personality, n=n)
        time_slots = ["morning", "afternoon", "evening"]
        slot_times = {"morning": "10:00", "afternoon": "14:00", "evening": "18:00"}

        events = []
        for i, (cat, activity) in enumerate(activities):
            slot = time_slots[i % len(time_slots)]
            flex = {"routine": 0.1, "social": 0.8}.get(cat, 0.5)
            events.append(_PlannedEvent(
                id=f"tpl_{i}_{int(_time.time())}",
                time_slot=slot,
                approximate_time=slot_times.get(slot, "12:00"),
                activity=activity,
                category="template",
                flexibility=flex,
            ))
        return events

    async def polish_template_events(
        self,
        events: list["PlannedEvent"],
        personality: dict[str, float],
    ) -> list["PlannedEvent"]:
        """用 LLM 润色模板事件的 activity 描述。"""
        if not self._llm_caller or not events:
            return events

        # 只润色 template 类型的事件
        template_events = [e for e in events if e.category == "template"]
        if not template_events:
            return events

        # 构建润色 prompt
        import datetime as _dt
        now = _dt.datetime.now()
        time_desc = now.strftime("%H:%M, %A")
        p_desc = ", ".join(f"{k}={v:.1f}" for k, v in personality.items())
        activities_text = "\n".join(
            f"{i+1}. {e.activity} (时间: {e.approximate_time})"
            for i, e in enumerate(template_events)
        )

        prompt = self._POLISH_PROMPT.format(
            personality=p_desc,
            time_desc=time_desc,
            activities=activities_text,
        )

        try:
            response = await self._llm_caller("你是生活模拟器。只输出 JSON。", prompt)
            import json as _json
            text = response.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start < 0 or end <= start:
                return events
            polished = _json.loads(text[start:end])
            if not isinstance(polished, list):
                return events

            # 替换 activity 描述
            for i, e in enumerate(template_events):
                if i < len(polished) and isinstance(polished[i], str) and polished[i]:
                    e.activity = polished[i][:80]  # 截断防过长
        except Exception:
            pass  # 润色失败则保留原模板

        return events

    # ── Full plan generation (Task 4) ─────────────────────────────────

    async def generate_daily_plan(
        self,
        personality: dict[str, float],
        recent_memories: list[str] | None = None,
        yesterday_events: list[str] | None = None,
    ) -> "DailyPlan":
        """生成明天的日程计划 (模板 + LLM 组合)。"""
        from .life_plan import DailyPlan
        import datetime as _dt

        recent_memories = recent_memories or []
        yesterday_events = yesterday_events or []

        # 模板事件 (3 个基础 + LLM 润色)
        template_events = self.generate_plan_template(personality, n=3)
        template_events = await self.polish_template_events(template_events, personality)

        # LLM 随机事件 (1-2 个)
        llm_events = await self.generate_plan_llm(personality, recent_memories, yesterday_events)

        # LLM 失败时补充 1 个模板事件
        if not llm_events:
            extra = self.generate_plan_template(personality, n=1)
            # 排除已有的 activity
            existing = {e.activity for e in template_events}
            for e in extra:
                if e.activity not in existing:
                    llm_events.append(e)
                    break

        # 组合
        all_events = template_events + llm_events

        # 分配到时间段 (确保不重复 approximate_time)
        slot_pool = ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "17:00", "18:00", "19:00", "21:00"]
        used_times: set[str] = set()
        for e in all_events:
            if e.approximate_time in used_times:
                # 找一个空闲时间
                for t in slot_pool:
                    if t not in used_times:
                        e.approximate_time = t
                        # 同步更新 time_slot
                        hour = int(t.split(":")[0])
                        if hour < 12: e.time_slot = "morning"
                        elif hour < 17: e.time_slot = "afternoon"
                        elif hour < 22: e.time_slot = "evening"
                        else: e.time_slot = "night"
                        break
            used_times.add(e.approximate_time)

        # 按 approximate_time 排序 (actual time string, not slot order)
        all_events.sort(key=lambda e: e.approximate_time)

        # 生成 dream_seed
        dream_seed = ", ".join(e.activity for e in all_events[:3])

        tomorrow = _dt.date.today() + _dt.timedelta(days=1)
        plan = DailyPlan(
            date=tomorrow.isoformat(),
            generated_at=time.time(),
            events=all_events,
            personality_snapshot=dict(personality),
            adaptations=[],
            dream_seed=dream_seed,
        )
        self._current_plan = plan
        return plan

    # ── Schedule context injection (Task 6) ─────────────────────────────

    def build_schedule_context(self, now: float | None = None) -> str:
        """将日程注入 system_prompt。

        返回人类可读的字符串，包含:
        - 当前时段计划事件
        - 已取消事件 (含原因)
        - 已完成事件 (最近 2 个)
        无计划时返回空字符串。
        """
        from .life_plan import _time_to_slot
        if not self._current_plan:
            return ""
        if now is None:
            now = time.time()

        current_slot = _time_to_slot(now)
        current_events = [
            e for e in self._current_plan.events
            if e.time_slot == current_slot and e.status == "planned"
        ]
        done_events = [e for e in self._current_plan.events if e.status == "done"]
        cancelled_events = [
            e for e in self._current_plan.events if e.status == "cancelled"
        ]

        parts: list[str] = []
        if current_events:
            activities = ", ".join(e.activity for e in current_events)
            parts.append(f"你现在计划做: {activities}")
        if cancelled_events:
            reasons = ", ".join(
                f"{e.activity}(因为{e.cancellation_reason})" for e in cancelled_events
            )
            parts.append(f"今天取消了: {reasons}")
        if done_events:
            done = ", ".join(e.activity for e in done_events[-2:])
            parts.append(f"今天已经做了: {done}")

        return "。".join(parts) + "。" if parts else ""

    # ── Persistence (Task 7) ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize LifeSimulatorV2 state for persistence."""
        data: dict[str, Any] = {}
        if self._current_plan:
            data["current_plan"] = self._current_plan.to_dict()
        return data

    def from_dict(self, data: dict[str, Any]) -> None:
        """Restore LifeSimulatorV2 state from persistence."""
        from .life_plan import DailyPlan
        plan_data = data.get("current_plan")
        if plan_data:
            self._current_plan = DailyPlan.from_dict(plan_data)

    # ── Plan adaptation (Task 5) ────────────────────────────────────────

    # 户外活动关键词
    _OUTDOOR_KEYWORDS = {"逛商场", "出门", "散步", "跑步", "去咖啡店", "出门见人", "公园"}
    # 社交活动关键词
    _SOCIAL_KEYWORDS = {"和朋友", "出门见人", "逛商场", "去咖啡店", "聊天"}

    def adapt_plan(
        self,
        emotion_delta: float = 0.0,
        cascade_active: bool = False,
        boundary_pressure: float = 0.0,
    ) -> list[dict]:
        """根据当前状态调整计划。返回调整动作列表。

        规则:
        1. 情绪下降 + 社交事件 → 取消
        2. cascade_active → 取消户外事件
        3. boundary_pressure > 0.7 → 取消社交事件

        人格调制:
        - neuroticism 高 → 阈值降低 (更容易取消)
        - conscientiousness 高 → 阈值提高 (更坚持计划)
        """
        if not self._current_plan:
            return []

        personality = self._current_plan.personality_snapshot
        neuroticism = personality.get("neuroticism", 0.5)
        conscientiousness = personality.get("conscientiousness", 0.5)

        # 基础阈值，被人格调制
        base_threshold = 0.3
        # neuroticism 高 → 阈值降低 (更容易取消)
        # conscientiousness 高 → 阈值提高 (更坚持计划)
        threshold = base_threshold * (
            1.0 - 0.7 * (neuroticism - 0.5) + 0.3 * (conscientiousness - 0.5)
        )
        threshold = max(0.1, min(0.6, threshold))

        actions: list[dict] = []
        for event in self._current_plan.events:
            if event.status != "planned":
                continue

            should_cancel = False
            reason = ""

            # 规则 1: 情绪下降 + 社交事件 → 取消
            if emotion_delta < -threshold:
                if any(kw in event.activity for kw in self._SOCIAL_KEYWORDS):
                    should_cancel = True
                    reason = "情绪下降，不想社交"

            # 规则 2: cascade_active → 取消户外事件
            if cascade_active:
                if any(kw in event.activity for kw in self._OUTDOOR_KEYWORDS):
                    should_cancel = True
                    reason = "情绪连锁反应，需要独处"

            # 规则 3: boundary_pressure 高 → 取消社交事件
            if boundary_pressure > 0.7:
                if any(kw in event.activity for kw in self._SOCIAL_KEYWORDS):
                    should_cancel = True
                    reason = "边界压力过高"

            # flexibility 检查: 只有 flexibility 足够高才能取消
            if should_cancel and event.flexibility < 0.3:
                should_cancel = False  # 不可改变的事件

            if should_cancel:
                event.status = "cancelled"
                event.cancellation_reason = reason
                self._current_plan.adaptations.append({
                    "event_id": event.id,
                    "action": "cancel",
                    "reason": reason,
                    "timestamp": time.time(),
                })
                actions.append({"action": "cancel", "event_id": event.id, "reason": reason})

        return actions

    # ── LLM random event generation (Task 3) ──────────────────────────

    _LLM_PLAN_PROMPT = """你是一个生活模拟器。根据以下信息，为角色规划 1-2 个随机生活事件。

角色人格: {personality}
近期记忆: {recent_memories}
昨天发生的事: {yesterday_events}

要求:
- 事件要符合角色性格
- 要有变化（不要每天都一样）
- 要考虑昨天的经历（昨天很累→今天休息）
- 输出 JSON 数组: [{{"time": "afternoon", "activity": "去公园散步", "mood": "期待"}}]
- time 只能是 "morning" / "afternoon" / "evening"
- 只输出 JSON，不要其他文字"""

    async def generate_plan_llm(
        self,
        personality: dict[str, float],
        recent_memories: list[str],
        yesterday_events: list[str],
    ) -> list["PlannedEvent"]:
        """调 LLM 生成 1-2 个随机事件。"""
        if not self._llm_caller:
            return []

        import json as _json
        import time as _time
        from .life_plan import PlannedEvent as _PlannedEvent

        mem_text = "\n".join(f"- {m}" for m in recent_memories[:5]) or "（暂无）"
        yes_text = "\n".join(f"- {e}" for e in yesterday_events[:3]) or "（暂无）"
        p_desc = ", ".join(f"{k}={v:.1f}" for k, v in personality.items())

        prompt = self._LLM_PLAN_PROMPT.format(
            personality=p_desc,
            recent_memories=mem_text,
            yesterday_events=yes_text,
        )

        try:
            response = await self._llm_caller("你是生活模拟器。只输出 JSON。", prompt)
            text = response.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start < 0 or end <= start:
                return []
            data = _json.loads(text[start:end])
            if not isinstance(data, list):
                return []

            slot_times = {"morning": "10:00", "afternoon": "14:00", "evening": "18:00"}
            events: list[_PlannedEvent] = []
            for i, item in enumerate(data[:2]):
                if not isinstance(item, dict):
                    continue
                slot = str(item.get("time", "afternoon"))
                if slot not in slot_times:
                    slot = "afternoon"
                events.append(_PlannedEvent(
                    id=f"llm_{i}_{int(_time.time())}",
                    time_slot=slot,
                    approximate_time=slot_times.get(slot, "14:00"),
                    activity=str(item.get("activity", "发呆"))[:50],
                    category="llm_random",
                    mood_expectation=str(item.get("mood", "平淡"))[:20],
                    flexibility=0.7,
                ))
            return events
        except Exception:
            return []
