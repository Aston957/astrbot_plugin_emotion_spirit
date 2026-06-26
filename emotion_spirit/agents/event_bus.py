"""Typed event bus for inter-agent communication (fire-forget)."""

from __future__ import annotations
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger("emotion_spirit")

__all__ = ["AgentEvent", "EventBus", "BoundaryBreached", "ShadowDetected",
           "LifeEventReady", "RelationshipChanged"]


@dataclass(slots=True)
class AgentEvent:
    source: str
    session_key: str


@dataclass(slots=True)
class BoundaryBreached(AgentEvent):
    pressure: float = 0.0


@dataclass(slots=True)
class ShadowDetected(AgentEvent):
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LifeEventReady(AgentEvent):
    text: str = ""
    mood: str = ""


@dataclass(slots=True)
class RelationshipChanged(AgentEvent):
    user_id: str = ""
    segment: str = ""
    delta: float = 0.0


Handler = Callable[[AgentEvent], None]


class EventBus:
    """Synchronous fire-and-forget publish-subscribe."""

    def __init__(self) -> None:
        self._subs: dict[type, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Handler) -> None:
        self._subs[event_type].append(handler)

    def publish(self, event: AgentEvent) -> None:
        for handler in self._subs.get(type(event), ()):
            try:
                handler(event)
            except Exception:
                logger.warning("EventBus handler error on %s", type(event).__name__, exc_info=True)

    def clear(self) -> None:
        self._subs.clear()
