"""DreamGenerator -- deep sleep (LLM) + sleep deprivation (template).

v3.1: Dream system with personality-driven round computation,
      LLM-based deep sleep dreams, template-based sleep deprivation dreams,
      and persistence via to_dict/from_dict.

Reference: docs/DREAM_GENERATOR_DESIGN.md
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, TYPE_CHECKING

from ..core.config import DREAM_CONFIG

if TYPE_CHECKING:
    from ..memory.memory_pool import MemoryPool
    from ..memory.memory_sampler import MemorySampler

__all__ = ["DreamGenerator"]


class DreamGenerator:
    """Dream system: deep sleep (LLM) + sleep deprivation (template).

    Deep sleep dreams use LLM to generate narrative from sampled memories
    and recent events.  Sleep deprivation dreams use templates (zero LLM).
    Dream rounds are computed from sleep hours + personality dimensions.
    """

    def __init__(self, memory_pool: "MemoryPool", sampler: "MemorySampler") -> None:
        self._pool = memory_pool
        self._sampler = sampler
        self._llm: Callable[[str, str], Awaitable[str]] | None = None
        self._last_dream_time: float = 0.0

    def configure(self, llm_caller: Callable[[str, str], Awaitable[str]] | None) -> None:
        """Register LLM callable for deep sleep dream generation."""
        self._llm = llm_caller

    # ── dream round computation ──────────────────────────────────────

    def compute_dream_rounds(self, sleep_hours: float, personality: dict[str, float]) -> int:
        """Compute dream rounds based on sleep duration + personality.

        Formula:
          base = max(1, sleep_hours // 3)
          +1 if openness > 0.7
          -1 if conscientiousness > 0.7
          clamped to [1, 5]
        """
        base = max(1, int(sleep_hours // 3))
        if personality.get("openness", 0.5) > 0.7:
            base += 1
        if personality.get("conscientiousness", 0.5) > 0.7:
            base -= 1
        return max(1, min(5, base))

    def _personality_tone(self, personality: dict[str, float]) -> str:
        """Derive dream tone keywords from personality dimensions."""
        tones: list[str] = []
        if personality.get("neuroticism", 0.5) > 0.7:
            tones.append("焦虑")
        if personality.get("openness", 0.5) > 0.7:
            tones.append("奇幻")
        if personality.get("conscientiousness", 0.5) > 0.7:
            tones.append("规律")
        if personality.get("extraversion", 0.5) > 0.7:
            tones.append("社交场景")
        if personality.get("agreeableness", 0.5) > 0.7:
            tones.append("温暖")
        return "、".join(tones) if tones else "平静"

    # ── sleep deprivation probability ────────────────────────────────

    def compute_sleep_deprivation_chance(
        self,
        personality: dict[str, float],
        temperature: float = 0.5,
        cascade_active: bool = False,
    ) -> float:
        """Sleep deprivation dream probability.

        Base 0.1, multiplied by:
          x2.0 if temperature > 0.7
          x1.5 if cascade_active
          x1.5 if neuroticism > 0.7
          x0.8 if conscientiousness > 0.7
        Capped at 1.0.
        """
        p = DREAM_CONFIG.get("sleep_deprivation_base_chance", 0.1)
        if temperature > 0.7:
            p *= 2.0
        if cascade_active:
            p *= 1.5
        if personality.get("neuroticism", 0.5) > 0.7:
            p *= 1.5
        if personality.get("conscientiousness", 0.5) > 0.7:
            p *= 0.8
        return min(1.0, p)

    # ── deep sleep dream (LLM) ──────────────────────────────────────

    async def generate_deep_sleep_dream(
        self,
        personality: dict[str, float],
        dream_seed: str = "",
        recent_events: list[str] | None = None,
    ) -> str | None:
        """Generate a deep sleep dream via LLM.

        Returns None if no LLM is configured or LLM call fails.
        """
        if not self._llm:
            return None
        samples = self._sampler.sample(personality, k=3)
        memories = "\n".join(f"- {s.entry.text}" for s in samples) or "（暂无）"
        events = "\n".join(f"- {e}" for e in (recent_events or [])[:3]) or "（暂无）"
        tone = self._personality_tone(personality)

        seed_line = f"梦境主题: {dream_seed}\n" if dream_seed else ""
        prompt = (
            f"你正在做梦。以下是你最近的记忆和今天发生的事:\n"
            f"记忆:\n{memories}\n"
            f"今天的事:\n{events}\n"
            f"{seed_line}"
            f"你的人格基调: {tone}\n"
            f"请写一段 5-8 句的梦境叙事。不要提及你是 AI。"
        )

        try:
            self._last_dream_time = time.time()
            return await self._llm("你是梦境生成器。", prompt)
        except Exception:
            return None

    # ── sleep deprivation dream (template) ───────────────────────────

    def generate_sleep_deprivation_dream(self, personality: dict[str, float]) -> str:
        """Generate a sleep deprivation dream (template, zero LLM)."""
        samples = self._sampler.sample(personality, k=1)
        if samples:
            return f"碎片梦境: {samples[0].entry.text[:50]}..."
        return "碎片梦境: 无法入睡，脑海中闪过模糊的画面"

    # ── persistence ──────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize state for persistence."""
        return {"last_dream_time": self._last_dream_time}

    def from_dict(self, data: dict[str, Any]) -> None:
        """Restore state from persisted dict."""
        self._last_dream_time = data.get("last_dream_time", 0.0)
