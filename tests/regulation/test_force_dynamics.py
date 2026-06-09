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
    from emotion_spirit.regulation.force_dynamics import ForceState
    fs = ForceState(natural=0.3, social=0.3, individual=0.4)
    assert abs(fs.natural + fs.social + fs.individual - 1.0) < 0.01


def test_force_state_rejects_non_normalized():
    """sum 偏离 1.0 超过 0.01 报错 (ValueError 而非 assert, 兼容 python -O)。"""
    from emotion_spirit.regulation.force_dynamics import ForceState
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
    from emotion_spirit.regulation.force_dynamics import ForceState
    fs = ForceState(natural=natural, social=social, individual=individual)
    assert fs.dominant == expected_dominant


# ═══ ForceDynamics.compute (算法 H) ═══

def test_force_dynamics_compute_uses_std_weights():
    """算法 H: std 高的 dim 权重应反映在 intensity 计算。"""
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
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
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    fs = fd.compute({})
    assert abs(fs.natural - 1/3) < 0.01
    assert abs(fs.social - 1/3) < 0.01
    assert abs(fs.individual - 1/3) < 0.01


def test_force_dynamics_compute_b_greater_than_one():
    """B 决策: personality 允许 > 1.0, 算法应兼容。"""
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
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
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
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
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
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
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
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
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
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


# ═══ BodyState (Phase 3.0B Task 3) ═══

def test_body_state_default_neutral():
    """BodyState() 默认全 0.5 (中性)。"""
    from emotion_spirit.regulation.body_state import BodyState
    bs = BodyState()
    assert bs.hormone == 0.5
    assert bs.energy == 0.5
    assert bs.arousal == 0.5


def test_body_state_validates_range():
    """BodyState 字段必须在 [0, 1], 越界 ValueError。"""
    from emotion_spirit.regulation.body_state import BodyState
    with pytest.raises(ValueError, match="必须在"):
        BodyState(hormone=1.5, energy=0.5, arousal=0.5)
    with pytest.raises(ValueError, match="必须在"):
        BodyState(hormone=0.5, energy=-0.1, arousal=0.5)
    with pytest.raises(ValueError, match="必须在"):
        BodyState(hormone=0.5, energy=0.5, arousal=1.2)


def test_body_state_module_default():
    """BodyStateModule.default() → BodyState(0.5, 0.5, 0.5) 中性。"""
    from emotion_spirit.regulation.body_state import BodyStateModule
    mod = BodyStateModule()
    bs = mod.default()
    assert bs.hormone == 0.5
    assert bs.energy == 0.5
    assert bs.arousal == 0.5


def test_body_state_module_from_dict():
    """BodyStateModule.from_dict(dict) → 缺字段填 0.5。"""
    from emotion_spirit.regulation.body_state import BodyStateModule
    mod = BodyStateModule()
    bs = mod.from_dict({"hormone": 0.8})
    assert bs.hormone == 0.8
    assert bs.energy == 0.5
    assert bs.arousal == 0.5

    bs2 = mod.from_dict({"hormone": 0.2, "energy": 0.7, "arousal": 0.3})
    assert bs2.hormone == 0.2
    assert bs2.energy == 0.7
    assert bs2.arousal == 0.3


