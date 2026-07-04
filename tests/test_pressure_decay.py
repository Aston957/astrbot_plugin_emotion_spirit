"""ConscienceTracker v1.3.0 rc.2 双通道衰减 + 缓解不入 _window 守护.

历史:
- v1.2.10: tick_pressure 死代码 (_raw_pressure 单调递增) + _window.append(累加值)
  → P95 of 单调序列 ≈ 当前值 → get_pressure()=1.0 永真 → 每条对话 critical.
- v1.2.11 test2: tick_pressure 接线 (decay loop) + _window 增量语义 (半修, 公式未改).
- v1.3.0 rc.2: 双通道 (急性+慢性) + lazy decay + 人格参数 + suppression 调制
  (治本: get_pressure = acute + chronic, 不再 _raw/P95 公式).

用户反馈: 2026-07-04-emotion-spirit-feedback-merged.md §3.
"""
from __future__ import annotations

import pytest

from emotion_spirit.regulation.superego.conscience import ConscienceTracker


@pytest.fixture
def tracker() -> ConscienceTracker:
    return ConscienceTracker()


def test_tick_pressure_decays_dual_channel(tracker: ConscienceTracker):
    """v1.3.0 rc.2: tick_pressure 衰减双通道 (急性 + 慢性)."""
    tracker.record_value_conflict(
        resistance=0.5,
        conflict_values=["v1"],
        tension_type="t",
        behavioral_shift=0.5,
        conscience_impact=0.8,
    )
    acute_before = tracker._acute_pressure
    chronic_before = tracker._chronic_pressure
    assert acute_before > 0
    assert chronic_before > 0
    tracker.tick_pressure(1.0)  # 1 小时衰减
    # 双通道都应衰减
    assert tracker._acute_pressure < acute_before, "tick_pressure 应衰减 _acute_pressure"
    assert tracker._chronic_pressure < chronic_before, "tick_pressure 应衰减 _chronic_pressure"
    # 1h: 急性衰 99.96%, 慢性衰 8%
    assert tracker._acute_pressure < acute_before * 0.1, "急性 1h 衰应 > 90%"


def test_window_append_delta_not_cumulative(tracker: ConscienceTracker):
    """_window append 单次增量, 不是累加值 (Bug-G v1.2.11 test2 修复保留)."""
    tracker.record_value_conflict(
        resistance=0.5,
        conflict_values=["v1"],
        tension_type="t",
        behavioral_shift=0.5,
        conscience_impact=0.3,
    )
    tracker.record_value_conflict(
        resistance=0.5,
        conflict_values=["v2"],
        tension_type="t",
        behavioral_shift=0.5,
        conscience_impact=0.5,
    )
    # _window 应含 [0.3, 0.5] (增量), 不是 [0.3, 0.8] (累加)
    assert tracker._window[-1] == pytest.approx(0.5), (
        "_window 应 append 单次增量 (0.5), 不是累加值 (0.8)"
    )
    assert tracker._window[-2] == pytest.approx(0.3)


def test_decay_reduces_get_pressure(tracker: ConscienceTracker):
    """v1.3.0 rc.2: 双通道衰减让 get_pressure 显著下降 (Bug-G 治本).

    15 次 0.2 灌完: 急性 3.0 + 慢性 0.9 = 3.9 → cap 1.0.
    50h tick: 急性衰 ~100%, 慢性衰 ~98%. total 接近 0.
    """
    for i in range(15):
        tracker.record_value_conflict(
            resistance=0.5,
            conflict_values=[f"v{i}"],
            tension_type="t",
            behavioral_shift=0.5,
            conscience_impact=0.2,
        )
    p_saturated = tracker.get_pressure()
    assert p_saturated == 1.0, "灌 15 个 0.2 事件, 灌完应 cap 1.0 (双通道)"

    # 50h tick: 急性衰 ~100%, 慢性 (1-0.08)^50 ≈ 0.015
    tracker.tick_pressure(50.0)
    p_decayed = tracker.get_pressure()
    assert p_decayed < 1.0, (
        f"长时衰减后 get_pressure 应 < 1.0, 实际 {p_decayed} (Bug-G 未修?)"
    )
    assert p_decayed < p_saturated, (
        f"衰减应降压: before={p_saturated} after={p_decayed}"
    )
    # 50h 慢性衰 98.5%, 急性衰 ~100%, total 应远 < 0.5
    assert p_decayed < 0.1, f"50h 衰减后期望 < 0.1, 实际 {p_decayed}"


def test_record_repair_does_not_append_window(tracker: ConscienceTracker):
    """v1.3.0 rc.2: record_repair / record_alignment (缓解) 不入 _window."""
    # 先灌一个事件让 _window 非空可观测增量
    tracker.record_value_conflict(
        resistance=0.5,
        conflict_values=["v1"],
        tension_type="t",
        behavioral_shift=0.5,
        conscience_impact=0.3,
    )
    acute_before = tracker._acute_pressure
    chronic_before = tracker._chronic_pressure
    window_before = len(tracker._window)
    last_value_before = tracker._window[-1] if tracker._window else None

    tracker.record_repair("simple")
    tracker.record_alignment("v2", "ok")

    assert len(tracker._window) == window_before, (
        "record_repair/record_alignment 不应 append _window (缓解不入 P95)"
    )
    # 原最后值仍为 0.3,没被缓解后的 _acute_pressure 覆盖
    assert tracker._window[-1] == last_value_before
    # 双通道应下降 (alignment_base_relief 0.12 + simple_repair ~0.2)
    assert tracker._acute_pressure < acute_before, (
        f"缓解应降 _acute_pressure: before={acute_before} after={tracker._acute_pressure}"
    )
    assert tracker._chronic_pressure < chronic_before, (
        f"缓解应降 _chronic_pressure: before={chronic_before} after={tracker._chronic_pressure}"
    )
