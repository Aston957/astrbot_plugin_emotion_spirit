"""LifeAgent -- axis 4: LifeSimulator v2 + dream system (T2).

PRE phase: adapt_plan -- adjust daily schedule based on emotional state.
AUTONOMOUS phase: consume pending LifeEvents and emit LifeEventReady.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .base import CognitiveAgent, AgentIntent, PRE, AUTONOMOUS, RULE, SKIP
from .event_bus import LifeEventReady

if TYPE_CHECKING:
    from ..regulation.life_simulator import LifeSimulatorV2

__all__ = ["LifeAgent"]


class LifeAgent(CognitiveAgent):
    """Cognitive agent wrapping LifeSimulatorV2."""

    name = "life"
    phases = (PRE, AUTONOMOUS)

    def __init__(self, bus, life_sim_v2: "LifeSimulatorV2 | None" = None):
        super().__init__(bus)
        self._life_sim = life_sim_v2

    # ── perceive ──

    def perceive(self, surface: dict[str, Any]) -> dict[str, Any]:
        return {
            "phase": surface.get("_phase", PRE),
            "emotion_delta": surface.get("emotion_delta", 0.0),
            "cascade_active": surface.get("cascade_active", False),
            "boundary_pressure": surface.get("boundary_pressure", 0.0),
            "_evo_delta": surface.get("_evo_delta", lambda k: 0.0),
        }

    # ── gate ──

    def gate(self, perceived: dict[str, Any]) -> str:
        if perceived.get("phase") == PRE:
            delta = abs(perceived.get("emotion_delta", 0.0))
            evo_fn = perceived.get("_evo_delta", lambda k: 0.0)
            thr = 0.3 + evo_fn("life_sim_adapt_threshold")
            return RULE if delta >= thr else SKIP
        # AUTONOMOUS: always eligible
        return RULE

    # ── act ──

    async def act(self, session_key: str, mode: str,
                  perceived: dict[str, Any], phase: str = AUTONOMOUS):
        if not self._life_sim:
            return None

        if phase == PRE:
            return await self._act_adapt(perceived)
        return await self._act_autonomous(session_key)

    async def _act_adapt(self, perceived: dict[str, Any]) -> "AgentIntent | None":
        """PRE phase: call adapt_plan on LifeSimulatorV2."""
        try:
            adaptations = self._life_sim.adapt_plan(
                emotion_delta=perceived.get("emotion_delta", 0.0),
                cascade_active=perceived.get("cascade_active", False),
                boundary_pressure=perceived.get("boundary_pressure", 0.0),
            )
        except Exception:
            return None

        if adaptations:
            return AgentIntent(
                source="life",
                payload={"plan_adaptations": adaptations},
                priority=0.3,
            )
        return None

    async def _act_autonomous(self, session_key: str) -> "AgentIntent | None":
        """AUTONOMOUS phase: consume pending LifeEvent and emit LifeEventReady."""
        try:
            event = self._life_sim.consume_life_event()
        except Exception:
            return None

        if event is None:
            return None

        self.emit(LifeEventReady(
            source="life",
            session_key=session_key,
            text=event.text,
            mood=event.mood,
        ))

        return AgentIntent(
            source="life",
            payload={
                "life_event": {
                    "text": event.text,
                    "mood": event.mood,
                    "urgency": event.urgency,
                    "event_type": event.event_type,
                    "wants_to_share": event.wants_to_share,
                },
            },
            priority=0.3,
        )