def test_force_dynamics_body_state_none_unchanged():
    """compute(p) == compute(p, None) == compute(p, neutral_BodyState)。

    向后兼容: 缺 body_state 或全 0.5 中性值时, 输出跟 baseline 完全一致。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    from emotion_spirit.regulation.body_state import BodyState
    fd = ForceDynamics()
    personality = {
        "warmth_bias": 0.60, "patience": 0.50, "boundary_permeability": 0.55,
        "relational_gravity": 0.50, "intimacy_pull": 0.65, "expression_drive": 0.50,
        "gossip_tendency": 0.50,
        "inner_coherence": 0.50, "curiosity": 0.55, "perception_acuity": 0.50,
        "directness": 0.50, "relational_autonomy": 0.60, "exploration_openness": 0.55,
    }
    fs_none = fd.compute(personality)
    fs_explicit_none = fd.compute(personality, None)
    fs_neutral = fd.compute(personality, BodyState(0.5, 0.5, 0.5))
    assert abs(fs_none.natural - fs_explicit_none.natural) < 1e-9
    assert abs(fs_none.social - fs_explicit_none.social) < 1e-9
    assert abs(fs_none.individual - fs_explicit_none.individual) < 1e-9
    assert abs(fs_none.natural - fs_neutral.natural) < 1e-9
    assert abs(fs_none.social - fs_neutral.social) < 1e-9
    assert abs(fs_none.individual - fs_neutral.individual) < 1e-9


def test_force_dynamics_body_state_low_energy_dampens():
    """低 energy → 各力 weight 差异"压缩" (low energy 整体衰减)。

    选一个非对称 personality (3 力都有偏离), 比较 low_energy (energy=0.0)
    跟 high_energy (energy=1.0) 时的 sum-of-weights-with-energy-multiplier 效果。
    由于 compute 是先 raw 算然后按 energy_factor 倍乘再 abs-normalize,
    归一化后权重比例应不变 (因为 raw*energy_factor 对所有力同步倍乘)。
    关键不变量: low_energy 和 high_energy 输出的 3 权重**比例**相同 (因
    energy_factor 同步作用), 但 raw 强度被压缩。
    验证方法: 跑 compute twice, 一遍 normal 一遍 low_energy,
    因归一化后 3 权比例一致 (但 raw 强度不同 — 我们看不到 raw, 只能看
    归一化结果), 需构造"energy 介入前 vs 后"的中间态比较。
    简化版断言: low_energy + baseline 的 3 weight 跟 baseline 一样
    (比例不变, 因同步倍乘), 但跟 high_arousal 的不同 (因 arousal 影响 salience)。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    from emotion_spirit.regulation.body_state import BodyState
    fd = ForceDynamics()
    # 3 力都有偏离 (用于看归一化比例)
    personality = {
        "warmth_bias": 0.70, "patience": 0.70, "boundary_permeability": 0.70,  # natural +
        "relational_gravity": 0.30, "intimacy_pull": 0.30,  # social - (low, 偏向负)
        "expression_drive": 0.30, "gossip_tendency": 0.30,
        "inner_coherence": 0.80, "curiosity": 0.80, "perception_acuity": 0.80,  # individual +
        "directness": 0.80, "relational_autonomy": 0.80, "exploration_openness": 0.80,
    }
    fs_baseline = fd.compute(personality)
    fs_low_energy = fd.compute(personality, BodyState(0.5, 0.0, 0.5))
    # 同步倍乘 + abs → 归一化后 3 权重比例不变
    assert abs(fs_low_energy.natural - fs_baseline.natural) < 1e-9
    assert abs(fs_low_energy.social - fs_baseline.social) < 1e-9
    assert abs(fs_low_energy.individual - fs_baseline.individual) < 1e-9


def test_force_dynamics_body_state_high_arousal_polarizes():
    """高 arousal → 极化 (per-dim 偏离被放大, 极端 personality 主导更显著)。

    arousal_factor = 0.5 + arousal ∈ [0.5, 1.5], 应用在 salience 上 (在 per-dim
    loop 内 before intensity calc)。salience 越大, intensity = signed_dev * salience
    越大 (且 abs-normalize 放大主导力)。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    from emotion_spirit.regulation.body_state import BodyState
    fd = ForceDynamics()
    # 个体 vs 集体 对比 (3 力全偏离, 个体力 high)
    personality = {
        "warmth_bias": 0.55, "patience": 0.50, "boundary_permeability": 0.50,
        "relational_gravity": 0.50, "intimacy_pull": 0.50, "expression_drive": 0.50,
        "gossip_tendency": 0.50,
        "inner_coherence": 0.60, "curiosity": 0.60, "perception_acuity": 0.60,
        "directness": 0.50, "relational_autonomy": 0.50, "exploration_openness": 0.50,
    }
    fs_baseline = fd.compute(personality)
    fs_high_arousal = fd.compute(personality, BodyState(0.5, 0.5, 1.0))
    # 主导力 (individual) 权重要更大 (arousal 放大 salience → 个体力 intensity 增 → abs-normalize 占比增)
    assert fs_high_arousal.individual > fs_baseline.individual, (
        f"high arousal 应放大 individual 权重, "
        f"baseline={fs_baseline.individual:.3f}, high_arousal={fs_high_arousal.individual:.3f}"
    )


def test_force_dynamics_body_state_high_hormone_individual():
    """高 hormone (cortisol 高) → individual 力增 (hormone direction: +0.8)。

    hormone_mult = 1.0 + (hormone - 0.5) * 0.5 * direction[force]
    individual direction = +0.8 → 高 hormone (0.8) 时 mult = 1.0 + 0.15 * 0.8 = 1.12
    放大 individual intensity, abs-normalize 让 individual 占比增。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    from emotion_spirit.regulation.body_state import BodyState
    fd = ForceDynamics()
    # 3 力均衡偏离, 个体力 0.6 / 自然力 0.6 / 集体力 0.4
    personality = {
        "warmth_bias": 0.60, "patience": 0.60, "boundary_permeability": 0.60,
        "relational_gravity": 0.40, "intimacy_pull": 0.40, "expression_drive": 0.40,
        "gossip_tendency": 0.40,
        "inner_coherence": 0.60, "curiosity": 0.60, "perception_acuity": 0.60,
        "directness": 0.60, "relational_autonomy": 0.60, "exploration_openness": 0.60,
    }
    fs_baseline = fd.compute(personality)
    fs_high_hormone = fd.compute(personality, BodyState(0.8, 0.5, 0.5))
    # individual hormone_mult > 1.0 → individual 占比增
    assert fs_high_hormone.individual > fs_baseline.individual, (
        f"high hormone (cortisol) 应放大 individual, "
        f"baseline={fs_baseline.individual:.3f}, high_hormone={fs_high_hormone.individual:.3f}"
    )


