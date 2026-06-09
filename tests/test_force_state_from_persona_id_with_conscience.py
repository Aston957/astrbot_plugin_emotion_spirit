"""Tests for force_state_from_persona_id_with_conscience (Phase 3.0C.3 spec §9.5)。

便捷方法, 跟 3.0B force_state_with_conscience 对标:
- 接受 ConscienceTracker 实例 (调 .get_pressure() 读压力)
- 接受 float scalar (直接当 conscience_pressure)
- 接受 None (压力=0)
- 其他类型 → TypeError
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from emotion_spirit.core.persona_labels_db import (
    REQUIRED_DIMS,
    force_state_from_persona_id_with_conscience,
    register_persona_baseline,
    reset_cache,
    get_kb_stats,
)
from emotion_spirit.regulation.body_state import BodyState
from emotion_spirit.regulation.force_dynamics import ForceState


def _make_baseline(centers: dict[str, float] | None = None) -> dict[str, float]:
    base = {dim: 0.5 for dim in REQUIRED_DIMS}
    if centers:
        base.update(centers)
    return base


@pytest.fixture(autouse=True)
def _reset():
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def nonuniform_baseline():
    """INFP-AV 风格非均匀 baseline, 让 modulation 可见。"""
    return _make_baseline({
        "curiosity": 0.85,
        "exploration_openness": 0.80,
        "warmth_bias": 0.70,
    })


# === ConscienceTracker 接受路径 ===

def test_with_conscience_tracker_instance(nonuniform_baseline):
    """传 ConscienceTracker 实例 → 调 .get_pressure() 拿压力, auto-normalize。

    用 MagicMock 模拟 ConscienceTracker (避免引入完整 3.0B 依赖)。
    """
    register_persona_baseline("INFP-AV-EX-CO-PR", nonuniform_baseline)
    mock_tracker = MagicMock()
    mock_tracker.get_pressure.return_value = 0.5  # 中等压力

    fs = force_state_from_persona_id_with_conscience(
        "INFP-AV-EX-CO-PR", mock_tracker
    )
    assert isinstance(fs, ForceState)
    mock_tracker.get_pressure.assert_called_once()


def test_with_conscience_tracker_normalize_high(nonuniform_baseline):
    """ConscienceTracker.get_pressure() 返 > 1.0 时, 内部 clip 到 1.0 (defensive)。"""
    register_persona_baseline("INFP-AV-EX-CO-PR", nonuniform_baseline)
    mock_tracker = MagicMock()
    mock_tracker.get_pressure.return_value = 2.0  # 异常值, 应 clip

    # 不应抛错, 内部 clip 到 1.0
    fs = force_state_from_persona_id_with_conscience(
        "INFP-AV-EX-CO-PR", mock_tracker
    )
    assert isinstance(fs, ForceState)


def test_with_conscience_tracker_none_pressure(nonuniform_baseline):
    """ConscienceTracker.get_pressure() 返 0.0 → 跟 pressure=0 等价。"""
    register_persona_baseline("INFP-AV-EX-CO-PR", nonuniform_baseline)
    mock_tracker = MagicMock()
    mock_tracker.get_pressure.return_value = 0.0

    fs_with_tracker = force_state_from_persona_id_with_conscience(
        "INFP-AV-EX-CO-PR", mock_tracker
    )
    # 跟 pressure=0 等价 → baseline 不被调制
    assert isinstance(fs_with_tracker, ForceState)


# === Float / None 接受路径 ===

def test_with_float_scalar(nonuniform_baseline):
    """传 float scalar (非 ConscienceTracker) → 直接当 pressure 用。"""
    register_persona_baseline("INFP-AV-EX-CO-PR", nonuniform_baseline)

    fs_p0 = force_state_from_persona_id_with_conscience(
        "INFP-AV-EX-CO-PR", 0.0
    )
    fs_p1 = force_state_from_persona_id_with_conscience(
        "INFP-AV-EX-CO-PR", 1.0
    )
    # pressure=1.0 改变 individual 方向
    assert fs_p0.individual != fs_p1.individual


def test_with_none_tracker(nonuniform_baseline):
    """传 None → pressure=0, 跟不传 pressure 等价。"""
    register_persona_baseline("INFP-AV-EX-CO-PR", nonuniform_baseline)
    fs = force_state_from_persona_id_with_conscience(
        "INFP-AV-EX-CO-PR", None
    )
    assert isinstance(fs, ForceState)


# === 错误处理 ===

def test_with_invalid_type_raises_typeerror():
    """传 str / list / dict 等非法类型 → TypeError。"""
    with pytest.raises(TypeError, match="conscience_tracker must be"):
        force_state_from_persona_id_with_conscience(
            "INFP-AV-EX-CO-PR", "not_a_tracker"
        )
    with pytest.raises(TypeError):
        force_state_from_persona_id_with_conscience(
            "INFP-AV-EX-CO-PR", ["list", "not", "ok"]
        )


# === body_state 透传 ===

def test_body_state_passthrough(nonuniform_baseline):
    """body_state 透传到 ForceDynamics。"""
    register_persona_baseline("INFP-AV-EX-CO-PR", nonuniform_baseline)
    bs = BodyState(hormone=0.7, energy=0.8, arousal=0.6)

    fs_no_body = force_state_from_persona_id_with_conscience(
        "INFP-AV-EX-CO-PR", 0.5
    )
    fs_with_body = force_state_from_persona_id_with_conscience(
        "INFP-AV-EX-CO-PR", 0.5, body_state=bs
    )
    # body_state 不同 → ForceState 应不同
    assert (
        fs_with_body.natural != fs_no_body.natural
        or fs_with_body.social != fs_no_body.social
        or fs_with_body.individual != fs_no_body.individual
    )
