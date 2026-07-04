"""Bug-G (v1.3.0 rc.4): 压力不饱和守护.

rc.3 set_personality 只传 deep (5维) → KB weights 6 个 surface 维度取 0.5 兜底 →
参数没人格化 → chronic_decay=0.08 (慢) → 3-4 条 conflict → critical.
rc.4 修: set_personality 传全 13 维 + 调 baseline + 核对 weights 正负.
本测试: 连续灌 conflict, 验证 get_pressure 不饱和 (< 0.95).
"""
from __future__ import annotations

from emotion_spirit.regulation.superego.conscience import ConscienceTracker


def _neutral_personality() -> dict[str, float]:
    """13 维中性人格 (全 0.5)."""
    return {dim: 0.5 for dim in [
        "warmth_bias", "patience", "boundary_permeability", "relational_gravity",
        "intimacy_pull", "expression_drive", "gossip_tendency", "inner_coherence",
        "curiosity", "perception_acuity", "directness", "relational_autonomy",
        "exploration_openness",
    ]}


def test_pressure_not_saturated_after_many_conflicts():
    """灌冲突后让时间流逝 → get_pressure < 0.95.

    模拟突发冲突爆发 → 24h 静默 → 压力应消散到 < 0.95.
    rc.3: 3-4 条 conflict 永饱和 (chronic_decay=0.08).
    rc.4: 50 条 conflict + 24h decay 后应 < 0.95.
    """
    tracker = ConscienceTracker()
    tracker.set_personality(_neutral_personality())
    for i in range(50):
        tracker.record_value_conflict(
            resistance=0.5,
            conflict_values=[f"v{i}"],
            tension_type="test",
            behavioral_shift=0.5,
            conscience_impact=0.5,
        )
    # 模拟 24 小时静默 (不设时间间隔, 一次性回拨)
    tracker._last_tick_time -= 24 * 3600
    p = tracker.get_pressure()
    assert p < 0.95, (
        f"50 条 conflict + 24h 衰减后 get_pressure={p}, 应 < 0.95. "
        f"(chronic_multiplier={tracker._chronic_multiplier}, "
        f"chronic_decay={tracker._chronic_decay_rate_per_hour})"
    )


def test_chronic_decays_within_hours():
    """慢性衰减: 5 小时后 chronic < 初始值 * 0.5.

    rc.4 chronic_decay_rate_per_hour baseline=0.20.
    5h 衰减系数 = (1-0.20)^5 = 0.328 < 0.50.
    """
    tracker = ConscienceTracker()
    tracker.set_personality(_neutral_personality())
    tracker.record_value_conflict(
        resistance=0.8,
        conflict_values=["v"],
        tension_type="a",
        behavioral_shift=0.5,
        conscience_impact=0.8,
    )
    chronic_before = tracker._chronic_pressure
    tracker._last_tick_time -= 5 * 3600
    tracker.get_pressure()
    assert tracker._chronic_pressure < chronic_before * 0.5, (
        f"5 小时后 chronic 应衰减到 < 50% (rc.4 baseline 0.20/h), "
        f"实际 {tracker._chronic_pressure}/{chronic_before}"
    )


def test_set_personality_changes_params_with_full_dims():
    """set_personality 传全 13 维 → 参数偏离 baseline (人格化生效)."""
    tracker = ConscienceTracker()
    resilient = _neutral_personality()
    resilient["inner_coherence"] = 0.9
    resilient["patience"] = 0.9
    tracker.set_personality(resilient)
    # rc.4 正权重: inner_coherence(0.06) + patience(0.04) → 0.20 + 0.9*0.06 + 0.9*0.04 = 0.29
    assert tracker._chronic_decay_rate_per_hour > 0.20, (
        f"高 inner_coherence+patience → chronic_decay 应 > baseline 0.20, "
        f"实际 {tracker._chronic_decay_rate_per_hour} (weights 正负反了?)"
    )


def test_acute_decay_from_personality():
    """高 patience/inner_coherence → acute_decay 升 (rc.4 正权重)."""
    tracker = ConscienceTracker()
    tracker.set_personality(_neutral_personality())
    neutral_acute = tracker._acute_decay_rate_per_min
    high = {**_neutral_personality(), "patience": 0.9, "inner_coherence": 0.9}
    tracker.set_personality(high)
    assert tracker._acute_decay_rate_per_min > neutral_acute, (
        f"高 patience+inner_coherence → acute_decay 应升 (正权重), "
        f"实际 {tracker._acute_decay_rate_per_min} vs neutral {neutral_acute}"
    )