"""RelationshipAgent -- axis 3: intimacy + social graph + topic privacy.

PRE phase: Retrieve intimacy context for the user (segment + tone).
POST phase: Emit RelationshipChanged events when intimacy shifts.
"""

from __future__ import annotations

from typing import Any

from .base import CognitiveAgent, AgentIntent, PRE, POST, RULE, SKIP

__all__ = ["RelationshipAgent"]


class RelationshipAgent(CognitiveAgent):
    """Cognitive agent wrapping IntimacyTracker and SocialGraph."""

    name = "relationship"
    phases = (PRE, POST)

    def __init__(self, intimacy_tracker=None, social_graph=None):
        super().__init__()
        self._intimacy = intimacy_tracker
        self._social_graph = social_graph

    # ── perceive ──

    def perceive(self, surface: dict[str, Any]) -> dict[str, Any]:
        return {
            "phase": surface.get("_phase", POST),
            "has_interaction": surface.get("has_interaction", False),
            "user_id": surface.get("user_id", ""),
            "persona": surface.get("persona", ""),
            "intimacy_delta": surface.get("intimacy_delta", 0.0),
            "session_key": surface.get("session_key", ""),
        }

    # ── gate ──

    def gate(self, perceived: dict[str, Any]) -> str:
        if perceived.get("phase") == PRE:
            # PRE: only gate in if we have a user_id and intimacy tracker
            if perceived.get("user_id") and self._intimacy:
                return RULE
            return SKIP
        # POST: only gate in if there was an interaction with delta
        if perceived.get("has_interaction") and perceived.get("intimacy_delta", 0.0) != 0.0:
            return RULE
        return SKIP

    # ── act ──

    async def act(self, session_key: str, mode: str,
                  perceived: dict[str, Any], phase: str = POST):
        if phase == PRE:
            return await self._act_context(perceived)
        return await self._act_update(perceived, session_key)

    async def _act_context(self, perceived: dict[str, Any]) -> AgentIntent | None:
        """PRE phase: retrieve intimacy context (segment + tone) for prompt injection."""
        user_id = perceived.get("user_id", "")
        persona = perceived.get("persona", "")
        if not user_id or not self._intimacy:
            return None

        try:
            intimacy_score = self._intimacy.get_intimacy(user_id, persona)
            segment = self._intimacy.get_segment(user_id)
            tone = self._intimacy.get_relationship_tone(user_id)
        except Exception:
            return None

        return AgentIntent(
            source="relationship",
            priority=0.5,
            payload={
                "intimacy_score": round(intimacy_score, 4),
                "segment": segment,
                "tone": tone,
            },
        )

    async def _act_update(self, perceived: dict[str, Any],
                          session_key: str) -> AgentIntent | None:
        """POST phase: emit RelationshipChanged event when intimacy shifts."""
        user_id = perceived.get("user_id", "")
        delta = perceived.get("intimacy_delta", 0.0)
        persona = perceived.get("persona", "")

        if not user_id or not self._intimacy or delta == 0.0:
            return None

        try:
            old_segment = self._intimacy.get_segment(user_id)
            self._intimacy.update(user_id, vulnerability_delta=delta)
            new_segment = self._intimacy.get_segment(user_id)
        except Exception:
            return None

        # Emit event if segment changed
        if old_segment != new_segment:
            # emit removed (v1.2.7 Q3: EventBus deleted)
            pass

        return AgentIntent(
            source="relationship",
            priority=0.4,
            payload={
                "intimacy_delta": delta,
                "old_segment": old_segment,
                "new_segment": new_segment,
            },
        )
