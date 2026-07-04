"""ConscienceTracker v1.3.0 rc.2 双通道 + 人格耦合 守护.

历史:
- Phase 4 C1: P95 归一化 (B2 算法) — 已删 (v1.3.0 rc.2 治 Bug-G 治本)
- v1.2.11 test2: _window 增量语义 + _decay_tick_loop 接线 (半修)
- v1.3.0 rc.2: 双通道 (急性 + 慢性) + lazy decay + 人格参数 + suppression 调制

本文件保留 _window 诊断 append 测试 + get_pressure [0,1] 范围测试,
旧 P95/cold-start 测试改写为双通道对应行为.
"""
import pytest

from emotion_spirit.regulation.superego import ConscienceTracker


# 清除 env var 防止测试间污染
@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    monkeypatch.delenv("EMOTION_SPIRIT_PRESSURE_WINDOW", raising=False)
    yield


def test_window_appends_on_record():
    """每次 record_* 写时, _window 应同步 append 单次增量 (Bug-G v1.2.11 增量语义)."""
    tracker = ConscienceTracker()
    initial_window_len = len(tracker._window)
    tracker.record_value_conflict(
        resistance=0.5, conflict_values=["honesty"], tension_type="intrinsic",
        behavioral_shift=0.1, conscience_impact=0.3,
    )
    assert len(tracker._window) == initial_window_len + 1
    assert tracker._window[-1] == pytest.approx(0.3, abs=0.01)


def test_get_pressure_dual_channel_caps_at_1():
    """v1.3.0 rc.2: 双通道 (急性+慢性) 求和后 cap 1.0 (不再是 _raw/P95 公式).

    10 次 impact=0.5 → 急性 5.0 + 慢性 1.5 = 6.5, min(1.0) = 1.0.
    这是 v1.3.0 rc.2 设计: 大量事件快速 cap 1.0, 但衰减后能下来.
    """
    tracker = ConscienceTracker()
    for _ in range(10):
        tracker.record_value_conflict(
            resistance=0.5, conflict_values=["x"], tension_type="intrinsic",
            behavioral_shift=0.1, conscience_impact=0.5,
        )
    # 双通道: 急性 5.0 + 慢性 1.5 = 6.5 → cap 1.0
    assert len(tracker._window) == 10
    assert tracker._window[-1] == pytest.approx(0.5)

    pressure = tracker.get_pressure()
    assert pressure == pytest.approx(1.0)

    # alignment: 急性 0.7×0.12 + 慢性 0.3×0.12 = 0.12 总减, 但仍 cap 1.0
    tracker.record_alignment(value_name="honesty", action="repair")
    assert len(tracker._window) == 10, "v1.3.0 rc.2: alignment 不应 append _window"
    pressure_after = tracker.get_pressure()
    assert pressure_after == pytest.approx(1.0), (
        f"alignment 后急性+慢性仍 cap 1.0, 实际 {pressure_after}"
    )


def test_small_events_reflect_in_pressure():
    """v1.3.0 rc.2: 小事件 (<阈值) 直接反映在 pressure, 无 cold-start 区分."""
    tracker = ConscienceTracker()
    for _ in range(5):
        tracker.record_value_conflict(
            resistance=0.5, conflict_values=["x"], tension_type="intrinsic",
            behavioral_shift=0.1, conscience_impact=0.06,
        )
    # 5 × 0.06 = 0.3 急性 + 0.09 慢性 = 0.39
    pressure = tracker.get_pressure()
    assert pressure == pytest.approx(0.39, abs=0.01)


def test_window_size_env_var_override(monkeypatch):
    """env var EMOTION_SPIRIT_PRESSURE_WINDOW 可覆盖默认 200 (诊断用)."""
    monkeypatch.setenv("EMOTION_SPIRIT_PRESSURE_WINDOW", "50")
    tracker = ConscienceTracker()
    assert tracker._window.maxlen == 50


