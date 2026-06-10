"""CascadeEngine — inverted index + mixed relevance cascade propagation.

Uses tag and entity inverted indexes for O(n*k) cascade instead of O(n²).
Mixed relevance: 0.4*tag + 0.3*entity + 0.3*text keyword overlap.

Reference: docs/UNIFIED_MEMORY_LIFESIM_DESIGN_2026-06-10.md §3.4
"""

from __future__ import annotations

from .unified_entry import UnifiedEntry

__all__ = ["CascadeEngine"]


class CascadeEngine:
    """Cascade propagation engine with inverted indexes."""

    RELEVANCE_THRESHOLD: float = 0.2
    TAG_WEIGHT: float = 0.4
    ENTITY_WEIGHT: float = 0.3
    TEXT_WEIGHT: float = 0.3

    def __init__(self) -> None:
        self._tag_index: dict[str, set[str]] = {}     # tag → {entry_ids}
        self._entity_index: dict[str, set[str]] = {}  # "type:value" → {entry_ids}

    def index_entry(self, entry: UnifiedEntry) -> None:
        """Add entry to inverted indexes."""
        for tag in entry.tags:
            self._tag_index.setdefault(tag, set()).add(entry.id)
        for entity_type, entity_list in entry.entities.items():
            for entity in entity_list:
                key = f"{entity_type}:{entity}"
                self._entity_index.setdefault(key, set()).add(entry.id)

    def remove_entry(self, entry: UnifiedEntry) -> None:
        """Remove entry from inverted indexes."""
        for tag in entry.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(entry.id)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]
        for entity_type, entity_list in entry.entities.items():
            for entity in entity_list:
                key = f"{entity_type}:{entity}"
                if key in self._entity_index:
                    self._entity_index[key].discard(entry.id)
                    if not self._entity_index[key]:
                        del self._entity_index[key]

    def find_related(self, source: UnifiedEntry) -> list[str]:
        """Find related entry IDs via inverted index (fast path)."""
        candidates: set[str] = set()
        for tag in source.tags:
            candidates.update(self._tag_index.get(tag, set()))
        for entity_type, entity_list in source.entities.items():
            for entity in entity_list:
                key = f"{entity_type}:{entity}"
                candidates.update(self._entity_index.get(key, set()))
        candidates.discard(source.id)
        return list(candidates)

    def relevance(self, a: UnifiedEntry, b: UnifiedEntry) -> float:
        """Mixed relevance: 0.4*tag + 0.3*entity + 0.3*text keyword overlap."""
        # Tag overlap (Jaccard)
        tags_a, tags_b = set(a.tags), set(b.tags)
        tag_union = tags_a | tags_b
        tag_overlap = len(tags_a & tags_b) / len(tag_union) if tag_union else 0.0

        # Entity overlap (Jaccard on flattened "type:value" keys)
        ent_a = {f"{t}:{v}" for t, vals in a.entities.items() for v in vals}
        ent_b = {f"{t}:{v}" for t, vals in b.entities.items() for v in vals}
        ent_union = ent_a | ent_b
        ent_overlap = len(ent_a & ent_b) / len(ent_union) if ent_union else 0.0

        # Text keyword overlap (Jaccard on whitespace-split words)
        words_a = set(a.text.split())
        words_b = set(b.text.split())
        text_union = words_a | words_b
        text_overlap = len(words_a & words_b) / len(text_union) if text_union else 0.0

        return (
            self.TAG_WEIGHT * tag_overlap
            + self.ENTITY_WEIGHT * ent_overlap
            + self.TEXT_WEIGHT * text_overlap
        )

    def propagate_cascade(
        self,
        source: UnifiedEntry,
        sensitivity: float,
        entries_lookup: dict[str, UnifiedEntry] | None = None,
    ) -> list[str]:
        """Propagate cascade from source to related entries.

        Args:
            source: The hot memory triggering the cascade.
            sensitivity: Multiplier for heat transfer (from cascade state).
            entries_lookup: Dict mapping entry_id → UnifiedEntry for lookup.

        Returns:
            List of entry IDs that received heat transfer.
        """
        if entries_lookup is None:
            return []

        related_ids = self.find_related(source)
        affected: list[str] = []

        for entry_id in related_ids:
            target = entries_lookup.get(entry_id)
            if target is None:
                continue
            r = self.relevance(source, target)
            if r > self.RELEVANCE_THRESHOLD:
                heat_transfer = source.temperature * r * sensitivity
                target.temperature = min(1.0, target.temperature + heat_transfer)
                target.cascade_generation = source.cascade_generation + 1
                affected.append(entry_id)

        return affected
