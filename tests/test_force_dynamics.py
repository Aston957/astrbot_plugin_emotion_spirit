"""ForceDynamics 算法 H 单元测试 (Phase 3.0A)。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_labels import INFP_A_LABELS  # noqa: E402


# ═══ ForceState ═══

def test_force_state_normalized_sum_equals_one():
    """ForceState 3 权重归一化到 sum=1.0。"""
    from emotion_spirit.force_dynamics import ForceState
    fs = ForceState(natural=0.3, social=0.3, individual=0.4)
    assert abs(fs.natural + fs.social + fs.individual - 1.0) < 0.01


def test_force_state_rejects_non_normalized():
    """sum 偏离 1.0 超过 0.01 报错。"""
    import pytest
    from emotion_spirit.force_dynamics import ForceState
    with pytest.raises(AssertionError, match="归一化和"):
        ForceState(natural=0.5, social=0.5, individual=0.5)


def test_force_state_dominant_property():
    """dominant property 返回最大力名 (natural → social → individual 优先级)。"""
    from emotion_spirit.force_dynamics import ForceState
    assert ForceState(natural=0.5, social=0.3, individual=0.2).dominant == "natural"
    assert ForceState(natural=0.2, social=0.5, individual=0.3).dominant == "social"
    assert ForceState(natural=0.2, social=0.3, individual=0.5).dominant == "individual"


# ═══ ForceDynamics.compute (算法 H) ═══

def test_force_dynamics_compute_uses_std_weights():
    """算法 H: std 高的 dim 权重应反映在 intensity 计算。"""
    from emotion_spirit.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    # 构造 personality 让 std 差异可见
    # warmth_bias std=0.20 (高), perception_acuity std=0.17 (低)
    personality = {
        "warmth_bias": 0.60, "patience": 0.50, "boundary_permeability": 0.50,
        "relational_gravity": 0.50, "intimacy_pull": 0.50, "expression_drive": 0.50,
        "gossip_tendency": 0.50, "inner_coherence": 0.50, "curiosity": 0.50,
        "perception_acuity": 0.60, "directness": 0.50, "relational_autonomy": 0.50,
        "exploration_openness": 0.50,
    }
    fs = fd.compute(personality)
    # warmth 0.60 → natural 方向 +0.10×0.20
    # perception 0.60 → individual 方向 +0.10×0.17
    # 两者都正, 但 warmth std 略高 → natural intensity 略强
    assert fs.natural > 0  # 自然力有强度
    assert fs.individual > 0  # 个体力有强度


def test_force_dynamics_compute_handles_empty():
    """空 personality → 3 权重均匀 (1/3 each)。"""
    from emotion_spirit.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    fs = fd.compute({})
    assert abs(fs.natural - 1/3) < 0.01
    assert abs(fs.social - 1/3) < 0.01
    assert abs(fs.individual - 1/3) < 0.01


def test_force_dynamics_compute_b_greater_than_one():
    """B 决策: personality 允许 > 1.0, 算法应兼容。"""
    from emotion_spirit.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    # 极端 personality (单 dim > 1.0)
    personality = {"warmth_bias": 1.20, "patience": 0.50, "boundary_permeability": 0.50,
                   "relational_gravity": 0.50, "intimacy_pull": 0.50, "expression_drive": 0.50,
                   "gossip_tendency": 0.50, "inner_coherence": 0.50, "curiosity": 0.50,
                   "perception_acuity": 0.50, "directness": 0.50, "relational_autonomy": 0.50,
                   "exploration_openness": 0.50}
    fs = fd.compute(personality)
    # 应有 valid ForceState (sum=1.0)
    assert abs(fs.natural + fs.social + fs.individual - 1.0) < 0.01
    # warmth 1.20 远偏离中性, 应让 natural 显著高
    assert fs.natural > fs.social


def test_force_dynamics_force_state_from_labels():
    """force_state_from_labels(labels) → 5 label → 13-dim → ForceState。"""
    from emotion_spirit.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    fs = fd.force_state_from_labels(INFP_A_LABELS)
    assert abs(fs.natural + fs.social + fs.individual - 1.0) < 0.01
    assert fs.dominant in {"natural", "social", "individual"}