def test_extreme_events_decay_via_dual_channel():
    """v1.3.0 rc.2: 极端事件不主导(双通道急性快衰 + 慢性有界).

    49 次 0.1 + 1 次 1.0: 急性 5.0 + 慢性 1.5 = 6.5 → cap 1.0 (灌完立刻).
    1h tick 后: 急性衰 99.96% → 0.002, 慢性衰 8% → 1.38.
    total = 1.38, clip 1.0 → 衰减后期望显著降.
    """
    tracker = ConscienceTracker()
    for _ in range(49):
        tracker.record_value_conflict(
            resistance=0.5, conflict_values=["x"], tension_type="intrinsic",
            behavioral_shift=0.1, conscience_impact=0.1,
        )
    tracker.record_value_conflict(
        resistance=1.0, conflict_values=["x"], tension_type="intrinsic",
        behavioral_shift=1.0, conscience_impact=1.0,  # 极端
    )
    # 灌完应 cap 1.0 (急性 5.0 + 慢性 1.5 = 6.5)
    pressure_full = tracker.get_pressure()
    assert pressure_full == 1.0, f"灌完应 cap 1.0, 实际 {pressure_full}"
    # 1h tick: 急性衰到 ~0.002, 慢性衰到 ~1.38, total ~1.38 → cap 1.0 (慢性积累有界)
    tracker.tick_pressure(1.0)
    pressure_decayed = tracker.get_pressure()
    # 1h 急性衰 99.96%, 慢性衰 8%. 灌了 50 个事件, 慢性积累有界 ~1.5
    # tick 后 慢性 ~1.38, 急性 ~0.002 → total ~1.38 → cap 1.0
    # 关键: 双通道让"灌完 cap 1.0"和"长期 cap 1.0"分开
    # 进一步: 24h tick (慢性衰 85%) → 慢性 ~0.23, 急性 ~0 → total < 0.3
    tracker.tick_pressure(23.0)  # 累计 24h
    pressure_24h = tracker.get_pressure()
    assert pressure_24h < 0.5, (
        f"24h 衰减后期望 < 0.5, 实际 {pressure_24h} (双通道衰减未生效?)"
    )


def test_no_negative_pressure():
    """v1.3.0 rc.2: 减压时, 双通道 (_acute + _chronic) 不变负."""
    tracker = ConscienceTracker()
    tracker._acute_pressure = 0.0
    tracker._chronic_pressure = 0.0
    tracker.record_repair(repair_type="simple")
    assert tracker._acute_pressure >= 0.0
    assert tracker._chronic_pressure >= 0.0


def test_no_negative_pressure_via_alignment():
    """v1.3.0 rc.2: record_alignment 减压时, 双通道不变负."""
    tracker = ConscienceTracker()
    tracker._acute_pressure = 0.0
    tracker._chronic_pressure = 0.0
    tracker.record_alignment(value_name="honesty", action="repair")
    assert tracker._acute_pressure >= 0.0
    assert tracker._chronic_pressure >= 0.0


def test_get_pressure_idempotent():
    """v1.3.0 rc.2: 多次 get_pressure 调用结果一致 (lazy decay 时间差 < 1s 视为不变)."""
    tracker = ConscienceTracker()
    for _ in range(15):
        tracker.record_value_conflict(
            resistance=0.5, conflict_values=["x"], tension_type="intrinsic",
            behavioral_shift=0.1, conscience_impact=0.2,
        )
    p1 = tracker.get_pressure()
    p2 = tracker.get_pressure()
    # 短时间 (<1s) 衰减可忽略
    assert p1 == pytest.approx(p2, abs=0.01), (
        f"多次 get_pressure 应一致 (短时衰减忽略), p1={p1} p2={p2}"
    )


def test_compat_force_dynamics_range():
    """get_pressure 永远 ∈ [0, 1] (ForceDynamics 契约保持)。"""
    tracker = ConscienceTracker()
    for i in range(100):
        tracker.record_value_conflict(
            resistance=0.5, conflict_values=["x"], tension_type="intrinsic",
            behavioral_shift=0.1, conscience_impact=0.5,
        )
    pressure = tracker.get_pressure()
    assert 0.0 <= pressure <= 1.0
