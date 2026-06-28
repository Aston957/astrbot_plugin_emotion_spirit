"""Tests for ActivityHistory — novelty decay mechanism (5.1)."""

from __future__ import annotations

import pytest

from emotion_spirit.memory.activity_history import ActivityHistory, ActivityRecord


# ---------------------------------------------------------------------------
# Basic record + novelty
# ---------------------------------------------------------------------------

class TestActivityHistoryRecord:
    """Record activities and read back state."""

    def test_record_stores_activity(self) -> None:
        ah = ActivityHistory(max_records=100, novelty_decay_days=3)
        ah.record("做饭", "physical", enjoyment=0.7)
        assert len(ah.records) == 1
        rec = ah.records[0]
        assert rec.activity == "做饭"
        assert rec.category == "physical"
        assert rec.enjoyment == pytest.approx(0.7)

    def test_record_default_enjoyment(self) -> None:
        ah = ActivityHistory()
        ah.record("画画", "creative")
        assert ah.records[0].enjoyment == pytest.approx(0.5)

    def test_records_capped_at_max(self) -> None:
        ah = ActivityHistory(max_records=5, novelty_decay_days=3)
        for i in range(10):
            ah.record(f"act{i}", "physical", 0.5)
        assert len(ah.records) == 5
        # Oldest should be dropped, newest kept
        assert ah.records[0].activity == "act5"
        assert ah.records[-1].activity == "act9"

    def test_activity_record_dataclass(self) -> None:
        rec = ActivityRecord(
            activity="x", category="c", timestamp=1.0, enjoyment=0.6
        )
        assert rec.activity == "x"
        assert rec.category == "c"
        assert rec.timestamp == pytest.approx(1.0)
        assert rec.enjoyment == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Novelty scoring
# ---------------------------------------------------------------------------

class TestGetNovelty:
    """Novelty = exp-decay on recency * (1 - frequency penalty)."""

    def test_unknown_category_is_fully_novel(self) -> None:
        ah = ActivityHistory()
        assert ah.get_novelty("physical") == pytest.approx(1.0)

    def test_first_time_category_is_high_novelty(self) -> None:
        ah = ActivityHistory(max_records=100, novelty_decay_days=3)
        ah.record("做饭", "physical", 0.7)
        assert ah.get_novelty("physical") > 0.9

    def test_repeated_activity_drops_novelty(self) -> None:
        ah = ActivityHistory(max_records=100, novelty_decay_days=3)
        ah.record("做饭", "physical", 0.7)
        ah.record("做饭", "physical", 0.7)
        ah.record("做饭", "physical", 0.7)
        assert ah.get_novelty("physical") < 0.5

    def test_novelty_bounded_zero_one(self) -> None:
        ah = ActivityHistory()
        for _ in range(20):
            ah.record("做饭", "physical", 0.5)
        novelty = ah.get_novelty("physical")
        assert 0.0 <= novelty <= 1.0

    def test_novelty_different_categories_independent(self) -> None:
        ah = ActivityHistory()
        for _ in range(5):
            ah.record("做饭", "physical", 0.5)
        # Creative never recorded → high novelty
        assert ah.get_novelty("creative") == pytest.approx(1.0)
        assert ah.get_novelty("physical") < 0.5


# ---------------------------------------------------------------------------
# Boredom detection
# ---------------------------------------------------------------------------

class TestBoredomThreshold:
    """is_bored() helper based on novelty < boredom_threshold."""

    def test_boredom_threshold_detection(self) -> None:
        ah = ActivityHistory(novelty_decay_days=3, boredom_threshold=0.2)
        for _ in range(5):
            ah.record("做饭", "physical", 0.5)
        assert ah.get_novelty("physical") < 0.2

    def test_is_bored_true_after_repeats(self) -> None:
        ah = ActivityHistory(novelty_decay_days=3, boredom_threshold=0.2)
        for _ in range(5):
            ah.record("做饭", "physical", 0.5)
        assert ah.is_bored("physical") is True

    def test_is_bored_false_for_fresh_category(self) -> None:
        ah = ActivityHistory(novelty_decay_days=3, boredom_threshold=0.2)
        ah.record("画画", "creative", 0.8)
        assert ah.is_bored("creative") is False

    def test_is_bored_false_for_unknown_category(self) -> None:
        ah = ActivityHistory(novelty_decay_days=3, boredom_threshold=0.2)
        assert ah.is_bored("physical") is False


