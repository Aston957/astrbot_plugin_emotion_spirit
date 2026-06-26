"""PersonalityAgent -- axis 2: superego safety + personality drift + force dynamics.

PRE phase: SuperegoGuard safety assessment (caution/warning/critical).
POST phase: PersonalityDrift observation (emits drift events when intensity exceeds threshold).
"""

from __future__ import annotations

from typing import Any

from .base import CognitiveAgent, AgentIntent, PRE, POST, RULE, SKIP, LLM
from .event_bus import BoundaryBreached

__all__ = ["PersonalityAgent"]


class PersonalityAgent(CognitiveAgent):
    """Cognitive agent wrapping SuperegoGuard (PRE) and PersonalityDrift (POST)."""

    name = "personality"
    phases = (PRE, POST)

    def __init__(self, bus, superego_guard=None, personality_drift=None):
        super().__init__(bus)
        self._superego = superego_guard
        self._drift = personality_drift

    # ── perceive ──

    def perceive(self, surface: dict[str, Any]) -> dict[str, Any]:
        return {
            "phase": surface.get("_phase", POST),
            "safety_level": surface.get("safety_level", "normal"),
            "valence": surface.get("valence", 0.0),
            "arousal": surface.get("arousal", 0.0),
            "sentinel_result": surface.get("sentinel_result", {}),
            "current_personality": surface.get("current_personality"),
            "session_key": surface.get("session_key", ""),
        }

    # ── gate ──

    def gate(self, perceived: dict[str, Any]) -> str:
        if perceived.get("phase") == PRE:
            safety = perceived.get("safety_level", "normal")
            if safety == "normal":
                return SKIP
            if safety == "caution":
                return RULE
            # warning or critical → LLM budget candidate
            return LLM
        # POST: drift check -- only when emotional intensity is high
        intensity = max(
            abs(perceived.get("valence", 0)),
            perceived.get("arousal", 0),
        )
        return RULE if intensity >= 0.2 else SKIP

    # ── act ──

    async def act(self, session_key: str, mode: str,
                  perceived: dict[str, Any], phase: str = POST):
        if phase == PRE:
            return await self._act_superego(perceived)
        return await self._act_drift(perceived, session_key)

    async def _act_superego(self, perceived: dict[str, Any]) -> AgentIntent | None:
        """PRE phase: run SuperegoGuard assessment and produce safety intent."""
        safety = perceived.get("safety_level", "normal")

        # If superego_guard is available, run full assessment
        if self._superego:
            sentinel_result = perceived.get("sentinel_result", {})
            current_personality = perceived.get("current_personality")
            try:
                intervention = self._superego.assess(sentinel_result, current_personality)
                safety = intervention.level
            except Exception:
                pass  # fall through to surface safety_level

        flags = ["safe"] if safety == "normal" else ["hurt"]

        # Emit BoundaryBreached event for non-normal safety levels
        if safety in ("warning", "critical"):
            pressure_map = {"warning": 0.5, "critical": 0.9}
            self.emit(BoundaryBreached(
                source="personality",
                session_key=perceived.get("session_key", ""),
                pressure=pressure_map.get(safety, 0.5),
            ))

        return AgentIntent(
            source="personality",
            flags=flags,
            priority=0.6,
            payload={"safety_level": safety},
        )

    async def _act_drift(self, perceived: dict[str, Any],
                         session_key: str) -> AgentIntent | None:
        """POST phase: observe personality drift if drift detector is available."""
        if not self._drift:
            return None

        try:
            drifts = self._drift.check_drift()
        except Exception:
            return None

        if not drifts:
            return None

        return AgentIntent(
            source="personality",
            priority=0.3,
            payload={"drifts": drifts},
        )
