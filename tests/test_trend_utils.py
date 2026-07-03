"""Tests for trend_utils.py"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotion_spirit.utils import EMASmoother, TrendDetector


def test_ema_smoother_convergence():
    smoother = EMASmoother(0.1)
    for _ in range(100):
        smoother.update(1.0)
    assert abs(smoother.value - 1.0) < 0.01


def test_ema_smoother_initial():
    smoother = EMASmoother(0.1)
    assert smoother.value == 0.0
    result = smoother.update(0.5)
    assert result == 0.5  # First update initializes directly


def test_ema_smoother_serialization():
    smoother = EMASmoother(0.1)
    smoother.update(0.5)
    data = smoother.to_dict()
    smoother2 = EMASmoother(0.1)
    smoother2.from_dict(data)
    assert abs(smoother.value - smoother2.value) < 1e-6


def test_trend_detector_convergence():
    td = TrendDetector(0.1, 0.01)
    for _ in range(50):
        td.update(0.3)
    for _ in range(50):
        td.update(0.8)
    assert td.trend() > 0  # Should be trending up


def test_trend_detector_stable():
    td = TrendDetector(0.1, 0.01)
    for _ in range(50):
        td.update(0.5)
    assert abs(td.trend()) < 0.01


def test_trend_detector_slope():
    td = TrendDetector(0.1, 0.01)
    for i in range(10):
        td.update(float(i) / 10)
    assert td.slope(window=10) > 0  # Positive slope


def test_trend_detector_serialization():
    td = TrendDetector(0.1, 0.01)
    td.update(0.5)
    td.update(0.6)
    data = td.to_dict()
    td2 = TrendDetector()
    td2.from_dict(data)
    assert abs(td.trend() - td2.trend()) < 1e-6


if __name__ == "__main__":
    test_ema_smoother_convergence()
    test_ema_smoother_initial()
    test_ema_smoother_serialization()
    test_trend_detector_convergence()
    test_trend_detector_stable()
    test_trend_detector_slope()
    test_trend_detector_serialization()
    print("All trend_utils tests passed!")
