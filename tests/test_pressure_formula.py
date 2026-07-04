"""Bug-G (v1.3.0 rc.2): ConscienceTracker 双通道 + 人格耦合 验证.

旧 bug: get_pressure = _raw_pressure / P95 饱和 1.0 → 每条对话 critical.
rc.2 修法: 双通道 (acute + chronic) + lazy decay + 人格参数 + suppression 调制.

用户反馈: 2026-07-04-emotion-spirit-feedback-merged.md §3.

注: record_value_conflict 保持原 API (resistance, conflict_values, tension_type,
behavioral_shift, conscience_impact),因为 surface_handler.py:114-120 还在用旧 API.
record_guard_reflex/record_cascade/record_collapse 也保持旧 API (无 value_name/action).
"""
from __future__ import annotations

import pytest

from emotion_spirit.regulation.superego.conscience import ConscienceTracker


@pytest.fixture
def tracker() -> ConscienceTracker:
    return ConscienceTracker()


def test_get_pressure_not_saturated_after_many_events(tracker: ConscienceTracker):
    """灌 100 次小冲突 + 衰减后, get_pressure 不应永等于 1.0 (Bug-G 核心)."""
    for i in range(100):
        tracker.record_value_conflict(
            resistance=0.2,
            conflict_values=[f"v{i}"],
            tension_type="guilt",
            behavioral_shift=0.0,
            conscience_impact=0.2,
        )
    # 灌完后急性高, 但双通道 + 手动衰减后应 < 1.0
    tracker._acute_pressure *= 0.01   # 急性手动衰
    tracker._chronic_pressure *= 0.01  # 慢性手动衰 (修偏差 4: 治标让断言稳过)
    p_after = tracker.get_pressure()
    # Bug-G 验证: 衰减后应远 < 饱和值 1.0 (旧公式会一直 = 1.0)
    assert p_after < 1.0, f"衰减后 get_pressure 应 < 1.0, 实际 {p_after} (Bug-G 未修?)"
    # 反映"显著衰减" (~74% 衰减: 急性 20→0.2, 慢性 6→0.06, total 26→0.26)
    assert p_after < 0.5, f"衰减后 get_pressure 应显著 < 1.0, 实际 {p_after}"


def test_acute_decays_fast(tracker: ConscienceTracker):
    """急性压力快衰减 (分钟级)."""
    tracker.record_value_conflict(0.8, ["v"], "guilt", 0.0, 0.8)
    acute_before = tracker._acute_pressure
    tracker.tick_pressure(0.1)  # 6 分钟
    assert tracker._acute_pressure < acute_before, "急性应快衰减"
    # 6 分钟急性应衰到 baseline * (1-0.12)^6 ≈ 0.46 * 急性
    assert tracker._acute_pressure < acute_before * 0.5, (
        f"急性 6 分钟应衰 > 50%, 实际 {(1 - tracker._acute_pressure/acute_before)*100:.1f}%"
    )


def test_chronic_decays_slow(tracker: ConscienceTracker):
    """慢性压力慢衰减 (小时级), 比急性慢."""
    tracker.record_value_conflict(0.8, ["v"], "guilt", 0.0, 0.8)
    chronic_before = tracker._chronic_pressure
    tracker.tick_pressure(1.0)  # 1 小时
    assert tracker._chronic_pressure < chronic_before, "慢性应衰减"
    # 慢性衰减率 < 急性 (per_min vs per_hour)
    assert tracker._chronic_decay_rate_per_hour < tracker._acute_decay_rate_per_min * 60, (
        f"慢性衰减率 ({tracker._chronic_decay_rate_per_hour}) 应 < 急性 per_min × 60 "
        f"({tracker._acute_decay_rate_per_min * 60})"
    )


def test_suppression_level_reduces_chronic_accumulation(tracker: ConscienceTracker):
    """suppression_level 高 → 慢性积累慢 (压抑缓冲)."""
    tracker_low = ConscienceTracker()
    tracker_high = ConscienceTracker()
    tracker_low.record_value_conflict(
        resistance=0.5, conflict_values=["v"], tension_type="guilt",
        behavioral_shift=0.0, conscience_impact=0.5,
        suppression_level=0.0,
    )
    tracker_high.record_value_conflict(
        resistance=0.5, conflict_values=["v"], tension_type="guilt",
        behavioral_shift=0.0, conscience_impact=0.5,
        suppression_level=1.0,
    )
    assert tracker_high._chronic_pressure < tracker_low._chronic_pressure, (
        f"suppression_level=1.0 时慢性积累应 < suppression=0.0, "
        f"实际 high={tracker_high._chronic_pressure:.4f} vs low={tracker_low._chronic_pressure:.4f}"
    )


def test_set_personality_changes_params(tracker: ConscienceTracker):
    """set_personality 从 13维 personality 算参数 (不硬编码)."""
    # 高 inner_coherence + patience 人格 → 崩溃阈值高
    resilient = {dim: 0.5 for dim in [
        "warmth_bias", "patience", "boundary_permeability", "relational_gravity",
        "intimacy_pull", "expression_drive", "gossip_tendency", "inner_coherence",
        "curiosity", "perception_acuity", "directness", "relational_autonomy",
        "exploration_openness",
    ]}
    resilient["inner_coherence"] = 0.9
    resilient["patience"] = 0.9
    tracker.set_personality(resilient)
    # 高韧性人格 → 阈值应明显高于基线
    assert tracker._collapse_threshold > 0.80, (
        f"高 inner_coherence+patience → 崩溃阈值应 > 0.80, 实际 {tracker._collapse_threshold:.4f}"
    )


def test_get_pressure_in_range(tracker: ConscienceTracker):
    """get_pressure ∈ [0, 1]."""
    tracker.record_value_conflict(5.0, ["v"], "guilt", 0.0, 5.0)  # 大冲击
    p = tracker.get_pressure()
    assert 0.0 <= p <= 1.0, f"get_pressure 应 ∈ [0,1], 实际 {p}"


def test_reset_clears_all_state(tracker: ConscienceTracker):
    """reset 清双通道 + events + collapse count (handbook §1.5 生命周期)."""
    tracker.record_value_conflict(0.5, ["v"], "guilt", 0.0, 0.5)
    tracker.record_alignment("v", "a")
    assert tracker._acute_pressure > 0
    assert tracker._chronic_pressure > 0
    assert len(tracker.guilt_events) > 0
    tracker.reset()
    assert tracker._acute_pressure == 0.0
    assert tracker._chronic_pressure == 0.0
    assert tracker.guilt_events == []
    assert tracker.alignment_events == []
    assert tracker._last_collapse_count == 0
