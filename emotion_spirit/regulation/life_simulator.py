"""Life Simulator — Mode A (对话驱动) / Mode B (自主保底) 双模式。

Mode A: 用户消息后 60s idle 或满 15 轮
Mode B: 2-4h 无对话, 系统状态允许时触发

v3.0 Phase G: LLM 生活片段生成
- LifeEvent 数据结构 (从 Sylanne 1.4.7 引入)
- 7 种事件类型 + 情绪权重
- configure(llm_caller=) 注入 LLM callable
- generate_life_prose() 调用 LLM 生成生活片段
- pending_life_event 供 bot_decision 上下文注入
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, TYPE_CHECKING

from ..core.config import LIFE_SIM_CONFIG
from ..output.surface_consumer import SemanticSignals

if TYPE_CHECKING:
    from ..memory.memory_pool import MemoryPool
    from ..memory.intimacy import IntimacyTracker
    from ..output.buffer_signals import BufferSignals
    from ..memory.meaning_reservoir import MeaningReservoir
    from ..output.surface_consumer import SurfaceConsumer
    from .life_plan import PlannedEvent, DailyPlan

from ..output.emotion_classifier import build_emotion_payload  # v1.1.2: 共享层
from ..memory.memory_sampler import MemorySampler, SampledMemory


from ..core.registry import register


__all__ = [
    "LifeSimulator",
    "LifeSimulatorV2",
    "LifeEvent",
    "LifeEventType",
    "LIFE_EVENT_WEIGHTS",
]

# Neutral baseline personality for sampling when none is provided.
_DEFAULT_PERSONALITY: dict[str, float] = {
    "openness": 0.5,
    "extraversion": 0.5,
    "agreeableness": 0.5,
    "neuroticism": 0.5,
    "conscientiousness": 0.5,
    "emotional_stability": 0.5,
}


# ═══════════════════════════════════════════════════════════════════════
# LifeEvent 数据结构 (从 Sylanne 1.4.7 引入, Phase G)
# ═══════════════════════════════════════════════════════════════════════


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

# 事件类型关键词映射 (用于从 LLM 输出推断事件类型)
_EVENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "reading": ["读", "书", "阅读", "看书", "翻阅", "read", "book", "novel", "article"],
    "walking": ["走", "散步", "漫步", "路", "walk", "stroll", "hike", "wander"],
    "cooking": ["做饭", "烹饪", "厨房", "煮", "烤", "cook", "kitchen", "bak", "meal"],
    "thinking": ["想", "思考", "沉思", "冥想", "think", "ponder", "reflect", "contempl"],
    "creating": ["创作", "画", "写", "做", "制作", "creat", "draw", "writ", "craft", "paint", "compos"],
    "resting": ["休息", "睡", "躺", "放松", "rest", "sleep", "relax", "nap", "doze"],
    "observing": ["观察", "看", "注视", "望", "observ", "watch", "gaze", "notic"],
}

# LLM 生活片段生成 prompt 模板
_LIFE_SIM_PROMPT = """你是一个创意写作助手。请为以下虚构角色生成一个当前时刻的生活片段。

注意：你不是在扮演这个角色对话，而是在模拟她独处时的生活状态——她此刻在做什么、想什么、心情如何。
输出应该是第三人称视角的简短生活快照。

角色设定：
{persona_desc}

当前环境：
- 时间：{time_desc}
- 角色情绪倾向：{emotion_desc}
- 距离上次和朋友聊天：{last_chat_desc}
- 近期记忆素材：{memory_texts}