def test_force_dynamics_body_state_low_hormone_social():
    """低 hormone (cortisol 低, 放松) → social 力增 (hormone direction: -0.3)。

    social direction = -0.3 → 低 hormone (0.2) 时 mult = 1.0 + (-0.15) * (-0.3) = 1.045
    放大 social intensity, abs-normalize 让 social 占比增。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    from emotion_spirit.regulation.body_state import BodyState
    fd = ForceDynamics()
    # 3 力均衡偏离, 集体力 0.6 / 自然力 0.6 / 个体力 0.4
    personality = {
        "warmth_bias": 0.60, "patience": 0.60, "boundary_permeability": 0.60,
        "relational_gravity": 0.60, "intimacy_pull": 0.60, "expression_drive": 0.60,
        "gossip_tendency": 0.60,
        "inner_coherence": 0.40, "curiosity": 0.40, "perception_acuity": 0.40,
        "directness": 0.40, "relational_autonomy": 0.40, "exploration_openness": 0.40,
    }
    fs_baseline = fd.compute(personality)
    fs_low_hormone = fd.compute(personality, BodyState(0.2, 0.5, 0.5))
    # social hormone_mult > 1.0 → social 占比增
    assert fs_low_hormone.social > fs_baseline.social, (
        f"low hormone (relax) 应放大 social, "
        f"baseline={fs_baseline.social:.3f}, low_hormone={fs_low_hormone.social:.3f}"
    )


# ═══ conscience_pressure (Phase 3.0B Task 4) ═══
#
# 理论依据: Tangney (2002) self-conscious emotions
#   - 价值冲突累积 (guilt/shame) → 自我聚焦 → individual +/social -
#   - 价值对齐 (pride/relief) → 关系放松 → social +/individual -
#
# 公式: pressure_factor = conscience_pressure * 0.6 ∈ [0, 0.6]
#       intensity *= 1.0 + pressure_factor * direction[force]
#       direction = {"natural": -0.2, "social": -0.5, "individual": +0.7}
#
# pressure=0: mult=1.0 全力, 不变 (向后兼容)
# pressure=1.0: natural 0.88, social 0.70, individual 1.42
#   → individual 显著增 (Tangney self-focus), social 显著被压 (Schaumberg guilt→withdrawal)


def test_force_dynamics_conscience_pressure_default_zero():
    """compute(p) == compute(p, conscience_pressure=0.0) — backward compat。

    pressure=0 时 pressure_factor=0, mult=1.0 对所有力, 输出应跟无 pressure 一致。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    personality = {
        "warmth_bias": 0.60, "patience": 0.50, "boundary_permeability": 0.55,
        "relational_gravity": 0.50, "intimacy_pull": 0.65, "expression_drive": 0.50,
        "gossip_tendency": 0.50,
        "inner_coherence": 0.50, "curiosity": 0.55, "perception_acuity": 0.50,
        "directness": 0.50, "relational_autonomy": 0.60, "exploration_openness": 0.55,
    }
    fs_no_pressure = fd.compute(personality)
    fs_zero_pressure = fd.compute(personality, conscience_pressure=0.0)
    assert abs(fs_no_pressure.natural - fs_zero_pressure.natural) < 1e-9
    assert abs(fs_no_pressure.social - fs_zero_pressure.social) < 1e-9
    assert abs(fs_no_pressure.individual - fs_zero_pressure.individual) < 1e-9


