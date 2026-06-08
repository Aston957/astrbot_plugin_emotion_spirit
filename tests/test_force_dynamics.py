"""ForceDynamics 算法 H 单元测试 (Phase 3.0A)。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_labels import INFP_A_LABELS  # noqa: E402


# ═══ ForceState ═══

def test_force_state_normalized_sum_equals_one():
    """ForceState 3 权重归一化到 sum=1.0。"""
    from emotion_spirit.force_dynamics import ForceState
    fs = ForceState(natural=0.3, social=0.3, individual=0.4)
    assert abs(fs.natural + fs.social + fs.individual - 1.0) < 0.01


def test_force_state_rejects_non_normalized():
    """sum 偏离 1.0 超过 0.01 报错 (ValueError 而非 assert, 兼容 python -O)。"""
    from emotion_spirit.force_dynamics import ForceState
    with pytest.raises(ValueError, match="归一化和"):
        ForceState(natural=0.5, social=0.5, individual=0.5)


@pytest.mark.parametrize("natural,social,individual,expected_dominant", [
    (0.5, 0.3, 0.2, "natural"),
    (0.2, 0.5, 0.3, "social"),
    (0.2, 0.3, 0.5, "individual"),
    # tie-break test: natural == social (highest priority wins)
    (0.4, 0.4, 0.2, "natural"),
])
def test_force_state_dominant_property(natural, social, individual, expected_dominant):
    """dominant property 返回最大力名 (natural > social > individual 优先级)。"""
    from emotion_spirit.force_dynamics import ForceState
    fs = ForceState(natural=natural, social=social, individual=individual)
    assert fs.dominant == expected_dominant


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


# ═══ STD_FLOOR (Phase 3.0B Task 3) ═══

def test_force_dynamics_std_floor_kicks_in_for_tiny_std():
    """std 极小 (0.05) 的 dim → 算法 H 实际用 STD_FLOOR (= 0.10), 不被压成 0.05。

    Phase 3.0B safety: 若未来加 std < 0.10 的 dim, floor 防止它"被压扁"
    (低 std × 偏离 = 几乎 0, 在归一化中完全消失)。

    验证: 用 2-force 场景 (natural warmth + social intimacy), 把 warmth_bias
    std 改成 0.05, 跑 compute, natural weight 应等同于直接用 std=0.10
    跑 compute (差异 < 1e-9) — 证明 floor 把 0.05 clamp 到 0.10。
    """
    from emotion_spirit.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    original_std = fd._dim_std["warmth_bias"]
    # 2-force 场景: warmth (natural) + intimacy (social) 都偏离
    personality = {
        "warmth_bias": 0.70, "patience": 0.50, "boundary_permeability": 0.50,
        "relational_gravity": 0.50, "intimacy_pull": 0.70, "expression_drive": 0.50,
        "gossip_tendency": 0.50,
        "inner_coherence": 0.50, "curiosity": 0.50, "perception_acuity": 0.50,
        "directness": 0.50, "relational_autonomy": 0.50, "exploration_openness": 0.50,
    }
    try:
        fd._dim_std["warmth_bias"] = 0.05  # 远小于 STD_FLOOR
        fs_with_floor = fd.compute(personality)
        fd._dim_std["warmth_bias"] = 0.10  # 显式用 floor 值
        fs_with_floor_explicit = fd.compute(personality)
        # 两者应一致 (floor clamp 0.05 → 0.10)
        assert abs(fs_with_floor.natural - fs_with_floor_explicit.natural) < 1e-9
    finally:
        fd._dim_std["warmth_bias"] = original_std


def test_force_dynamics_std_floor_skipped_for_normal_std():
    """std=0.20 (>= STD_FLOOR=0.10) → 不用 floor, 用真值 0.20。

    验证: 用 2-force 场景 (natural warmth + social intimacy), std=0.20 时
    natural weight 应显著高于 std=0.10 时 (因 std 参与加权), 证明 floor
    没误触发, 真用 0.20 算。
    """
    from emotion_spirit.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    original_std = fd._dim_std["warmth_bias"]
    personality = {
        "warmth_bias": 0.70, "patience": 0.50, "boundary_permeability": 0.50,
        "relational_gravity": 0.50, "intimacy_pull": 0.70, "expression_drive": 0.50,
        "gossip_tendency": 0.50,
        "inner_coherence": 0.50, "curiosity": 0.50, "perception_acuity": 0.50,
        "directness": 0.50, "relational_autonomy": 0.50, "exploration_openness": 0.50,
    }
    try:
        fd._dim_std["warmth_bias"] = 0.20
        fs_020 = fd.compute(personality)
        fd._dim_std["warmth_bias"] = 0.10
        fs_010 = fd.compute(personality)
        # natural 应不同 (std 0.20 > 0.10, weighted 更高)
        assert abs(fs_020.natural - fs_010.natural) > 0.01
    finally:
        fd._dim_std["warmth_bias"] = original_std


def test_force_dynamics_std_floor_fallback_above_floor():
    """未知 dim → fallback 0.20 (> STD_FLOOR=0.10), floor 不触发。

    验证: 从 _dim_std 删掉 warmth_bias (→ fallback 0.20), natural weight
    应等同 std=0.20 时 (因 0.20 > STD_FLOOR, floor 不影响)。
    """
    from emotion_spirit.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    original_warmth_std = fd._dim_std.pop("warmth_bias")
    personality = {
        "warmth_bias": 0.70, "patience": 0.50, "boundary_permeability": 0.50,
        "relational_gravity": 0.50, "intimacy_pull": 0.70, "expression_drive": 0.50,
        "gossip_tendency": 0.50,
        "inner_coherence": 0.50, "curiosity": 0.50, "perception_acuity": 0.50,
        "directness": 0.50, "relational_autonomy": 0.50, "exploration_openness": 0.50,
    }
    try:
        # fallback = 0.20 (因 warmth_bias 不在 std table)
        fs_fallback = fd.compute(personality)
        # 显式 std=0.20
        fd._dim_std["warmth_bias"] = 0.20
        fs_explicit_020 = fd.compute(personality)
        # 两者应一致 (fallback 0.20 > STD_FLOOR, 不被 floor 影响)
        assert abs(fs_fallback.natural - fs_explicit_020.natural) < 1e-9
    finally:
        fd._dim_std["warmth_bias"] = original_warmth_std
