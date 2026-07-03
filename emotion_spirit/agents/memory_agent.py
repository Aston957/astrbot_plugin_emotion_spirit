"""MemoryAgent -- axis 1: MemoryPool recall + shadow detection."""

from __future__ import annotations

from typing import Any

from .base import CognitiveAgent, AgentIntent, PRE, POST, RULE, SKIP

__all__ = ["MemoryAgent"]


class MemoryAgent(CognitiveAgent):
    """Cognitive agent wrapping MemoryPool (recall on PRE, shadow on POST)."""

    name = "memory"
    phases = (PRE, POST)

    def __init__(self, memory_pool, shadow_detector=None):
        super().__init__()
        self._pool = memory_pool
        self._shadow = shadow_detector

    # ── perceive ──

    def perceive(self, surface: dict[str, Any]) -> dict[str, Any]:
        return {
            "phase": surface.get("_phase", POST),
            "intimacy_gravity": surface.get("intimacy_gravity", 0.5),
            "user_text": surface.get("user_text", ""),
            "echo_count": surface.get("echo_count", 0),
            "_evo_delta": surface.get("_evo_delta", lambda k: 0.0),
        }

    # ── gate ──

    def gate(self, perceived: dict[str, Any]) -> str:
        if perceived.get("phase") == PRE:
            intim = perceived.get("intimacy_gravity", 0.5)
            evo_fn = perceived.get("_evo_delta", lambda k: 0.0)
            thr = 0.35 + evo_fn("intimacy_recall_threshold")
            return RULE if intim >= thr else SKIP
        # POST: always run shadow detection / decay observation
        return RULE

    # ── act ──

    async def act(self, session_key: str, mode: str,
                  perceived: dict[str, Any], phase: str = POST):
        if phase == PRE:
            return await self._act_recall(perceived, session_key)
        return await self._act_post(perceived, session_key)

    async def _act_recall(self, perceived: dict[str, Any], session_key: str):
        """PRE phase: recall top memories related to user text."""
        text = perceived.get("user_text", "")
        if not text:
            return None
        results = self._pool.recall(text, max_results=3)
        if results:
            return AgentIntent(
                source="memory",
                payload={"recalled_memories": [r.text for r in results]},
                priority=0.4,
            )
        return None

    async def _act_post(self, perceived: dict[str, Any], session_key: str):
        """POST phase: shadow detection (if available)."""
        if self._shadow:
            try:
                shadows = self._shadow.detect()
                if shadows:
                    # emit removed (v1.2.7 Q3: EventBus deleted)
                    pass
            except Exception:
                pass
        # Decay is handled by MemoryPool.tick() in main loop, not here
        return None