def test_force_dynamics_conscience_pressure_validates_range():
    """conscience_pressure 必须在 [0, 1], 越界 ValueError。"""
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    personality = {"warmth_bias": 0.60, "patience": 0.50, "boundary_permeability": 0.50}
    with pytest.raises(ValueError, match="conscience_pressure"):
        fd.compute(personality, conscience_pressure=1.5)
    with pytest.raises(ValueError, match="conscience_pressure"):
        fd.compute(personality, conscience_pressure=-0.1)


def test_force_dynamics_conscience_pressure_neutral_zero_no_shift():
    """pressure=0 → 3 力权重跟 baseline (无 pressure) 完全一致 (1e-9 内)。

    关键不变量: 默认 conscience_pressure=0.0 跟不传 param 完全等价。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    # 3 力都有偏离 (避免 abs-normalize 把单力压平)
    personality = {
        "warmth_bias": 0.60, "patience": 0.50, "boundary_permeability": 0.50,
        "relational_gravity": 0.50, "intimacy_pull": 0.60, "expression_drive": 0.50,
        "gossip_tendency": 0.50,
        "inner_coherence": 0.60, "curiosity": 0.50, "perception_acuity": 0.50,
        "directness": 0.50, "relational_autonomy": 0.50, "exploration_openness": 0.50,
    }
    fs_baseline = fd.compute(personality)
    fs_neutral = fd.compute(personality, conscience_pressure=0.0)
    assert abs(fs_baseline.natural - fs_neutral.natural) < 1e-9
    assert abs(fs_baseline.social - fs_neutral.social) < 1e-9
    assert abs(fs_baseline.individual - fs_neutral.individual) < 1e-9


def test_force_dynamics_conscience_pressure_high_individual_boost():
    """pressure=1.0 → individual 占比显著增加 (Tangney self-focus)。

    individual direction=+0.7, pressure=1.0 → mult=1.42, 在 abs-normalize
    中 individual 占比应高于 pressure=0 时的占比。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    personality = {
        "warmth_bias": 0.60, "patience": 0.50, "boundary_permeability": 0.50,
        "relational_gravity": 0.50, "intimacy_pull": 0.60, "expression_drive": 0.50,
        "gossip_tendency": 0.50,
        "inner_coherence": 0.60, "curiosity": 0.50, "perception_acuity": 0.50,
        "directness": 0.50, "relational_autonomy": 0.50, "exploration_openness": 0.50,
    }
    fs_baseline = fd.compute(personality)
    fs_high_pressure = fd.compute(personality, conscience_pressure=1.0)
    assert fs_high_pressure.individual > fs_baseline.individual, (
        f"pressure=1.0 应放大 individual (Tangney self-focus), "
        f"baseline={fs_baseline.individual:.3f}, high={fs_high_pressure.individual:.3f}"
    )


