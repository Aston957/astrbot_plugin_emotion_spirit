"""SelfCore orchestrator: perceive -> gate -> act -> compose."""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from ..core.registry import register
from .base import SKIP, LLM, VALID_FLAGS, CognitiveAgent, AgentIntent
from .event_bus import EventBus

if TYPE_CHECKING:
    from ..memory.reflex_learner import ReflexLearnerStore

logger = logging.getLogger("emotion_spirit")

__all__ = ["SelfCore", "ComposedInputs"]


@dataclass(slots=True)
class ComposedInputs:
    """Fused output from all agents."""
    flags: list[str] = field(default_factory=list)
    confidence: float | None = None
    values: dict[str, float] = field(default_factory=dict)
    assessment: dict[str, float] = field(default_factory=dict)
    carried: dict[str, dict] = field(default_factory=dict)


@register(
    name="self_core",
    provides=["SelfCore"],
    depends_on=[],
)
class SelfCore:
    """Agent orchestrator (global singleton per session)."""

    def __init__(self, llm_budget: int = 2) -> None:
        self.bus = EventBus()
        self._agents: list[CognitiveAgent] = []
        self._llm_budget = llm_budget
        self._llm_priority = ["personality", "life", "memory", "relationship"]
        self._store: ReflexLearnerStore | None = None

    def set_store(self, store: ReflexLearnerStore) -> None:
        self._store = store

    def register(self, agent: CognitiveAgent) -> None:
        self._agents.append(agent)

    async def run_cycle(self, session_key: str, surface: dict[str, Any],
                        phase: str) -> ComposedInputs:
        """Run one cognitive cycle for a session at a given phase."""
        active = [a for a in self._agents if phase in a.phases]
        decisions: list[tuple[CognitiveAgent, str, dict]] = []

        for agent in active:
            try:
                perceived = agent.perceive(surface)
                if self._store:
                    perceived["_evo_delta"] = lambda key, an=agent.name: self._store.get_delta(an, key)
                else:
                    perceived["_evo_delta"] = lambda key: 0.0
                mode = agent.gate(perceived)
            except Exception:
                logger.warning("Agent %s perceive/gate failed", agent.name, exc_info=True)
                continue
            if mode != SKIP:
                decisions.append((agent, mode, perceived))

        decisions = self._apply_llm_budget(decisions)

        intents: list[AgentIntent] = []
        for agent, mode, perceived in decisions:
            try:
                intent = await agent.act(session_key, mode, perceived, phase=phase)
            except Exception:
                logger.warning("Agent %s act failed", agent.name, exc_info=True)
                continue
            if intent is not None:
                intents.append(intent)

        return self._compose(intents)

    def _apply_llm_budget(self, decisions):
        llm_ones = [d for d in decisions if d[1] == LLM]
        if len(llm_ones) <= self._llm_budget:
            return decisions
        rank = {name: i for i, name in enumerate(self._llm_priority)}
        llm_ones.sort(key=lambda d: rank.get(d[0].name, 999))
        keep = {id(d[0]) for d in llm_ones[:self._llm_budget]}
        return [(a, "rule" if m == LLM and id(a) not in keep else m, p)
                for a, m, p in decisions]

    def _compose(self, intents: list[AgentIntent]) -> ComposedInputs:
        flags: set[str] = set()
        conf_weighted, conf_w = 0.0, 0.0
        affect: dict[str, float] = {}
        group_heat: float | None = None
        carried: dict[str, dict] = {}

        for it in intents:
            flags |= {f for f in it.flags if f in VALID_FLAGS}
            if it.confidence_hint is not None:
                conf_weighted += it.confidence_hint * it.priority
                conf_w += it.priority
            for k, v in it.affect.items():
                affect[k] = affect.get(k, 0.0) + v * it.priority
            if it.group_heat is not None:
                group_heat = max(group_heat or 0.0, it.group_heat)
            if it.payload:
                carried[it.source] = it.payload

        return ComposedInputs(
            flags=sorted(flags),
            confidence=(conf_weighted / conf_w) if conf_w else None,
            values=dict(affect),
            assessment=dict(affect),
            carried=carried,
        )