请根据角色设定，生成这个角色此刻可能在做什么、想什么。内容要符合角色的性格和习惯。
用 JSON 格式输出：
{{"activity": "正在做什么（简短）", "thought": "在想什么（简短）", "mood": "当前心情（一个词）", "wants_to_share": true/false, "share_reason": "如果想分享给朋友，原因（简短）", "urgency": 0.0-1.0}}"""


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
    """双模式 Life Sim。"""

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
        # Phase G: LLM 生活片段生成
        self._llm_caller: Callable[[str, str], Awaitable[str]] | None = None
        self._events: list[LifeEvent] = []
        self._pending_life_event: LifeEvent | None = None

    def on_user_message(self) -> None:
        """用户消息到达时调用。重置 Mode B 计时。"""
        self._turn_count += 1
        self._last_interaction = time.time()
        self._mode_b_cooldown = LIFE_SIM_CONFIG["mode_b_cooldown_after_trigger_minutes"] * 60

    # ═══════════════════════════════════════════════════════════════════
    # Phase G: LLM 生活片段生成
    # ═══════════════════════════════════════════════════════════════════

    def configure(
        self,
        llm_caller: Callable[[str, str], Awaitable[str]] | None = None,
    ) -> None:
        """注入 LLM callable。由 main.py 在初始化时调用。"""
        self._llm_caller = llm_caller

    @property
    def pending_life_event(self) -> LifeEvent | None:
        """获取待消费的生活事件 (供 bot_decision 上下文注入)。"""
        return self._pending_life_event

    def consume_life_event(self) -> LifeEvent | None:
        """消费待处理的生活事件 (一次性)。"""
        event = self._pending_life_event
        self._pending_life_event = None
        return event

    async def generate_life_prose(
        self,
        event_dict: dict[str, Any],
        persona_desc: str = "",
        personality: dict[str, float] | None = None,
    ) -> LifeEvent | None:
        """从 Mode A/B 事件 dict 生成 LifeEvent。

        有 LLM 时调用 LLM 生成自然语言生活片段;
        无 LLM 时用规则 fallback。
        """
        now = time.time()
        memories = event_dict.get("memories", [])
        state_narrative = event_dict.get("state_narrative", "")
        signals_data = event_dict.get("signals", {})
        emotion = event_dict.get("emotion")

        # 构建记忆素材文本
        memory_texts = "\n".join(
            f"- [{m.get('layer', '?')}] {m.get('text', '')}"
            for m in memories[:3]
        ) if memories else "（暂无近期记忆）"

        # 情绪描述
        emotion_desc = self._describe_emotion(signals_data, emotion)

        # 时间描述
        import datetime
        dt = datetime.datetime.fromtimestamp(now)
        time_desc = dt.strftime("%H:%M, %A")

        # 距离上次交互
        gap = now - self._last_interaction
        if gap < 60:
            last_chat_desc = "刚刚"
        elif gap < 3600:
            last_chat_desc = f"{int(gap / 60)} 分钟前"
        elif gap < 86400:
            last_chat_desc = f"{int(gap / 3600)} 小时前"
        else:
            last_chat_desc = f"{int(gap / 86400)} 天前"

        p = personality or _DEFAULT_PERSONALITY

        if self._llm_caller:
            try:
                return await self._generate_with_llm(
                    persona_desc or "一个有自己生活节奏的虚构角色",
                    time_desc,
                    emotion_desc,
                    last_chat_desc,
                    memory_texts,
                    state_narrative,
                    p,
                    now,
                )
            except Exception:
                pass  # LLM 失败时 fallback 到规则

        # 规则 fallback
        return self._generate_fallback(memories, state_narrative, now, p)

    def check_mode_a(
        self,
        signals: SemanticSignals,
        personality: dict[str, float] | None = None,
    ) -> dict[str, Any] | None:
        """检查 Mode A 触发条件。返回事件或 None。"""
        idle_seconds = time.time() - self._last_interaction
        max_turns = int(LIFE_SIM_CONFIG["mode_a_max_turns"])

        if idle_seconds >= LIFE_SIM_CONFIG["mode_a_idle_seconds"] or self._turn_count >= max_turns:
            self._turn_count = 0
            p = personality if personality is not None else _DEFAULT_PERSONALITY
            samples = self._sampler.sample(p, k=3)
            if samples:
                return {
                    "type": "mode_a",
                    "trigger": "idle" if idle_seconds >= LIFE_SIM_CONFIG["mode_a_idle_seconds"] else "turn_limit",
                    "memories": [
                        {
                            "text": s.entry.text,
                            "layer": s.layer,
                            "temperature": round(s.entry.temperature, 3),
                            "emotional_weight": round(s.entry.emotional_weight, 3),
                            "tags": s.entry.tags,
                        }
                        for s in samples
                    ],
                    "state_narrative": self._generate_state_narrative(
                        mean_temp=self._memory.mean_temperature(),
                        cascade_active=self._memory.cascade_active(),
                        ghost_count=len(self._memory.get_layer("ghost")),
                    ),
                    "signals": {
                        "rhythm_beat": signals.rhythm_beat,
                        "valence_warmth": signals.valence_warmth,
                        "needs_expression": signals.needs_expression,
                        # v1.1.1: 结构化情绪数据
                        "pad": {
                            "valence": signals.pad_valence,
                            "arousal": signals.pad_arousal,
                            "dominance": signals.pad_dominance,
                        },
                        "emotion_distribution": signals.pad_distribution,
                        "emotion_primary": signals.pad_primary,
                        "emotion_secondary": signals.pad_secondary,
                        "emotion_intensity": signals.pad_intensity,
                        # v1.2: 动态字段
                        "emotion_ambiguity": signals.emotion_ambiguity,
                        "emotion_velocity": signals.emotion_velocity,
                    },
                }
        return None

    def check_mode_b(
        self,
        signals: SemanticSignals,
        personality: dict[str, float] | None = None,
    ) -> dict[str, Any] | None:
        """检查 Mode B 触发条件。返回事件或 None。"""
        now = time.time()

        # 冷却期
        if now - self._last_mode_b < self._mode_b_cooldown:
            return None

        # 间隔检查
        min_interval = self._mode_b_interval(self._interaction_density())
        if now - self._last_interaction < min_interval:
            return None

        # 状态条件
        if not self._can_mode_b_trigger(signals):
            return None

        self._last_mode_b = now
        self._mode_b_cooldown = LIFE_SIM_CONFIG["mode_b_cooldown_after_trigger_minutes"] * 60

        p = personality if personality is not None else _DEFAULT_PERSONALITY
        samples = self._sampler.sample(p, k=3)
        reservoir_level = self._reservoir.level
        phi = signals.phi_smoothed

        # v1.1.2: 从共享 emotion_classifier.build_emotion_payload 获取
        emotion_payload = build_emotion_payload(signals)

        if samples and reservoir_level > 0.3:
            return self._generate_life_event(
                samples, phi, self._signals.mode_b_strategy(), emotion_payload
            )
        elif samples:
            return self._generate_reflection(samples, phi, emotion_payload)
        else:
            return self._generate_soliloquy(phi, emotion_payload)

    def _can_mode_b_trigger(self, signals: SemanticSignals) -> bool:
        """Mode B 触发条件 (全部从 Surface 读)。"""
        return (
            signals.needs_expression > 0.5
            and signals.boundary_budget > 0.1
            and signals.boundary_cooldown == 0
            and not signals.boundary_paused
            and signals.capacity_exhaustion < 0.6
            and signals.needs_quiet < 0.5
            and not signals.cascade_active
            and signals.body_criticality < 0.5
        )

    def _mode_b_interval(self, density: float) -> float:
        """Mode B 触发间隔 (秒)。"""
        base = LIFE_SIM_CONFIG["mode_b_min_hours"] * 3600
        # 根据交互密度动态调整: 密度越高，间隔越短
        return max(3600, base * (1 - 0.3 * (1 - density)))

    def _interaction_density(self) -> float:
        """交互密度 [0, 1]。"""
        elapsed_hours = (time.time() - self._last_interaction) / 3600
        if elapsed_hours < 1:
            return 1.0
        return max(0.0, 1.0 - elapsed_hours / 24)

    def _generate_life_event(
        self,
        samples: list[SampledMemory],
        phi: float,
        strategy: str,
        emotion_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Mode B 生活事件。"""
        self._reservoir.draw(0.1)
        result: dict[str, Any] = {
            "type": "mode_b",
            "subtype": "life_event",
            "strategy": strategy,
            "memories": [
                {
                    "text": s.entry.text,
                    "layer": s.layer,
                    "temperature": round(s.entry.temperature, 3),
                    "emotional_weight": round(s.entry.emotional_weight, 3),
                    "tags": s.entry.tags,
                }
                for s in samples
            ],
            "phi": phi,
            "reservoir_used": 0.1,
            "state_narrative": self._generate_state_narrative(
                mean_temp=self._memory.mean_temperature(),
                cascade_active=self._memory.cascade_active(),
                ghost_count=len(self._memory.get_layer("ghost")),
            ),
        }
        if emotion_payload is not None:
            result["emotion"] = emotion_payload  # v1.1.1
        return result

    def _generate_reflection(
        self,
        samples: list[SampledMemory],
        phi: float,
        emotion_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """反思性独白。"""
        result: dict[str, Any] = {
            "type": "mode_b",
            "subtype": "reflection",
            "memories": [
                {
                    "text": s.entry.text,
                    "layer": s.layer,
                    "temperature": round(s.entry.temperature, 3),
                    "emotional_weight": round(s.entry.emotional_weight, 3),
                    "tags": s.entry.tags,
                }
                for s in samples
            ],
            "phi": phi,
            "state_narrative": self._generate_state_narrative(
                mean_temp=self._memory.mean_temperature(),
                cascade_active=self._memory.cascade_active(),
                ghost_count=len(self._memory.get_layer("ghost")),
            ),
        }
        if emotion_payload is not None:
            result["emotion"] = emotion_payload  # v1.1.1
        return result

    def _generate_soliloquy(
        self,
        phi: float,
        emotion_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """纯独白 (存在性思考)。"""
        result: dict[str, Any] = {
            "type": "mode_b",
            "subtype": "soliloquy",
            "memories": [],
            "phi": phi,
            "state_narrative": self._generate_state_narrative(
                mean_temp=self._memory.mean_temperature(),
                cascade_active=self._memory.cascade_active(),
                ghost_count=len(self._memory.get_layer("ghost")),
            ),
        }
        if emotion_payload is not None:
            result["emotion"] = emotion_payload  # v1.1.1
        return result

    @staticmethod
    def _generate_state_narrative(
        mean_temp: float,
        cascade_active: bool,
        ghost_count: int,
        body: dict[str, float] | None = None,
    ) -> str:
        """Rule-based state narrative describing the bot's current internal state."""
        parts: list[str] = []
        if mean_temp > 0.7:
            parts.append("你现在内心很不平静，很多情绪在翻涌")
        elif mean_temp > 0.4:
            parts.append("你现在有些心绪不宁")
        else:
            parts.append("你现在相对平静")
        if cascade_active:
            parts.append("一个念头牵出另一个念头，思绪在连锁反应")
        if ghost_count > 0:
            parts.append(f"有 {ghost_count} 个很久以前的画面一直在脑海里挥之不去")
        return "，".join(parts) + "。"

    # ═══════════════════════════════════════════════════════════════════
    # Phase G: LLM 生成 + 规则 fallback + 事件类型推断
    # ═══════════════════════════════════════════════════════════════════

    async def _generate_with_llm(
        self,
        persona_desc: str,
        time_desc: str,
        emotion_desc: str,
        last_chat_desc: str,
        memory_texts: str,
        state_narrative: str,
        personality: dict[str, float],
        now: float,
    ) -> LifeEvent | None:
        """调用 LLM 生成生活片段。"""
        prompt = _LIFE_SIM_PROMPT.format(
            persona_desc=persona_desc[:500],
            time_desc=time_desc,
            emotion_desc=emotion_desc,
            last_chat_desc=last_chat_desc,
            memory_texts=memory_texts[:300],
        )
        if state_narrative:
            prompt += f"\n当前内心状态：{state_narrative}"

        system_prompt = "你是一个创意写作助手，负责模拟角色独处时的生活状态。请用 JSON 格式输出。"
        response = await self._llm_caller(system_prompt, prompt)  # type: ignore[misc]
        return self._parse_llm_response(response, now, personality)

    def _parse_llm_response(
        self,
        response: str,
        now: float,
        personality: dict[str, float],
    ) -> LifeEvent | None:
        """解析 LLM JSON 响应为 LifeEvent。容错处理。"""
        try:
            text = response.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                return None
            data = json.loads(text[start:end])
            activity = str(data.get("activity", ""))
            thought = str(data.get("thought", ""))
            combined = f"{activity}" if not thought else f"{activity}（{thought}）"
            event_type = self._infer_event_type(combined)

            event = LifeEvent(
                text=combined[:200],
                mood=str(data.get("mood", "neutral"))[:20],
                urgency=max(0.0, min(1.0, float(data.get("urgency", 0.0)))),
                timestamp=now,
                wants_to_share=bool(data.get("wants_to_share", False)),
                event_type=event_type,
            )

            # 事件类型情绪权重调制
            weights = self._apply_event_emotion_weights(event)
            if weights.get("share_tendency", 0.0) > 0.5 and not event.wants_to_share:
                import random
                if random.random() < weights["share_tendency"] * 0.5:
                    event.wants_to_share = True

            self._events.append(event)
            if len(self._events) > 50:
                self._events = self._events[-30:]
            self._store_event_to_memory(event)
            self._pending_life_event = event
            return event
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    def _generate_fallback(
        self,
        memories: list[dict[str, Any]],
        state_narrative: str,
        now: float,
        personality: dict[str, float],
    ) -> LifeEvent:
        """无 LLM 时的规则 fallback 生活片段生成。"""
        import random

        # 根据人格选择活动类型
        if personality.get("openness", 0.5) > 0.6:
            activities = ["reading", "creating", "observing"]
        elif personality.get("extraversion", 0.5) > 0.6:
            activities = ["walking", "cooking", "observing"]
        else:
            activities = ["resting", "thinking", "reading"]

        activity_type = random.choice(activities)
        activity_descs = {
            "reading": "安静地翻着一本书",
            "walking": "出去散了散步",
            "cooking": "给自己做了点吃的",
            "thinking": "坐在那里发呆想事情",
            "creating": "在做些什么创作",
            "resting": "靠在沙发上休息",
            "observing": "望着窗外发呆",
        }

        text = activity_descs.get(activity_type, "安静地待着")
        mood = "平静"
        if state_narrative and "不平静" in state_narrative:
            mood = "心绪不宁"
        elif state_narrative and "心绪不宁" in state_narrative:
            mood = "有些走神"

        event = LifeEvent(
            text=text,
            mood=mood,
            urgency=0.1,
            timestamp=now,
            wants_to_share=False,
            event_type=activity_type,
        )
        self._events.append(event)
        if len(self._events) > 50:
            self._events = self._events[-30:]
        self._store_event_to_memory(event)
        self._pending_life_event = event
        return event

    @staticmethod
    def _infer_event_type(text: str) -> str:
        """从事件文本推断事件类型 (关键词匹配)。"""
        text_lower = text.lower()
        best_type = ""
        best_score = 0
        for event_type, keywords in _EVENT_TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_type = event_type
        return best_type

    @staticmethod
    def _apply_event_emotion_weights(event: LifeEvent) -> dict[str, float]:
        """根据事件类型返回情绪权重 (valence/arousal/share_tendency)。"""
        if not event.event_type or event.event_type not in LIFE_EVENT_WEIGHTS:
            return {"valence": 0.0, "arousal": 0.0, "share_tendency": 0.0}
        return dict(LIFE_EVENT_WEIGHTS[event.event_type])

    def _store_event_to_memory(self, event: LifeEvent) -> None:
        """将 LifeEvent 写入 MemoryPool 作为记忆条目。

        事件类型的情绪权重决定 raw_weight:
          valence 绝对值越高 → 权重越高 (正面或负面事件都印象深刻)
          share_tendency 高 → 权重稍高 (想分享的事件更难忘)
        """
        weights = self._apply_event_emotion_weights(event)
        raw_weight = min(1.0, abs(weights.get("valence", 0.0)) + weights.get("share_tendency", 0.0) * 0.3 + 0.1)
        tags = ["life_event"]
        if event.event_type:
            tags.append(event.event_type)
        if event.mood and event.mood != "neutral":
            tags.append(event.mood)
        try:
            self._memory.add(
                text=event.text,
                raw_weight=raw_weight,
                phi=0.3,  # 生活事件 phi 较低 (不是紧急情绪)
                tags=tags,
                source_user="life_simulator",
            )
        except Exception:
            pass  # 写入失败不影响主流程

    @staticmethod
    def _describe_emotion(
        signals_data: dict[str, Any],
        emotion: dict[str, Any] | None = None,
    ) -> str:
        """从 signals dict 构建情绪描述文本。"""
        parts: list[str] = []
        pad = signals_data.get("pad", {})
        if pad.get("valence", 0) > 0.3:
            parts.append("愉快")
        elif pad.get("valence", 0) < -0.3:
            parts.append("低落")
        if pad.get("arousal", 0) > 0.3:
            parts.append("兴奋")
        elif pad.get("arousal", 0) < -0.3:
            parts.append("平静")
        primary = signals_data.get("emotion_primary", "")
        if primary:
            parts.append(primary)
        return ", ".join(parts) if parts else "neutral"

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_mode_b": self._last_mode_b,
            "mode_b_cooldown": self._mode_b_cooldown,
            "turn_count": self._turn_count,
            "last_interaction": self._last_interaction,
            "events": [
                {
                    "text": e.text,
                    "mood": e.mood,
                    "urgency": e.urgency,
                    "timestamp": e.timestamp,
                    "wants_to_share": e.wants_to_share,
                    "shared": e.shared,
                    "event_type": e.event_type,
                }
                for e in self._events[-20:]
            ],
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self._last_mode_b = data.get("last_mode_b", 0.0)
        self._mode_b_cooldown = data.get("mode_b_cooldown", 0.0)
        self._turn_count = data.get("turn_count", 0)
        self._last_interaction = data.get("last_interaction", time.time())
        for e in data.get("events", []):
            self._events.append(
                LifeEvent(
                    text=e.get("text", ""),
                    mood=e.get("mood", "neutral"),
                    urgency=float(e.get("urgency", 0.0)),
                    timestamp=float(e.get("timestamp", 0.0)),
                    wants_to_share=e.get("wants_to_share", False),
                    shared=e.get("shared", False),
                    event_type=e.get("event_type", ""),
                )
            )


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
            # flexibility: routine=0.1, social=0.8, others=0.5
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
