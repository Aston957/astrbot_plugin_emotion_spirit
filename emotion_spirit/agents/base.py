"""CognitiveAgent base class + AgentIntent + phase/flag constants."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .event_bus import EventBus, AgentEvent

__all__ = [
    "SKIP", "RULE", "LLM", "PRE", "POST", "RESPONSE_POST", "AUTONOMOUS",
    "VALID_FLAGS", "CognitiveAgent", "AgentIntent",
]

SKIP = "skip"
RULE = "rule"
LLM = "llm"
PRE = "pre"
POST = "post"
RESPONSE_POST = "response_post"
AUTONOMOUS = "autonomous"

VALID_FLAGS = frozenset({
    "safe", "hurt", "boundary", "repair", "idle",
    "pause", "resume", "reset", "proactive", "tool",
    "task", "group", "fallibility", "interrupt",
})


class CognitiveAgent:
    """Cognitive worker base class: perceive -> gate -> act."""

    name: str = "base"
    phases: tuple[str, ...] = (POST,)

    def __init__(self, bus: "EventBus") -> None:
        self._bus = bus

    def perceive(self, surface: dict[str, Any]) -> dict[str, Any]:
        return {}

    def gate(self, perceived: dict[str, Any]) -> str:
        return SKIP

    async def act(self, session_key: str, mode: str,
                  perceived: dict[str, Any], phase: str = POST) -> "AgentIntent | None":
        return None

    def emit(self, event: "AgentEvent") -> None:
        self._bus.publish(event)


@dataclass(slots=True)
class AgentIntent:
    """Worker's intent contribution to SelfCore."""
    source: str
    flags: list[str] = field(default_factory=list)
    confidence_hint: float | None = None
    affect: dict[str, float] = field(default_factory=dict)
    group_heat: float | None = None
    priority: float = 0.5
    payload: dict[str, Any] = field(default_factory=dict)
