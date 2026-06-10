"""UnifiedMemory -- the unified memory system.

Central orchestrator: owns all entries (UnifiedEntry), manages 4-layer
tier transitions (buffer/warm/cold/ghost), dual-axis decay (DecayModel),
cascade propagation (CascadeEngine), and body-state feedback.

Architecture: entries are event entities; the pool is the emotion entity.

Reference: docs/UNIFIED_MEMORY_LIFESIM_DESIGN_2026-06-10.md section 3
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from ..core.registry import register
from .decay_model import DecayModel
from .unified_entry import UnifiedEntry
from .cascade_engine import CascadeEngine

__all__ = ["UnifiedMemory"]

# -- Capacity limits --
BUFFER_MAX = 30
WARM_MAX = 100
COLD_MAX = 500
GHOST_MAX = 50

# -- Layer transition thresholds --
BUFFER_TO_WARM_TEMP = 0.5
BUFFER_MAX_AGE_HOURS = 48
WARM_TO_COLD_TEMP = 0.2
WARM_TTL_HOURS = 72
COLD_WEIGHT_THRESHOLD = 0.05
NOISE_THRESHOLD = 0.05

# -- Ghost formation --
GHOST_TEMP_THRESHOLD = 0.9
GHOST_WEIGHT_THRESHOLD = 0.8
GHOST_TICKS_REQUIRED = 10

# -- Decay --
DECAY_INTERVAL_SECONDS = 300  # 5 minutes


@register(name="unified_memory", provides=["UnifiedMemory"], depends_on=[])
class UnifiedMemory:
    """Unified memory system -- the main orchestrator.

    Manages a flat dict of UnifiedEntry objects with 4-layer tier
    management, dual-axis decay, cascade propagation, and body-state
    feedback.
    """

    def __init__(self) -> None:
        self._entries: dict[str, UnifiedEntry] = {}
        self._tag_index: dict[str, set[str]] = {}
        self._entity_index: dict[str, set[str]] = {}
        self._decay = DecayModel()
        self._cascade_engine = CascadeEngine()
        self._next_id: int = 0
        self._cascade_active: bool = False
        self._last_tick: float = time.time()

    # ═══ Entry Management ═══

    def add(
        self,
        text: str,
        tags: list[str],
        entities: dict,
        source_user: str,
        arousal: float,
        raw_weight: float,
        privacy: str = "private",
    ) -> UnifiedEntry:
        """Create a new entry and add it to the buffer tier.

        Initial temperature = 0.5*arousal + 0.3*weight + 0.2*novelty.

        Args:
            text: The memory text content.
            tags: List of semantic tags.
            entities: Entity dict, e.g. {"person": ["bob"]}.
            source_user: The user who created this memory.
            arousal: Arousal level [0, 1].
            raw_weight: Raw emotional weight [0, 1].
            privacy: Privacy level ("private"/"circle"/"public").

        Returns:
            The created UnifiedEntry.
        """
        entry_id = f"unified_{self._next_id}"
        self._next_id += 1

        novelty = self._compute_novelty(text)
        temperature = 0.5 * arousal + 0.3 * raw_weight + 0.2 * novelty
        temperature = DecayModel.clamp(temperature, 0.0, 1.0)

        # Emotional mass: higher weight = more mass = slower cooling
        mass = raw_weight

        entry = UnifiedEntry(
            id=entry_id,
            text=text,
            tags=list(tags),
            entities=dict(entities),
            source_user=source_user,
            privacy=privacy,
            created_at=time.time(),
            temperature=temperature,
            emotional_weight=raw_weight,
            mass=mass,
            tier="buffer",
            is_ghost=False,
            recall_count=0,
            last_recalled=0.0,
            peak_temperature=temperature,
        )

        self._entries[entry_id] = entry
        self._index_entry(entry)
        return entry

    def get_layer(self, tier: str) -> list[UnifiedEntry]:
        """Return entries in the specified tier.

        Args:
            tier: One of "buffer", "warm", "cold", "ghost".

        Returns:
            List of entries in that tier.
        """
        return [e for e in self._entries.values() if e.tier == tier]

    def mean_temperature(self) -> float:
        """Return average temperature across all entries."""
        if not self._entries:
            return 0.0
        return sum(e.temperature for e in self._entries.values()) / len(self._entries)

    def count_hot(self, threshold: float) -> int:
        """Return count of entries with temperature above threshold."""
        return sum(1 for e in self._entries.values() if e.temperature > threshold)

    # ═══ Tick / Decay ═══

    def tick(self) -> None:
        """Advance one tick: apply decay, check transitions, ghost formation.

        Should be called periodically (e.g. every 5 minutes).
        """
        now = time.time()
        elapsed = now - self._last_tick

        # Apply dual-axis decay to all entries
        for entry in self._entries.values():
            if entry.is_ghost:
                continue
            elapsed_hours = elapsed / 3600.0

            # Thermal decay (exponential)
            entry.temperature = self._decay.thermal_decay(
                elapsed_seconds=elapsed,
                initial_temp=entry.temperature,
                mass=entry.mass,
                is_ghost=entry.is_ghost,
            )

            # Memory decay (power law) -- only for non-ghost entries
            # Use time since creation for retention calculation
            age_hours = (now - entry.created_at) / 3600.0
            entry.emotional_weight = self._decay.memory_retention(
                elapsed_hours=age_hours,
                initial_weight=entry.emotional_weight,
            )

        # Check tier transitions
        self._check_transitions()

        # Check ghost formation
        self._check_ghost_formation()

        # Check cascade state
        self._update_cascade_state()

        self._last_tick = now

    # ═══ Layer Transitions ═══

    def _check_transitions(self) -> None:
        """Check and execute layer transitions for all entries."""
        now = time.time()

        for entry in list(self._entries.values()):
            if entry.tier == "buffer":
                self._check_buffer_to_warm(entry, now)
            elif entry.tier == "warm":
                self._check_warm_to_cold(entry, now)
            elif entry.tier == "cold":
                self._check_cold_evict(entry)

    def _check_buffer_to_warm(self, entry: UnifiedEntry, now: float) -> None:
        """Promote buffer entry to warm if conditions met.

        Conditions: temperature < 0.5, weight > noise, age < 48h.
        """
        age_hours = (now - entry.created_at) / 3600.0
        if (
            entry.temperature < BUFFER_TO_WARM_TEMP
            and entry.emotional_weight > NOISE_THRESHOLD
            and age_hours < BUFFER_MAX_AGE_HOURS
        ):
            self._move_to_tier(entry, "warm")

        # Evict stale buffer entries
        if age_hours >= BUFFER_MAX_AGE_HOURS:
            self._remove_entry(entry)

    def _check_warm_to_cold(self, entry: UnifiedEntry, now: float) -> None:
        """Demote warm entry to cold if conditions met.

        Conditions: (temp < 0.2 and weight < 0.2) OR age > 72h.
        """
        age_hours = (now - entry.created_at) / 3600.0
        if (
            (entry.temperature < WARM_TO_COLD_TEMP and entry.emotional_weight < 0.2)
            or age_hours > WARM_TTL_HOURS
        ):
            self._move_to_tier(entry, "cold")

    def _check_cold_evict(self, entry: UnifiedEntry) -> None:
        """Evict cold entry if weight too low or capacity exceeded."""
        if entry.emotional_weight < COLD_WEIGHT_THRESHOLD:
            self._remove_entry(entry)
            return

        cold_entries = self.get_layer("cold")
        if len(cold_entries) > COLD_MAX:
            # Evict lowest weight entries
            cold_entries.sort(key=lambda e: e.emotional_weight)
            for victim in cold_entries[: len(cold_entries) - COLD_MAX]:
                self._remove_entry(victim)

    def _move_to_tier(self, entry: UnifiedEntry, new_tier: str) -> None:
        """Move entry to a new tier."""
        entry.tier = new_tier

        # Enforce capacity limits on warm and ghost tiers
        if new_tier == "warm":
            warm_entries = self.get_layer("warm")
            if len(warm_entries) > WARM_MAX:
                warm_entries.sort(key=lambda e: e.emotional_weight)
                for victim in warm_entries[: len(warm_entries) - WARM_MAX]:
                    self._move_to_tier(victim, "cold")
        elif new_tier == "ghost":
            ghost_entries = self.get_layer("ghost")
            if len(ghost_entries) > GHOST_MAX:
                ghost_entries.sort(key=lambda e: e.emotional_weight)
                for victim in ghost_entries[: len(ghost_entries) - GHOST_MAX]:
                    self._remove_entry(victim)

    # ═══ Ghost Formation ═══

    def _check_ghost_formation(self) -> None:
        """Check for ghost formation: sustained high temp + high weight."""
        for entry in self._entries.values():
            if entry.is_ghost:
                continue

            if (
                entry.temperature > GHOST_TEMP_THRESHOLD
                and entry.emotional_weight > GHOST_WEIGHT_THRESHOLD
            ):
                entry._ticks_above_ghost_threshold += 1
            else:
                entry._ticks_above_ghost_threshold = 0

            if entry._ticks_above_ghost_threshold >= GHOST_TICKS_REQUIRED:
                self._form_ghost(entry)

    def _form_ghost(self, entry: UnifiedEntry) -> None:
        """Convert entry to ghost tier."""
        entry.is_ghost = True
        entry.tier = "ghost"
        entry._ticks_above_ghost_threshold = 0

        # Enforce ghost capacity
        ghost_entries = self.get_layer("ghost")
        if len(ghost_entries) > GHOST_MAX:
            ghost_entries.sort(key=lambda e: e.emotional_weight)
            for victim in ghost_entries[: len(ghost_entries) - GHOST_MAX]:
                self._remove_entry(victim)

    # ═══ External Interaction ═══

    def inject_signal(self, entry_id: str, signal_type: str, intensity: float) -> None:
        """Inject a signal into a specific entry.

        Args:
            entry_id: The entry to inject into.
            signal_type: Type of signal (contradiction, reinforcement, etc.).
            intensity: Signal intensity [0, 1].
        """
        entry = self._entries.get(entry_id)
        if entry is not None:
            entry.on_inject(signal_type, intensity)

    def recall_entry(self, entry_id: str, personality: dict[str, float]) -> None:
        """Recall an entry: raise temperature, open reconsolidation window.

        Args:
            entry_id: The entry to recall.
            personality: Personality dimensions for window calculation.
        """
        entry = self._entries.get(entry_id)
        if entry is not None:
            entry.on_recall(personality)

    def feed_body(self, body_state: dict[str, float]) -> None:
        """Feed body state feedback into the memory system.

        Adjusts temperatures based on aggregate body state.
        """
        if not self._entries:
            return
        mean_temp = self.mean_temperature()
        # Body state can modulate overall memory temperature
        arousal = body_state.get("arousal", 0.5)
        shift = (arousal - 0.5) * 0.1
        for entry in self._entries.values():
            entry.temperature = DecayModel.clamp(entry.temperature + shift, 0.0, 1.0)

    # ═══ Cascade ═══

    def cascade_active(self) -> bool:
        """Return True if a cascade is currently in progress."""
        return self._cascade_active

    def _update_cascade_state(self) -> None:
        """Update cascade state and propagate if active."""
        hot_entries = [e for e in self._entries.values() if e.temperature > GHOST_TEMP_THRESHOLD]

        if hot_entries and not self._cascade_active:
            self._cascade_active = True
            # Trigger cascade from hottest entry
            hot_entries.sort(key=lambda e: e.temperature, reverse=True)
            source = hot_entries[0]
            self._cascade_engine.propagate_cascade(
                source=source,
                sensitivity=0.5,
                entries_lookup=self._entries,
            )
        elif not hot_entries:
            self._cascade_active = False

    # ═══ Indexes ═══

    def _index_entry(self, entry: UnifiedEntry) -> None:
        """Add entry to tag and entity indexes."""
        for tag in entry.tags:
            self._tag_index.setdefault(tag, set()).add(entry.id)
        for entity_type, entity_list in entry.entities.items():
            for entity in entity_list:
                key = f"{entity_type}:{entity}"
                self._entity_index.setdefault(key, set()).add(entry.id)

        # Also index in cascade engine
        self._cascade_engine.index_entry(entry)

    def _remove_entry(self, entry: UnifiedEntry) -> None:
        """Remove entry from all structures."""
        self._entries.pop(entry.id, None)

        # Remove from tag index
        for tag in entry.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(entry.id)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]

        # Remove from entity index
        for entity_type, entity_list in entry.entities.items():
            for entity in entity_list:
                key = f"{entity_type}:{entity}"
                if key in self._entity_index:
                    self._entity_index[key].discard(entry.id)
                    if not self._entity_index[key]:
                        del self._entity_index[key]

        # Remove from cascade engine
        self._cascade_engine.remove_entry(entry)

    # ═══ Novelty ═══

    def _compute_novelty(self, text: str) -> float:
        """Compute novelty score for new text against recent entries.

        Uses Jaccard distance on whitespace-split words.
        Returns 0.0 when no existing entries to compare (first entry).
        """
        if not self._entries:
            return 0.0

        recent = sorted(
            self._entries.values(), key=lambda e: e.created_at, reverse=True
        )[:10]

        words = set(text.split())
        if not words:
            return 0.3

        max_overlap = 0.0
        for r in recent:
            r_words = set(r.text.split())
            if r_words:
                overlap = len(words & r_words) / len(words | r_words)
                max_overlap = max(max_overlap, overlap)

        return 1.0 - max_overlap

    # ═══ Serialization ═══

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for persistence."""
        return {
            "entries": {eid: e.to_dict() for eid, e in self._entries.items()},
            "next_id": self._next_id,
            "cascade_active": self._cascade_active,
            "last_tick": self._last_tick,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnifiedMemory:
        """Deserialize from dict."""
        mem = cls()
        mem._next_id = data.get("next_id", 0)
        mem._cascade_active = data.get("cascade_active", False)
        mem._last_tick = data.get("last_tick", time.time())

        for eid, entry_data in data.get("entries", {}).items():
            entry = UnifiedEntry.from_dict(entry_data)
            mem._entries[eid] = entry
            mem._index_entry(entry)

        return mem
