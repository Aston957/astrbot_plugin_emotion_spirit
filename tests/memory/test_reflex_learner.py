"""Tests for ReflexLearner — behavior feedback loop."""

from __future__ import annotations

import pytest

from emotion_spirit.memory.reflex_learner import (
    ReflexLearner,
    ReflexLearnerStore,
    compute_behavior,
)


# ---------------------------------------------------------------------------
# ReflexLearnerStore
# ---------------------------------------------------------------------------

class TestReflexLearnerStore:
    """Unit tests for the persistent delta store."""

    def test_get_delta_default_zero(self) -> None:
        store = ReflexLearnerStore()
        assert store.get_delta("memory", "intimacy_recall_threshold") == 0.0

    def test_set_and_get_delta(self) -> None:
        store = ReflexLearnerStore()
        store.set_delta("memory", "intimacy_recall_threshold", 0.15)
        assert store.get_delta("memory", "intimacy_recall_threshold") == pytest.approx(0.15)

    def test_set_delta_clamped_upper(self) -> None:
        store = ReflexLearnerStore()
        store.set_delta("memory", "k", 0.99)
        assert store.get_delta("memory", "k") == pytest.approx(0.2)

    def test_set_delta_clamped_lower(self) -> None:
        store = ReflexLearnerStore()
        store.set_delta("memory", "k", -0.99)
        assert store.get_delta("memory", "k") == pytest.approx(-0.2)

    def test_to_dict_roundtrip(self) -> None:
        store = ReflexLearnerStore()
        store.set_delta("memory", "k1", 0.1)
        store.set_delta("personality", "k2", -0.05)
        data = store.to_dict()
        assert data == {"memory": {"k1": 0.1}, "personality": {"k2": -0.05}}

        store2 = ReflexLearnerStore()
        store2.from_dict(data)
        assert store2.get_delta("memory", "k1") == pytest.approx(0.1)
        assert store2.get_delta("personality", "k2") == pytest.approx(-0.05)

    def test_from_dict_ignores_non_dict_values(self) -> None:
        store = ReflexLearnerStore()
        store.from_dict({"bad": "string", "ok": {"k": 0.1}})
        assert store.get_delta("bad", "anything") == 0.0
        assert store.get_delta("ok", "k") == pytest.approx(0.1)

    def test_from_dict_replaces_old_data(self) -> None:
        store = ReflexLearnerStore()
        store.set_delta("a", "k", 0.5)
        store.from_dict({"b": {"k2": 0.3}})
        # Old data gone
        assert store.get_delta("a", "k") == 0.0
        assert store.get_delta("b", "k2") == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# ReflexLearner
# ---------------------------------------------------------------------------

class TestReflexLearner:
    """Unit tests for the behavior-feedback learner."""

    def test_positive_behavior_increases_deltas(self) -> None:
        store = ReflexLearnerStore()
        learner = ReflexLearner(store, learning_rate=0.01)
        learner.learn(1.0)
        for agent_name, key in ReflexLearner.LEARNABLE:
            assert store.get_delta(agent_name, key) == pytest.approx(0.01)

    def test_negative_behavior_decreases_deltas(self) -> None:
        store = ReflexLearnerStore()
        learner = ReflexLearner(store, learning_rate=0.02)
        learner.learn(-1.0)
        for agent_name, key in ReflexLearner.LEARNABLE:
            assert store.get_delta(agent_name, key) == pytest.approx(-0.02)

    def test_zero_behavior_no_change(self) -> None:
        store = ReflexLearnerStore()
        learner = ReflexLearner(store, learning_rate=0.05)
        learner.learn(0.0)
        for agent_name, key in ReflexLearner.LEARNABLE:
            assert store.get_delta(agent_name, key) == 0.0

    def test_multiple_learn_calls_accumulate(self) -> None:
        store = ReflexLearnerStore()
        learner = ReflexLearner(store, learning_rate=0.01)
        for _ in range(5):
            learner.learn(1.0)
        for agent_name, key in ReflexLearner.LEARNABLE:
            assert store.get_delta(agent_name, key) == pytest.approx(0.05)

    def test_delta_clamped_at_boundary(self) -> None:
        store = ReflexLearnerStore()
        learner = ReflexLearner(store, learning_rate=0.1)
        # 3 positive steps = 0.3, but clamp at 0.2
        for _ in range(3):
            learner.learn(1.0)
        for agent_name, key in ReflexLearner.LEARNABLE:
            assert store.get_delta(agent_name, key) == pytest.approx(0.2)

    def test_delta_clamped_at_negative_boundary(self) -> None:
        store = ReflexLearnerStore()
        learner = ReflexLearner(store, learning_rate=0.1)
        for _ in range(3):
            learner.learn(-1.0)
        for agent_name, key in ReflexLearner.LEARNABLE:
            assert store.get_delta(agent_name, key) == pytest.approx(-0.2)

    def test_store_property(self) -> None:
        store = ReflexLearnerStore()
        learner = ReflexLearner(store)
        assert learner.store is store

    def test_learnable_count(self) -> None:
        assert len(ReflexLearner.LEARNABLE) == 4

    def test_mixed_signals(self) -> None:
        store = ReflexLearnerStore()
        learner = ReflexLearner(store, learning_rate=0.01)
        learner.learn(1.0)   # +0.01
        learner.learn(1.0)   # +0.02
        learner.learn(-1.0)  # +0.01
        learner.learn(0.0)   # +0.01
        learner.learn(-1.0)  # 0.0
        for agent_name, key in ReflexLearner.LEARNABLE:
            assert store.get_delta(agent_name, key) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_behavior
# ---------------------------------------------------------------------------

class TestComputeBehavior:
    """Tests for the gap-to-signal helper."""

    def test_immediate_reply(self) -> None:
        assert compute_behavior(0.0) == 1.0

    def test_5min_boundary(self) -> None:
        assert compute_behavior(300.0) == 1.0

    def test_just_over_5min(self) -> None:
        assert compute_behavior(301.0) == 0.0

    def test_1hour_uncertain(self) -> None:
        assert compute_behavior(3600.0) == 0.0

    def test_2hour_boundary(self) -> None:
        assert compute_behavior(7200.0) == -1.0

    def test_just_under_2hour(self) -> None:
        assert compute_behavior(7199.0) == 0.0

    def test_very_long_gap(self) -> None:
        assert compute_behavior(86400.0) == -1.0
