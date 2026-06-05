"""Tests for intimacy.py"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotion_spirit.intimacy import IntimacyTracker


def test_update_creates_profile():
    tracker = IntimacyTracker()
    tracker.update("user1", temporal_hours=100, interval_seconds=3600)
    profile = tracker.get_profile("user1")
    assert profile.temporal_depth == 100


def test_intimacy_score_range():
    tracker = IntimacyTracker()
    tracker.update("user1", temporal_hours=200, repair_count=3)
    score = tracker.get_intimacy("user1", "xiaofu")
    assert 0.0 <= score <= 1.0


def test_intimacy_modulation():
    tracker = IntimacyTracker()
    tracker.update("user1", temporal_hours=500, repair_count=10)
    mod = tracker.get_weight("user1", "xiaofu", "hot_pool")
    assert mod > 1.0  # High intimacy -> hot pool weight boost


def test_lifecycle_progression():
    tracker = IntimacyTracker()
    # Stranger
    tracker.update("user1", temporal_hours=0.1)
    assert tracker.get_lifecycle("user1") == "stranger"

    # Acquaintance: needs intimacy > 0.2 AND temporal_depth >= 168
    # temporal=192h: 192/912*0.3=0.063, need investment*0.2 > 0.137 -> investment > 0.685
    tracker.update("user1", temporal_hours=24 * 8, user_investment_delta=0.8)
    assert tracker.get_lifecycle("user1") == "acquaintance"


def test_asymmetric():
    tracker = IntimacyTracker()
    tracker.update("user1", temporal_hours=100, user_investment_delta=0.8)
    score_f = tracker.get_intimacy("user1", "xiaofu")
    score_t = tracker.get_intimacy("user1", "xiaotian")
    assert score_f >= 0
    assert score_t >= 0


def test_serialization():
    tracker = IntimacyTracker()
    tracker.update("user1", temporal_hours=100)
    data = tracker.to_dict()
    tracker2 = IntimacyTracker()
    tracker2.from_dict(data)
    assert tracker2.get_profile("user1").temporal_depth == 100


if __name__ == "__main__":
    test_update_creates_profile()
    test_intimacy_score_range()
    test_intimacy_modulation()
    test_lifecycle_progression()
    test_asymmetric()
    test_serialization()
    print("All intimacy tests passed!")
