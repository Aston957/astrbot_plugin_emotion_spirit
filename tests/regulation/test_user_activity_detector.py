"""Tests for emotion_spirit.utils.user_activity_detector — Task 5.5 UserActivityDetector."""

from emotion_spirit.utils import UserActivityDetector
from emotion_spirit.regulation.life_plan import DailyPlan, PlannedEvent


class TestDetectPlan:
    """Unit tests for UserActivityDetector.detect_plan."""

    def test_detect_joint_activity(self):
        uad = UserActivityDetector()
        result = uad.detect_plan("明天陪你去逛街")
        assert result is not None
        assert result["type"] == "joint"
        assert "逛街" in result["activity"]

    def test_detect_busy_signal(self):
        uad = UserActivityDetector()
        result = uad.detect_plan("我今天很忙")
        assert result is not None
        assert result["type"] == "busy"

    def test_detect_no_plan(self):
        uad = UserActivityDetector()
        result = uad.detect_plan("今天天气不错")
        assert result is None

    def test_detect_一起_pattern(self):
        uad = UserActivityDetector()
        result = uad.detect_plan("我们一起去看电影吧")
        assert result is not None
        assert result["type"] == "joint"

    def test_detect_没时间(self):
        uad = UserActivityDetector()
        result = uad.detect_plan("今天没时间")
        assert result is not None
        assert result["type"] == "busy"


class TestInjectIntoPlan:
    """Unit tests for UserActivityDetector.inject_into_plan."""

    def test_inject_joint_adds_event(self):
        uad = UserActivityDetector()
        plan = DailyPlan("2026-06-28", generated_at=0.0, events=[])
        detected = {"type": "joint", "activity": "逛街", "time": "明天"}
        uad.inject_into_plan(plan, detected)
        assert len(plan.events) == 1
        assert plan.events[0].category == "user_joint"
        assert "逛街" in plan.events[0].activity

    def test_inject_busy_cancels_flexible_template_events(self):
        uad = UserActivityDetector()
        e1 = PlannedEvent(
            id="t1", time_slot="afternoon", approximate_time="14:00",
            activity="喝茶", category="template", flexibility=0.8,
        )
        e2 = PlannedEvent(
            id="t2", time_slot="evening", approximate_time="20:00",
            activity="重要约会", category="template", flexibility=0.1,
        )
        plan = DailyPlan("2026-06-28", generated_at=0.0, events=[e1, e2])
        detected = {"type": "busy"}
        uad.inject_into_plan(plan, detected)
        # flexible event cancelled, inflexible event kept
        assert e1.status == "cancelled"
        assert e1.cancellation_reason == "用户忙"
        assert e2.status != "cancelled"