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
    "_flatten_personality",
]


# ═══════════════════════════════════════════════════════════════════════
# v1.2.5 PR3 T9: 拍平嵌套 personality dict (Bug 14 防回归)
# ═══════════════════════════════════════════════════════════════════════

def _flatten_personality(p: dict) -> list[tuple[str, float]]:
    """拍平嵌套 personality dict 为 (qualified_key, scalar) 列表。

    处理三种 shape:
    - 嵌套: {"deep": {"expression_drive": 0.15, ...}, ...} (真实数据源, persona_profiles.py:120)
    - flat: {"openness": 0.5, ...} (fallback, main.py:923)
    - mixed: {"deep": {...}, "top_level_scalar": 0.8} (防御性)

    非 scalar 值 (str, None, 嵌套 dict, bool) 跳过, 不崩.
    """
    flat = []
    for layer, params in p.items():
        if isinstance(params, dict):
            for k, v in params.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    flat.append((f"{layer}.{k}", float(v)))
        elif isinstance(params, (int, float)) and not isinstance(params, bool):
            flat.append((layer, float(params)))
    return flat


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


@register(
    name="life_simulator_v2",
    provides=["LifeSimulatorV2"],
    depends_on=[
        "surface_consumer", "memory_pool", "intimacy",
        "buffer_signals", "meaning_reservoir",
        "environment_context", "personality_feedback",
        "project_manager", "recovery_tracker",
    ],
    param_wire={
        "memory_pool": "memory",
        "buffer_signals": "signals",
        "surface_consumer": "consumer",
        "intimacy": "intimacy",
        "meaning_reservoir": "reservoir",
        "environment_context": "env_ctx",
        "personality_feedback": "feedback",
        "project_manager": "project_mgr",
        "recovery_tracker": "recovery",
    },
)
class LifeSimulatorV2:
    """v2: 主动规划日程 + 实时根据对话调整。"""

    def __init__(
        self,
        consumer: "SurfaceConsumer",
        memory: "MemoryPool",
        intimacy: "IntimacyTracker",
        signals: "BufferSignals",
        reservoir: "MeaningReservoir",
        env_ctx: "EnvironmentContext | None" = None,
        feedback: "PersonalityFeedback | None" = None,
        project_mgr: "ProjectManager | None" = None,
        recovery: "RecoveryTracker | None" = None,
    ) -> None:
        self._consumer = consumer
        self._memory = memory
        self._sampler = MemorySampler(memory)
        self._intimacy = intimacy
        self._signals = signals
        self._reservoir = reservoir
        self._current_plan: "DailyPlan | None" = None
        self._llm_caller: Callable[[str, str], Awaitable[str]] | None = None
        # v1.2.7: 4 组件接通
        self._env_ctx = env_ctx
        self._feedback = feedback
        self._project_mgr = project_mgr
        self._recovery = recovery
        self._latest_mood_adjustment: str = ""  # emotion_predictor 输出

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
        from .life_plan import (
            PlannedEvent as _PlannedEvent, select_template_activities,
            PERSONALITY_ACTIVITY_BIAS,
        )
        import time as _time

        activities = select_template_activities(personality, n=n)

        # v1.1.0C: apply PERSONALITY_ACTIVITY_BIAS to re-rank selected activities.
        # v1.2.7: +environment_context + energy_model biases
        weighted_activities = []
        for i, (cat, activity) in enumerate(activities):
            weight = 1.0
            for trait, biases in PERSONALITY_ACTIVITY_BIAS.items():
                weight += personality.get(trait, 0.5) * biases.get(cat, 0.0)
            # v1.2.7: environment_context bias (season + day-of-week)
            if self._env_ctx:
                season_bias = self._env_ctx.get_season_bias()
                weight += season_bias.get(cat, 0.0)
                day_bias = self._env_ctx.get_day_bias()
                weight += day_bias.get(cat, 0.0)
            # v1.2.7: energy_model bias (slot-dependent)
            slot_idx = i % 3  # morning/afternoon/evening
            slot_names = ["morning", "afternoon", "evening"]
            try:
                from ..utils.energy_model import get_energy_level, apply_energy_bias
                energy = get_energy_level(personality, slot_names[slot_idx])
                weight = apply_energy_bias({cat: weight}, energy).get(cat, weight)
            except Exception:
                pass
            weighted_activities.append((cat, activity, weight))
        weighted_activities.sort(key=lambda x: -x[2])
        activities = [(cat, activity) for cat, activity, _ in weighted_activities[:n]]
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
        p_desc = ", ".join(f"{k}={v:.1f}" for k, v in _flatten_personality(personality))
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
        user_activity: dict | None = None,
    ) -> "DailyPlan":
        """生成今天的日程计划 (模板 + LLM 组合)。

        v1.3.0 rc.5 Bug-I: plan.date = date.today() (不是 today+1).
        cron 在 02:00 (< 6am 逻辑日边界) 触发, date.today() = 即将到来的逻辑日.
        原 today+1 让 /view_schedule 永远显示明天 + dedup 双路径不一致.
        """
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

        plan = DailyPlan(
            date=_dt.date.today().isoformat(),
            generated_at=time.time(),
            events=all_events,
            personality_snapshot=dict(personality),
            adaptations=[],
            dream_seed=dream_seed,
        )
        # v1.2.7: recovery_tracker — 推进恢复阶段
        if self._recovery and self._recovery._active_recovery is not None:
            try:
                self._recovery.advance_stage()
            except Exception:
                pass

        self._current_plan = plan

        # v1.2.7: project_manager — 注入多日项目事件
        if self._project_mgr:
            try:
                project = self._project_mgr.suggest_project(personality)
                if project:
                    self._project_mgr.inject_into_plan(plan)
            except Exception:
                pass

        # v1.2.7: user_activity — 注入用户提及的活动
        if user_activity:
            try:
                from ..utils.user_activity_detector import UserActivityDetector
                UserActivityDetector().inject_into_plan(plan, user_activity)
            except Exception:
                pass

        # v1.2.7: emotion_predictor — 预测情绪轨迹
        self._latest_mood_adjustment = ""
        try:
            from ..utils.emotion_predictor import EmotionPredictor
            predictor = EmotionPredictor()
            current_mood = personality.get("neuroticism", 0.5)
            trajectory = predictor.predict_mood_trajectory(plan, current_mood)
            adj = predictor.suggest_adjustment(trajectory)
            if adj:
                self._latest_mood_adjustment = adj
        except Exception:
            pass

        return plan

    # ── Schedule context injection (Task 6) ─────────────────────────────

    def build_schedule_context(self, now: float | None = None) -> str:
        """将日程注入 system_prompt。

        返回人类可读的字符串，包含:
        - 当前时段计划事件
        - 已取消事件 (含原因)
        - 已完成事件 (最近 2 个)
        无计划时返回空字符串。

        Fallback: 如果当前时段没有 planned 事件（CI 时段错配 / 用户查不在活动时段的计划），
        自动 fallback 到展示今日全部 planned 事件（按 time_slot 排序），避免返回空字符串。
        """
        from .life_plan import _time_to_slot
        # 时段顺序常量（避免依赖 life_plan 的内部 _SLOT_ORDER，未来统一）
        _SLOT_ORDER = {"morning": 0, "afternoon": 1, "evening": 2, "night": 3}
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
        else:
            # Fallback: 当前时段无 planned 事件 → 展示今日全部 planned (按时段顺序)
            all_planned = [e for e in self._current_plan.events if e.status == "planned"]
            if all_planned:
                all_planned.sort(key=lambda e: _SLOT_ORDER.get(e.time_slot, 99))
                activities = ", ".join(f"{e.time_slot}{e.activity}" for e in all_planned)
                parts.append(f"今天计划: {activities}")
        if cancelled_events:
            reasons = ", ".join(
                f"{e.activity}(因为{e.cancellation_reason})" for e in cancelled_events
            )
            parts.append(f"今天取消了: {reasons}")
        if done_events:
            done = ", ".join(e.activity for e in done_events[-2:])
            parts.append(f"今天已经做了: {done}")

        # v1.2.7: emotion_predictor mood adjustment
        if self._latest_mood_adjustment:
            parts.append(f"情绪提醒: {self._latest_mood_adjustment}")

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

    # ── Extension persistence (v1.2.8: 公开接口, 替代外部伸手 _project_mgr/_recovery 私有) ──

    def persist_extensions(self) -> dict[str, Any]:
        """持久化接通的扩展组件 (project_manager / recovery_tracker).

        返回 {key: to_dict()|None}。caller (main.py _persist_modules) 遍历写 store,
        不再直接访问 self._project_mgr / self._recovery 私有属性。
        """
        data: dict[str, Any] = {}
        if self._project_mgr and hasattr(self._project_mgr, "to_dict"):
            data["project_manager"] = self._project_mgr.to_dict()
        if self._recovery and hasattr(self._recovery, "to_dict"):
            data["recovery_tracker"] = self._recovery.to_dict()
        return data

    def restore_extensions(self, data: dict[str, Any]) -> None:
        """恢复扩展组件状态 (main.py _load 调用)."""
        pm_data = data.get("project_manager")
        if pm_data and self._project_mgr and hasattr(self._project_mgr, "from_dict"):
            self._project_mgr.from_dict(pm_data)
        rc_data = data.get("recovery_tracker")
        if rc_data and self._recovery and hasattr(self._recovery, "from_dict"):
            self._recovery.from_dict(rc_data)

    def trigger_recovery(self, archetype: str) -> None:
        """触发崩溃恢复 (封装 recovery_tracker.start_recovery, surface_handler 调用)."""
        if self._recovery and hasattr(self._recovery, "start_recovery"):
            self._recovery.start_recovery(archetype)

    # ── Plan adaptation (v1.1.0C Task 3: emotion × personality × suppression × collapse) ──

    # 户外活动关键词 (legacy, kept for reference)
    _OUTDOOR_KEYWORDS = {"逛商场", "出门", "散步", "跑步", "去咖啡店", "出门见人", "公园"}
    # 社交活动关键词 (legacy, kept for reference)
    _SOCIAL_KEYWORDS = {"和朋友", "出门见人", "逛商场", "去咖啡店", "聊天"}

    def _is_social_event(self, event) -> bool:
        """Check if event is social category.

        Social = category in (social, template) AND activity contains a social keyword.
        Template events are checked because templates may render social activities.
        """
        if event.category not in ("social", "template"):
            return False
        return any(
            kw in event.activity
            for kw in ("聊天", "出门", "逛街", "咖啡店", "社交")
        )

    def adapt_plan(
        self,
        emotion_state: dict,
        personality: dict[str, float],
        suppression_level: float = 0.0,
        collapse_archetype: str | None = None,
    ) -> list[dict]:
        """Adapt daily plan based on emotion × personality × suppression × collapse.

        Uses compute_social_tendency() to decide whether to keep or cancel events,
        and select_adaptation_activity() to find replacement categories.

        v1.2.7: +recovery_tracker (替换事件) + personality_feedback (只读反馈).
        """
        from ..utils.adaptation import compute_social_tendency, select_adaptation_activity

        if not self._current_plan:
            return []

        # v1.2.7: recovery_tracker — 若 active recovery, 替换当天事件
        if self._recovery and self._recovery._active_recovery is not None:
            try:
                self._recovery.adapt_plan_for_recovery(self._current_plan)
            except Exception:
                pass

        tendency = compute_social_tendency(
            emotion_state, personality, suppression_level, collapse_archetype
        )
        actions: list[dict] = []

        for event in self._current_plan.events:
            if event.status != "planned":
                continue
            is_social = self._is_social_event(event)

            if tendency == "seek" and not is_social:
                replacement_cat = select_adaptation_activity(emotion_state, personality, "seek")
                event.status = "cancelled"
                event.cancellation_reason = "想找人聊聊"
                actions.append({
                    "action": "cancel", "event_id": event.id,
                    "replace_category": replacement_cat, "tendency": "seek",
                })
            elif tendency == "avoid" and is_social:
                replacement_cat = select_adaptation_activity(emotion_state, personality, "avoid")
                event.status = "cancelled"
                event.cancellation_reason = "想一个人呆着"
                actions.append({
                    "action": "cancel", "event_id": event.id,
                    "replace_category": replacement_cat, "tendency": "avoid",
                })

        if self._current_plan.adaptations is None:
            self._current_plan.adaptations = []
        self._current_plan.adaptations.extend(actions)

        # v1.2.7: personality_feedback (只读输出给 compose)
        if self._feedback:
            try:
                cancelled_categories = [
                    e.category for e in self._current_plan.events
                    if e.status == "cancelled"
                ]
                for cat in cancelled_categories:
                    delta = self._feedback.compute_feedback(personality, cat)
                    if delta:
                        self._current_plan.adaptations.append({
                            "action": "feedback",
                            "source_category": cat,
                            "delta": delta,
                        })
            except Exception:
                pass

        return actions

    # ── LLM random event generation (Task 3) ──────────────────────────

    _LLM_PLAN_PROMPT = """你是一个生活模拟器。根据以下信息，为角色规划 1-2 个随机生活事件。

角色人格: {personality}
人格偏好 (5维): {personality_preferences}
近期记忆: {recent_memories}
昨天发生的事: {yesterday_events}

要求:
- 事件要符合角色性格和当前情绪偏好
- 高外向 → 倾向社交/运动类活动
- 高开放 → 倾向创造/探索类活动
- 高尽责 → 倾向整理/计划类活动
- 高宜人 → 倾向照顾/社交类活动
- 高神经质 → 倾向独处/反思类活动
- 要有变化（不要每天都一样）
- 输出 JSON: [{{"time": "afternoon", "activity": "...", "mood": "..."}}]
"""

    async def generate_plan_llm(
        self,
        personality: dict[str, float],
        recent_memories: list[str],
        yesterday_events: list[str],
    ) -> list["PlannedEvent"]:
        """调 LLM 生成 1-2 个随机事件。

        v1.1.0C: Now passes personality_preferences (7-dim activity preference
        vector derived from personality via derive_activity_preferences) so the
        LLM can bias event selection toward categories the character gravitates
        toward.
        """
        if not self._llm_caller:
            return []

        from ..utils.adaptation import derive_activity_preferences
        import json as _json
        import time as _time
        from .life_plan import PlannedEvent as _PlannedEvent

        mem_text = "\n".join(f"- {m}" for m in recent_memories[:5]) or "（暂无）"
        yes_text = "\n".join(f"- {e}" for e in yesterday_events[:3]) or "（暂无）"
        p_desc = ", ".join(f"{k}={v:.1f}" for k, v in _flatten_personality(personality))
        preferences = derive_activity_preferences(personality)
        pref_text = ", ".join(f"{k}={v:.2f}" for k, v in preferences.items())

        prompt = self._LLM_PLAN_PROMPT.format(
            personality=p_desc,
            personality_preferences=pref_text,
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
