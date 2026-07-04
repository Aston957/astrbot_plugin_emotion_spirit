"""Bug-G (v1.2.11): conscience pressure 衰减 + _window 增量语义 守护.

原 bug: tick_pressure 死代码 (_raw_pressure 单调递增) + _window.append(累加值)
→ P95 of 单调序列 ≈ 当前值 → get_pressure()=1.0 永真 → 每条对话 critical.

v1.2.11 方案 A: ① tick_pressure 接线 (decay loop, 本测试直接调); ② _window 改增量语义.
用户反馈: 2026-07-04-emotion-spirit-v1210test-feedback.md §4.
"""
from __future__ import annotations

import pytest

from emotion_spirit.regulation.superego.conscience import ConscienceTracker


@pytest.fixture
def tracker() -> ConscienceTracker:
    return ConscienceTracker()


def test_tick_pressure_decays_raw_pressure(tracker: ConscienceTracker):
    """tick_pressure 衰减 _raw_pressure (原死代码, 现应能调)."""
    tracker.record_value_conflict(
        resistance=0.5,
        conflict_values=["v1"],
        tension_type="t",
        behavioral_shift=0.5,
        conscience_impact=0.8,
    )
    raw_before = tracker._raw_pressure
    assert raw_before > 0
    tracker.tick_pressure(1.0)  # 1 小时衰减
    assert tracker._raw_pressure < raw_before, "tick_pressure 应衰减 _raw_pressure"


def test_window_append_delta_not_cumulative(tracker: ConscienceTracker):
    """_window append 单次增量, 不是累加值 (Bug-G 核心修复)."""
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
    """长时衰减应让 get_pressure 下降 (Bug-G 修复核心: 衰减让 _raw_pressure 不会永饱和).

    Bug-G 原症: tick_pressure 死代码 → _raw_pressure 单调递增 + _window.append(累加值) →
    P95 ≈ 当前值 → get_pressure()=1.0 永真 → 每条对话 critical.
    修后: tick_pressure 接线 (本测试直接调), _window 改增量 → P95 = 典型事件强度.
    _raw_pressure 衰减后可远低于 P95 → get_pressure 下降.
    """
    for i in range(15):
        tracker.record_value_conflict(
            resistance=0.5,
            conflict_values=[f"v{i}"],
            tension_type="t",
            behavioral_shift=0.5,
            conscience_impact=0.2,
        )
    # 15 个事件后 _raw_pressure ≈ 3.0, P95 = 0.2 → 必饱和 (ratio = 15)
    p_saturated = tracker.get_pressure()
    assert p_saturated == 1.0, "灌 15 个 0.2 事件, 未衰减前应饱和 (ratio=15, cap 1.0)"

    # 50h 衰减 (~98%): _raw_pressure ≈ 3.0 * 0.92^50 ≈ 0.10, 远低于 P95 (0.2)
    tracker.tick_pressure(50.0)
    p_decayed = tracker.get_pressure()
    assert p_decayed < 1.0, (
        f"长时衰减后 get_pressure 应 < 1.0, 实际 {p_decayed} (Bug-G 未修?)"
    )
    assert p_decayed < p_saturated, (
        f"衰减应降压: before={p_saturated} after={p_decayed}"
    )


def test_record_repair_does_not_append_window(tracker: ConscienceTracker):
    """record_repair / record_alignment (缓解) 不入 _window (缓解不是事件强度)."""
    # 先灌一个事件让 _window 非空可观测增量
    tracker.record_value_conflict(
        resistance=0.5,
        conflict_values=["v1"],
        tension_type="t",
        behavioral_shift=0.5,
        conscience_impact=0.3,
    )
    raw_before = tracker._raw_pressure
    window_before = len(tracker._window)
    last_value_before = tracker._window[-1] if tracker._window else None

    tracker.record_repair("simple")
    tracker.record_alignment("v2", "ok")

    assert len(tracker._window) == window_before, (
        "record_repair/record_alignment 不应 append _window (缓解不入 P95)"
    )
    # 原最后值仍为 0.3,没被缓解后的 _raw_pressure 覆盖
    assert tracker._window[-1] == last_value_before
    # _raw_pressure 应下降 (alignment_base_relief + simple_repair 总和 ≈ 0.2)
    assert tracker._raw_pressure < raw_before, (
        f"缓解应降 _raw_pressure: before={raw_before} after={tracker._raw_pressure}"
    )
