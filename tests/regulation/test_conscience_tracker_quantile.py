"""Phase 4 C1 — ConscienceTracker 滑动窗口 P95 归一化 (B2 算法)"""
import pytest

from emotion_spirit.regulation.superego import ConscienceTracker


# 清除 env var 防止测试间污染
@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    monkeypatch.delenv("EMOTION_SPIRIT_PRESSURE_WINDOW", raising=False)
    yield


def test_window_appends_on_record():
    """每次 record_* 写时, _window 应同步 append 当前 raw_pressure。"""
    tracker = ConscienceTracker()
    initial_window_len = len(tracker._window)
    tracker.record_value_conflict(
        resistance=0.5, conflict_values=["honesty"], tension_type="intrinsic",
        behavioral_shift=0.1, conscience_impact=0.3,
    )
    assert len(tracker._window) == initial_window_len + 1
    assert tracker._window[-1] == pytest.approx(0.3, abs=0.01)


def test_get_pressure_quantile_normalized():
    """冷启动后 (>10 帧), get_pressure 返回 raw_pressure / P95, 非 clip。

    场景: 10 帧 conscience_impact=0.5 → raw=5.0; 然后 1 次 record_alignment
    (alignment_base_relief=0.12) → raw=4.88, window 末尾追加 4.88。
    Window: [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 4.88]
    P95 idx = int(11 * 0.95) = 10, sorted[10] = 5.0
    normalized = 4.88 / 5.0 = 0.976 (NOT clipped, NOT raw=4.88)
    """
    tracker = ConscienceTracker()
    for _ in range(10):
        tracker.record_value_conflict(
            resistance=0.5, conflict_values=["x"], tension_type="intrinsic",
            behavioral_shift=0.1, conscience_impact=0.5,
        )
    tracker.record_alignment(value_name="honesty", action="repair")
    pressure = tracker.get_pressure()
    assert pressure == pytest.approx(0.976, abs=0.01)


def test_cold_start_returns_raw():
    """< 10 帧时, get_pressure 直接返回 raw_pressure (degraded mode)。"""
    tracker = ConscienceTracker()
    for _ in range(5):
        tracker.record_value_conflict(
            resistance=0.5, conflict_values=["x"], tension_type="intrinsic",
            behavioral_shift=0.1, conscience_impact=0.06,
        )
    # 5 × 0.06 = 0.3
    pressure = tracker.get_pressure()
    assert pressure == pytest.approx(0.3, abs=0.01)


def test_window_size_env_var_override(monkeypatch):
    """env var EMOTION_SPIRIT_PRESSURE_WINDOW 可覆盖默认 200。"""
    monkeypatch.setenv("EMOTION_SPIRIT_PRESSURE_WINDOW", "50")
    tracker = ConscienceTracker()
    assert tracker._window.maxlen == 50


def test_extreme_events_dont_dominate():
    """单一极端事件不主导归一化 (P95 给 5% headroom, 50 帧窗口)。

    49 帧常态 (conscience_impact=0.1 → raw=4.9) + 1 帧极端 (impact=1.0 → raw=5.9) = 50 帧
    P95 idx = int(50 * 0.95) = 47, sorted[47] = 0.1 (NOT the extreme 1.0)
    normalized = 5.9 / 0.1 = 59 → clip 1.0
    """
    tracker = ConscienceTracker()
    for _ in range(49):
        tracker.record_value_conflict(
            resistance=0.5, conflict_values=["x"], tension_type="intrinsic",
            behavioral_shift=0.1, conscience_impact=0.1,
        )
    tracker.record_value_conflict(
        resistance=1.0, conflict_values=["x"], tension_type="intrinsic",
        behavioral_shift=1.0, conscience_impact=1.0,  # 极端但非 raw=10
    )
    # 验证 P95 不是 max (5% headroom 生效)
    assert tracker._window_quantile < tracker._window[-1], \
        f"P95 ({tracker._window_quantile}) 应小于 max ({tracker._window[-1]})"
    # 极端事件导致 raw/P95 = 5.9/0.1 = 59 → clip 1.0
    pressure = tracker.get_pressure()
    assert pressure == 1.0


def test_no_negative_pressure():
    """减压时, raw_pressure 不变负。"""
    tracker = ConscienceTracker()
    tracker._raw_pressure = 0.0
    tracker.record_repair(repair_type="simple")
    assert tracker._raw_pressure >= 0.0


def test_no_negative_pressure_via_alignment():
    """record_alignment 减压时, raw_pressure 不变负。"""
    tracker = ConscienceTracker()
    tracker._raw_pressure = 0.0
    tracker.record_alignment(value_name="honesty", action="repair")
    assert tracker._raw_pressure >= 0.0


def test_p95_caching():
    """多次 get_pressure 不重复排序 (window_quantile 缓存)。"""
    tracker = ConscienceTracker()
    for _ in range(15):
        tracker.record_value_conflict(
            resistance=0.5, conflict_values=["x"], tension_type="intrinsic",
            behavioral_shift=0.1, conscience_impact=0.2,
        )
    p1 = tracker.get_pressure()
    cached_quantile = tracker._window_quantile
    assert cached_quantile > 0.0
    p2 = tracker.get_pressure()
    assert tracker._window_quantile == cached_quantile
    assert p1 == p2


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
