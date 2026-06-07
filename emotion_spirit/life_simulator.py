"""Life Simulator — Mode A (对话驱动) / Mode B (自主保底) 双模式。

Mode A: 用户消息后 60s idle 或满 15 轮
Mode B: 2-4h 无对话, 系统状态允许时触发
"""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

from .config import LIFE_SIM_CONFIG
from .surface_consumer import SemanticSignals

if TYPE_CHECKING:
    from .memory_pool import MemoryPool, BufferEntry
    from .intimacy import IntimacyTracker
    from .buffer_signals import BufferSignals
    from .meaning_reservoir import MeaningReservoir
    from .surface_consumer import SurfaceConsumer

from .emotion_classifier import build_emotion_payload  # v1.1.2: 共享层


from .registry import register


@register(name="life_simulator", provides=["LifeSimulator"], depends_on=["memory_pool"])
class LifeSimulator:
    """双模式 Life Sim。"""

    def __init__(
        self,
        consumer: SurfaceConsumer,
        pool: MemoryPool,
        intimacy: IntimacyTracker,
        signals: BufferSignals,
        reservoir: MeaningReservoir,
    ) -> None:
        self._consumer = consumer
        self._pool = pool
        self._intimacy = intimacy
        self._signals = signals
        self._reservoir = reservoir
        self._last_mode_b: float = 0.0
        self._mode_b_cooldown: float = 0.0
        self._turn_count: int = 0
        self._last_interaction: float = time.time()

    def on_user_message(self) -> None:
        """用户消息到达时调用。重置 Mode B 计时。"""
        self._turn_count += 1
        self._last_interaction = time.time()
        self._mode_b_cooldown = LIFE_SIM_CONFIG["mode_b_cooldown_after_trigger_minutes"] * 60

    def check_mode_a(self, signals: SemanticSignals) -> dict[str, Any] | None:
        """检查 Mode A 触发条件。返回事件或 None。"""
        idle_seconds = time.time() - self._last_interaction
        max_turns = int(LIFE_SIM_CONFIG["mode_a_max_turns"])

        if idle_seconds >= LIFE_SIM_CONFIG["mode_a_idle_seconds"] or self._turn_count >= max_turns:
            self._turn_count = 0
            recent = self._pool.sample_for_mode_a(minutes=5)
            if recent:
                return {
                    "type": "mode_a",
                    "trigger": "idle" if idle_seconds >= LIFE_SIM_CONFIG["mode_a_idle_seconds"] else "turn_limit",
                    "entries": [e.text for e in recent[-3:]],
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

    def check_mode_b(self, signals: SemanticSignals, persona: str = "default") -> dict[str, Any] | None:
        """检查 Mode B 触发条件。返回事件或 None。"""
        now = time.time()

        # 冷却期
        if now - self._last_mode_b < self._mode_b_cooldown:
            return None

        # 间隔检查
        min_interval = self._mode_b_interval(persona, self._interaction_density())
        if now - self._last_interaction < min_interval:
            return None

        # 状态条件
        if not self._can_mode_b_trigger(signals):
            return None

        self._last_mode_b = now
        self._mode_b_cooldown = LIFE_SIM_CONFIG["mode_b_cooldown_after_trigger_minutes"] * 60

        entries = self._pool.sample_for_mode_b(k=3)
        reservoir_level = self._reservoir.level
        phi = signals.phi_smoothed

        # v1.1.2: 从共享 emotion_classifier.build_emotion_payload 获取
        emotion_payload = build_emotion_payload(signals)

        if entries and reservoir_level > 0.3:
            return self._generate_life_event(
                entries, phi, self._signals.mode_b_strategy(), emotion_payload
            )
        elif entries:
            return self._generate_reflection(entries, phi, emotion_payload)
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

    def _mode_b_interval(self, persona: str, density: float) -> float:
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
        entries: list[BufferEntry],
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
            "entries": [e.text for e in entries],
            "phi": phi,
            "reservoir_used": 0.1,
        }
        if emotion_payload is not None:
            result["emotion"] = emotion_payload  # v1.1.1
        return result

    def _generate_reflection(
        self,
        entries: list[BufferEntry],
        phi: float,
        emotion_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """反思性独白。"""
        result: dict[str, Any] = {
            "type": "mode_b",
            "subtype": "reflection",
            "entries": [e.text for e in entries],
            "phi": phi,
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
            "entries": [],
            "phi": phi,
        }
        if emotion_payload is not None:
            result["emotion"] = emotion_payload  # v1.1.1
        return result

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
