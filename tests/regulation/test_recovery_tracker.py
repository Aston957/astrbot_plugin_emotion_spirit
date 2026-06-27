"""Tests for emotion_spirit.regulation.recovery_tracker — Task 6 (5.3).

Emotional recovery trajectory tracker based on Bonanno (2004) and
Walker (2013) 4F model. Different collapse archetypes have different
recovery paths.
"""

from emotion_spirit.regulation.recovery_tracker import (
    RecoveryTracker, RECOVERY_TRAJECTORIES,
)
from emotion_spirit.regulation.life_plan import DailyPlan, PlannedEvent


# ── Trajectory data integrity ──

def test_trajectories_have_all_five_archetypes():
    """All five collapse archetypes have recovery trajectories."""
    expected = {"volcanic", "collapse", "freeze", "drift", "cold"}
    assert set(RECOVERY_TRAJECTORIES.keys()) == expected


def test_every_trajectory_ends_with_normalization():
    """Every trajectory's final stage is a return-to-normal."""
    for archetype, stages in RECOVERY_TRAJECTORIES.items():
        assert stages[-1] == "恢复正常", (
            f"{archetype} trajectory should end with '恢复正常', got '{stages[-1]}'"
        )


def test_trajectories_have_at_least_two_stages():
    """Every trajectory has at least 2 stages."""
    for archetype, stages in RECOVERY_TRAJECTORIES.items():
        assert len(stages) >= 2, f"{archetype} has only {len(stages)} stage(s)"


# ── RecoveryTracker lifecycle ──

def test_start_recovery_initializes_stage():
    """start_recovery sets active archetype and resets stage to 0."""
    rt = RecoveryTracker()
    rt.start_recovery("volcanic")
    assert rt._active_recovery == "volcanic"
    assert rt._recovery_stage == 0


def test_advance_stage_progression():
    """advance_stage increments the recovery stage."""
    rt = RecoveryTracker()
    rt.start_recovery("volcanic")
    rt.advance_stage()
    assert rt._recovery_stage == 1


def test_completion_clears_active_recovery():
    """After advancing through all stages, active recovery is cleared."""
    rt = RecoveryTracker()
    rt.start_recovery("freeze")  # freeze has 4 stages
    for _ in range(4):
        rt.advance_stage()
    assert rt._active_recovery is None


def test_advance_stage_noop_when_no_active_recovery():
    """advance_stage is a no-op when no recovery is active."""
    rt = RecoveryTracker()
    rt.advance_stage()  # should not crash
    assert rt._active_recovery is None


def test_start_recovery_resets_previous():
    """Starting a new recovery resets a previous one."""
    rt = RecoveryTracker()
    rt.start_recovery("volcanic")
    rt.advance_stage()
    rt.advance_stage()
    assert rt._recovery_stage == 2
    # Start a new recovery — should reset
    rt.start_recovery("cold")
    assert rt._active_recovery == "cold"
    assert rt._recovery_stage == 0


# ── adapt_plan_for_recovery ──

def test_adapt_plan_cancels_existing_events():
    """adapt_plan_for_recovery cancels planned events and adds recovery ones."""
    rt = RecoveryTracker()
    rt.start_recovery("volcanic")
    plan = DailyPlan(
        date="2026-06-27", generated_at=0.0,
        events=[
            PlannedEvent(
                id="e1", time_slot="morning", approximate_time="10:00",
                activity="社交聚会", category="social", status="planned",
                flexibility=0.5,
            ),
        ],
        personality_snapshot={}, adaptations=[], dream_seed="",
    )
    rt.adapt_plan_for_recovery(plan)
    # The social event should be cancelled
    social_event = [e for e in plan.events if e.activity == "社交聚会"]
    assert len(social_event) == 1
    assert social_event[0].status == "cancelled"
    assert social_event[0].cancellation_reason is not None