# ---------------------------------------------------------------------------
# apply_novelty_bias
# ---------------------------------------------------------------------------

class TestApplyNoveltyBias:
    """Multiply category weights by their novelty scores."""

    def test_apply_novelty_bias_scales_weights(self) -> None:
        ah = ActivityHistory()
        ah.record("做饭", "physical", 0.7)
        ah.record("做饭", "physical", 0.7)  # second occurrence starts penalty
        weights = {"physical": 1.0, "creative": 1.0}
        biased = ah.apply_novelty_bias(weights)
        assert biased["physical"] < biased["creative"]

    def test_apply_novelty_bias_preserves_keys(self) -> None:
        ah = ActivityHistory()
        weights = {"physical": 1.0, "creative": 0.5, "social": 0.8}
        biased = ah.apply_novelty_bias(weights)
        assert set(biased.keys()) == {"physical", "creative", "social"}

    def test_apply_novelty_bias_unknown_category_unchanged(self) -> None:
        ah = ActivityHistory()
        # Nothing recorded → novelty = 1.0 for all → weights unchanged
        weights = {"physical": 0.5, "creative": 0.8}
        biased = ah.apply_novelty_bias(weights)
        assert biased["physical"] == pytest.approx(0.5)
        assert biased["creative"] == pytest.approx(0.8)

    def test_apply_novelty_bias_returns_new_dict(self) -> None:
        ah = ActivityHistory()
        weights = {"physical": 1.0}
        biased = ah.apply_novelty_bias(weights)
        assert biased is not weights

    def test_apply_novelty_bias_empty(self) -> None:
        ah = ActivityHistory()
        assert ah.apply_novelty_bias({}) == {}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    """to_dict / from_dict round-trip."""

    def test_to_dict_roundtrip(self) -> None:
        ah = ActivityHistory(max_records=10, novelty_decay_days=3)
        ah.record("做饭", "physical", 0.7)
        ah.record("画画", "creative", 0.9)
        data = ah.to_dict()

        ah2 = ActivityHistory(max_records=10, novelty_decay_days=3)
        ah2.from_dict(data)
        assert len(ah2.records) == 2
        assert ah2.records[0].activity == "做饭"
        assert ah2.records[1].activity == "画画"

    def test_from_dict_empty(self) -> None:
        ah = ActivityHistory()
        ah.from_dict({})
        assert ah.records == []


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestRegistryIntegration:
    """ActivityHistory must be discoverable via the module registry."""

    def test_registered_in_registry(self) -> None:
        from emotion_spirit.core.registry import ModuleRegistry

        # Save the full registry (all 48 modules populated at import), then restore
        # it in a finally block. reset() below wipes everything; reload() only
        # re-registers activity_history. Without restore we leak an empty/partial
        # registry into every later test (e.g. test_registry_mismatch_fix /
        # test_registry_build_dryrun), which they assert against and fail.
        # Mirrors the isolate_registry() pattern in tests/test_module_registry.py.
        saved = dict(ModuleRegistry.get_all())
        try:
            ModuleRegistry.reset()
            # Re-import to trigger @register
            import importlib
            from emotion_spirit.memory import activity_history
            importlib.reload(activity_history)
            spec = ModuleRegistry.get_all().get("activity_history")
            assert spec is not None
            assert "ActivityHistory" in spec.provides
            assert spec.depends_on == []
        finally:
            ModuleRegistry._registry.clear()
            for name, spec in saved.items():
                ModuleRegistry._registry[name] = spec