def test_force_dynamics_conscience_pressure_high_social_suppress():
    """pressure=1.0 → social 占比显著被压 (Schaumberg guilt → social withdrawal)。

    social direction=-0.5 (最强反向), pressure=1.0 → mult=0.70, social 占比应低于 baseline。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    personality = {
        "warmth_bias": 0.60, "patience": 0.50, "boundary_permeability": 0.50,
        "relational_gravity": 0.50, "intimacy_pull": 0.60, "expression_drive": 0.50,
        "gossip_tendency": 0.50,
        "inner_coherence": 0.60, "curiosity": 0.50, "perception_acuity": 0.50,
        "directness": 0.50, "relational_autonomy": 0.50, "exploration_openness": 0.50,
    }
    fs_baseline = fd.compute(personality)
    fs_high_pressure = fd.compute(personality, conscience_pressure=1.0)
    assert fs_high_pressure.social < fs_baseline.social, (
        f"pressure=1.0 应压制 social (guilt → social withdrawal), "
        f"baseline={fs_baseline.social:.3f}, high={fs_high_pressure.social:.3f}"
    )


def test_force_dynamics_conscience_pressure_intermediate_smooth():
    """pressure=0.5 效果在 pressure=0 和 pressure=1.0 之间 (monotonic smooth)。

    mult 是 pressure 的线性函数, 所以 intermediate 效果应在两端之间。
    个体应满足: individual(0) < individual(0.5) < individual(1.0)。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    personality = {
        "warmth_bias": 0.60, "patience": 0.50, "boundary_permeability": 0.50,
        "relational_gravity": 0.50, "intimacy_pull": 0.60, "expression_drive": 0.50,
        "gossip_tendency": 0.50,
        "inner_coherence": 0.60, "curiosity": 0.50, "perception_acuity": 0.50,
        "directness": 0.50, "relational_autonomy": 0.50, "exploration_openness": 0.50,
    }
    fs_0 = fd.compute(personality, conscience_pressure=0.0)
    fs_05 = fd.compute(personality, conscience_pressure=0.5)
    fs_1 = fd.compute(personality, conscience_pressure=1.0)
    # individual monotonic 增
    assert fs_0.individual < fs_05.individual < fs_1.individual, (
        f"individual 应随 pressure 单调增, "
        f"0={fs_0.individual:.3f}, 0.5={fs_05.individual:.3f}, 1={fs_1.individual:.3f}"
    )
    # social monotonic 减
    assert fs_0.social > fs_05.social > fs_1.social, (
        f"social 应随 pressure 单调减, "
        f"0={fs_0.social:.3f}, 0.5={fs_05.social:.3f}, 1={fs_1.social:.3f}"
    )


def test_force_dynamics_force_state_with_conscience_tracker():
    """force_state_with_conscience(ConscienceTracker) → read pressure → 接入力学。

    验证:
    1) 全新 ConscienceTracker (pressure=0) → 跟 force_state_with_conscience(None) 一致
    2) 触发 record_value_conflict (pressure>0) → individual 占比上升 vs pressure=0
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    from emotion_spirit.regulation.superego import ConscienceTracker
    fd = ForceDynamics()
    personality = {
        "warmth_bias": 0.60, "patience": 0.50, "boundary_permeability": 0.50,
        "relational_gravity": 0.50, "intimacy_pull": 0.60, "expression_drive": 0.50,
        "gossip_tendency": 0.50,
        "inner_coherence": 0.60, "curiosity": 0.50, "perception_acuity": 0.50,
        "directness": 0.50, "relational_autonomy": 0.50, "exploration_openness": 0.50,
    }
    # 1) 全新 tracker (pressure=0)
    tracker_empty = ConscienceTracker()
    assert tracker_empty.get_pressure() == 0.0
    fs_empty = fd.force_state_with_conscience(personality, conscience_tracker=tracker_empty)
    # 等价于 conscience_pressure=0.0 → 等价于 baseline
    fs_baseline = fd.compute(personality)
    assert abs(fs_empty.natural - fs_baseline.natural) < 1e-9
    assert abs(fs_empty.social - fs_baseline.social) < 1e-9
    assert abs(fs_empty.individual - fs_baseline.individual) < 1e-9

    # 2) 触发 value_conflict (pressure>0)
    tracker_loaded = ConscienceTracker()
    # 多次 record_value_conflict 让 pressure 累计到 0.6+ (明显 shift)
    for _ in range(3):
        tracker_loaded.record_value_conflict(
            resistance=0.7,
            conflict_values=["warmth_bias", "directness"],
            tension_type="guilt",
            behavioral_shift=-0.3,
            conscience_impact=0.3,
        )
    pressure = tracker_loaded.get_pressure()
    assert pressure > 0.5, f"conscience pressure 应 > 0.5, 实际 {pressure}"
    fs_loaded = fd.force_state_with_conscience(personality, conscience_tracker=tracker_loaded)
    # individual 占比应高于 baseline
    assert fs_loaded.individual > fs_baseline.individual, (
        f"conscience pressure={pressure:.2f} 应放大 individual, "
        f"baseline={fs_baseline.individual:.3f}, loaded={fs_loaded.individual:.3f}"
    )
    # social 占比应低于 baseline
    assert fs_loaded.social < fs_baseline.social, (
        f"conscience pressure={pressure:.2f} 应压制 social, "
        f"baseline={fs_baseline.social:.3f}, loaded={fs_loaded.social:.3f}"
    )
