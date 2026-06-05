"""Tests for meaning_reservoir.py"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotion_spirit.meaning_reservoir import MeaningReservoir


def test_accumulate_basic():
    r = MeaningReservoir()
    r.accumulate(phi=0.8, emotional_weight=0.7)
    assert r.level > 0


def test_draw_basic():
    r = MeaningReservoir()
    r.level = 0.5
    drawn = r.draw(0.3)
    assert drawn == 0.3
    assert abs(r.level - 0.2) < 1e-6


def test_draw_exceeds():
    r = MeaningReservoir()
    r.level = 0.1
    drawn = r.draw(0.5)
    assert drawn == 0.1
    assert r.level == 0.0


def test_tick_decay():
    r = MeaningReservoir()
    r.level = 1.0
    r._last_tick = time.time() - 3600  # 1 hour ago
    r.tick()
    assert r.level < 1.0


def test_serialization():
    r = MeaningReservoir()
    r.accumulate(0.5, 0.5)
    data = r.to_dict()
    r2 = MeaningReservoir()
    r2.from_dict(data)
    assert abs(r.level - r2.level) < 1e-6


if __name__ == "__main__":
    test_accumulate_basic()
    test_draw_basic()
    test_draw_exceeds()
    test_tick_decay()
    test_serialization()
    print("All meaning_reservoir tests passed!")
