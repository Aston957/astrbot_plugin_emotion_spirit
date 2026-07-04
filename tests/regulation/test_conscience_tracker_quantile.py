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
    """冷启动后 (>10 帧), get_pressure 用 P95 归一化, 非 clip raw.

    v1.2.11 Bug-G 修后场景: _window 改增量语义 (单次 conscience_impact).
    10 帧 impact=0.5 → raw=5.0, _window=[0.5]*10, P95=0.5.
    ratio = 5.0/0.5 = 10.0 → cap 1.0 (10 个事件累计已饱和, 期望行为).

    关键不变量 (增量语义):
    1. _window 含 10 项 (not 11) — alignment 不入 window
    2. P95 = 0.5 (单次事件强度), 不是 raw 累计 5.0
    3. alignment 后 _raw_pressure 下降, P95 不变 (验证 Bug-G 修复)
    """
    tracker = ConscienceTracker()
    for _ in range(10):
        tracker.record_value_conflict(
            resistance=0.5, conflict_values=["x"], tension_type="intrinsic",
            behavioral_shift=0.1, conscience_impact=0.5,
        )
    # Bug-G 增量语义: window 含 10 项单次增量, 每项 0.5 (not 累计值 5.0)
    assert len(tracker._window) == 10
    assert tracker._window[-1] == pytest.approx(0.5)

    pressure = tracker.get_pressure()
    # 10 × 0.5 = 5.0 / 0.5 = 10 → cap 1.0 (saturated by design)
    assert pressure == pytest.approx(1.0)

    # alignment: raw 减 0.12 → 4.88, 但 _window 不变 (alignment 不入 window per Bug-G)
    tracker.record_alignment(value_name="honesty", action="repair")
    assert len(tracker._window) == 10, "Bug-G: alignment 不应 append _window"
    # 仍 cap 1.0 (raw=4.88 仍 >> P95=0.5)
    pressure_after = tracker.get_pressure()
    assert pressure_after == pytest.approx(1.0), (
        f"alignment 后 _raw 下降但 _window 不变, ratio 仍 > 1 → 应 cap 1.0, 实际 {pressure_after}"
    )


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