def test_adapt_plan_adds_recovery_events():
    """adapt_plan_for_recovery adds recovery-category events."""
    rt = RecoveryTracker()
    rt.start_recovery("volcanic")
    plan = DailyPlan(
        date="2026-06-27", generated_at=0.0,
        events=[
            PlannedEvent(
                id="e1", time_slot="morning", approximate_time="10:00",
                activity="社交聚会", category="social", status="planned",
                flexibility=0.5,
            ),
        ],
        personality_snapshot={}, adaptations=[], dream_seed="",
    )
    rt.adapt_plan_for_recovery(plan)
    recovery_events = [e for e in plan.events if e.category == "recovery"]
    assert len(recovery_events) >= 1
    assert all(e.status == "planned" for e in recovery_events)
    assert recovery_events[0].flexibility == 0.2


def test_adapt_plan_noop_when_no_active_recovery():
    """adapt_plan_for_recovery is a no-op when no recovery is active."""
    rt = RecoveryTracker()
    plan = DailyPlan(
        date="2026-06-27", generated_at=0.0,
        events=[
            PlannedEvent(
                id="e1", time_slot="morning", approximate_time="10:00",
                activity="社交聚会", category="social", status="planned",
                flexibility=0.5,
            ),
        ],
        personality_snapshot={}, adaptations=[], dream_seed="",
    )
    original_count = len(plan.events)
    rt.adapt_plan_for_recovery(plan)
    assert len(plan.events) == original_count
    assert plan.events[0].status == "planned"


def test_adapt_plan_stage_two_different_activities():
    """Stage 2 of recovery gives different activities from stage 1."""
    rt = RecoveryTracker()
    rt.start_recovery("volcanic")
    plan1 = DailyPlan(
        date="2026-06-27", generated_at=0.0,
        events=[
            PlannedEvent(
                id="e1", time_slot="morning", approximate_time="10:00",
                activity="社交聚会", category="social", status="planned",
                flexibility=0.5,
            ),
        ],
        personality_snapshot={}, adaptations=[], dream_seed="",
    )
    rt.adapt_plan_for_recovery(plan1)
    stage1_activities = [e.activity for e in plan1.events if e.category == "recovery"]

    # Advance to stage 2
    rt.advance_stage()
    plan2 = DailyPlan(
        date="2026-06-28", generated_at=0.0,
        events=[
            PlannedEvent(
                id="e1", time_slot="morning", approximate_time="10:00",
                activity="社交聚会", category="social", status="planned",
                flexibility=0.5,
            ),
        ],
        personality_snapshot={}, adaptations=[], dream_seed="",
    )
    rt.adapt_plan_for_recovery(plan2)
    stage2_activities = [e.activity for e in plan2.events if e.category == "recovery"]

    # The activities should be from different templates
    assert stage1_activities != stage2_activities


# ── Serialization ──

def test_to_dict_roundtrip():
    """to_dict/from_dict round-trip preserves state."""
    import time
    rt = RecoveryTracker()
    rt.start_recovery("volcanic")
    rt.advance_stage()
    data = rt.to_dict()
    assert data["active"] == "volcanic"
    assert data["stage"] == 1
    assert data["start"] > 0

    rt2 = RecoveryTracker()
    rt2.from_dict(data)
    assert rt2._active_recovery == "volcanic"
    assert rt2._recovery_stage == 1
    assert rt2._recovery_start == data["start"]


def test_from_dict_empty():
    """from_dict with empty dict handles gracefully."""
    rt = RecoveryTracker()
    rt.from_dict({})
    assert rt._active_recovery is None
    assert rt._recovery_stage == 0
    assert rt._recovery_start == 0.0


# ── All archetype paths are traversable ──

def test_all_archetypes_can_complete():
    """Every archetype can go through all stages and complete."""
    for archetype in RECOVERY_TRAJECTORIES:
        rt = RecoveryTracker()
        rt.start_recovery(archetype)
        n_stages = len(RECOVERY_TRAJECTORIES[archetype])
        for _ in range(n_stages):
            rt.advance_stage()
        assert rt._active_recovery is None, (
            f"{archetype} did not complete after {n_stages} stages"
        )
