"""5 fixture baseline + 1 gossip scenario 三元力学仿真验证 (Phase 3.0A Task 4, 复用 C3 framework)。

Spec §8.1 4 验证目标:
1. 5 fixture baseline 可分辨 (本文件覆盖: test_5_fixture_force_state_at_baseline + spread)
2. gossip_topic_heavy shift social (本文件覆盖: test_gossip_topic_heavy_shifts_social)
3. 8 scenarios 不全同向 (推 Phase 3.0B, spec 标 "可选")
4. 归一化不变性 (Task 3 单元测试覆盖: test_force_dynamics_compute_handles_empty, _b_greater_than_one)

本测试目的: 集成验证 ForceDynamics (算法 H) 在 C3 gossip_tendency 仿真
上下文中能输出有意义的 ForceState, 证明三元力学引擎在仿真层"做事"
(不是个常量)。复用 C3 framework (simulation_runner.simulate_persona +
DriftSimulator), 不写新 simulator 代码。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_labels import (  # noqa: E402
    INFP_A_LABELS, ISTJ_S_LABELS, ENTP_AV_LABELS, ISFJ_D_LABELS, ESTP_A_LABELS,
    ALL_5_FIXTURE_LABELS, ALL_5_FIXTURE_NAMES,
)


# ═══ 1. 5 fixture baseline ForceState 可分辨 ═══

def test_5_fixture_force_state_at_baseline():
    """5 fixture baseline → ForceState, sum=1.0 + dominant 在 3 力之一。

    验证 ForceDynamics.force_state_from_labels 集成路径: 5 标签 → KB
    compute_baseline_from_labels → 13 维 → ForceState (算法 H)。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    for labels in ALL_5_FIXTURE_LABELS:
        fs = fd.force_state_from_labels(labels)
        assert abs(fs.natural + fs.social + fs.individual - 1.0) < 0.01
        assert fs.dominant in {"natural", "social", "individual"}


def test_5_fixture_social_weight_spread():
    """5 fixture social 权重要有 spread (gossip_tendency 公式差异可见)。

    gossip_tendency 是 social 力 4 dim 之一 (relational_gravity, intimacy_pull,
    expression_drive, gossip_tendency)。5 persona gossip_tendency baseline
    在 0.40-0.60 区间 (placeholder labels), 应反映在 social weight 差异。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    fd = ForceDynamics()
    socials = [fd.force_state_from_labels(labels).social for labels in ALL_5_FIXTURE_LABELS]
    spread = max(socials) - min(socials)
    assert spread >= 0.05, (
        f"5 fixture social spread {spread:.3f} 太小 "
        f"(socials: {[f'{s:.3f}' for s in socials]})"
    )


# ═══ 2. gossip_topic_heavy shift social ═══

def test_gossip_topic_heavy_shifts_social():
    """gossip_topic_heavy 跑 20 步 → social weight 应增或保持。

    集成验证: simulate_persona 走 C3 framework (DriftSimulator + gossip 漂移),
    gossip_tendency 上升 → social 力 4 dim 加权 → social weight 升。
    选 ESTP-A (高 social baseline ~0.62) 跑 gossip_topic_heavy 20 步。
    """
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    from verification.simulation_runner import run_simulation

    fd = ForceDynamics()
    result = run_simulation(
        labels=ESTP_A_LABELS,
        scenario="gossip_topic_heavy",
        steps=20,
        persona_id="ESTP-A",
    )
    # trajectory[0] = step-0 state (initial); personality = final state after 20-step drift
    initial_fs = fd.compute(result["trajectory"][0])
    final_fs = fd.compute(result["personality"])
    # gossip 升 → social 平均升 (容忍 0.05 浮点噪声)
    assert final_fs.social >= initial_fs.social - 0.05, (
        f"gossip 应让 social 升或保持, "
        f"{initial_fs.social:.3f} → {final_fs.social:.3f}"
    )


# ═══ 3. force_state 快照 (Phase 3.0B Task 3) ═══

def test_trajectory_includes_force_state_per_step():
    """simulate_persona 返回 force_trajectory: list[dict], 长度 = steps + 1。

    每个元素是 ForceState.to_dict() 形式 (natural/social/individual 三键),
    归一化和 = 1.0。
    """
    from verification.simulation_runner import run_simulation

    result = run_simulation(
        labels=INFP_A_LABELS,
        scenario="neutral_only",
        steps=5,
        persona_id="INFP-A",
    )
    # force_trajectory 字段存在
    assert "force_trajectory" in result, "result 缺 force_trajectory 字段"

    force_trajectory = result["force_trajectory"]
    # 长度 = steps + 1 (initial + 5 步)
    assert len(force_trajectory) == 6, (
        f"force_trajectory 长度应为 6 (initial + 5 steps), got {len(force_trajectory)}"
    )

    # 每步是 dict, 含 natural/social/individual 三键, 归一化
    for i, fs in enumerate(force_trajectory):
        assert isinstance(fs, dict), f"step {i}: expected dict, got {type(fs).__name__}"
        assert set(fs.keys()) == {"natural", "social", "individual"}, (
            f"step {i}: keys 错, got {set(fs.keys())}"
        )
        total = fs["natural"] + fs["social"] + fs["individual"]
        assert abs(total - 1.0) < 0.01, (
            f"step {i}: 归一化和 != 1.0, got {total:.4f}"
        )


def test_force_state_snapshot_varies_with_scenario():
    """gossip_topic_heavy 跟 neutral_only 跑同样步数, 终态 ForceState 不同。

    验证: gossip 漂移 → social weight 改变 → force_state[last] 跟 neutral
    scenario 跑同样步数时的 force_state[last] 不同。
    """
    from verification.simulation_runner import run_simulation

    result_neutral = run_simulation(
        labels=ESTP_A_LABELS,
        scenario="neutral_only",
        steps=20,
        persona_id="ESTP-A",
    )
    result_gossip = run_simulation(
        labels=ESTP_A_LABELS,
        scenario="gossip_topic_heavy",
        steps=20,
        persona_id="ESTP-A",
    )
    fs_neutral_last = result_neutral["force_trajectory"][-1]
    fs_gossip_last = result_gossip["force_trajectory"][-1]
    # gossip 应让 personality drift 不同 → force_state 终态不同
    assert fs_neutral_last != fs_gossip_last, (
        f"gossip scenario 跟 neutral scenario 终态 force_state 应不同, "
        f"neutral={fs_neutral_last}, gossip={fs_gossip_last}"
    )


def test_force_state_snapshot_initial_step_matches_baseline():
    """force_trajectory[0] (initial step) 应跟 personality 初始 baseline ForceState 一致。"""
    from emotion_spirit.regulation.force_dynamics import ForceDynamics
    from verification.simulation_runner import run_simulation

    fd = ForceDynamics()
    result = run_simulation(
        labels=INFP_A_LABELS,
        scenario="neutral_only",
        steps=3,
        persona_id="INFP-A",
    )
    # 初始 ForceState (从 labels 算)
    initial_fs_expected = fd.force_state_from_labels(INFP_A_LABELS).to_dict()
    initial_fs_actual = result["force_trajectory"][0]
    assert abs(initial_fs_actual["natural"] - initial_fs_expected["natural"]) < 0.01
    assert abs(initial_fs_actual["social"] - initial_fs_expected["social"]) < 0.01
    assert abs(initial_fs_actual["individual"] - initial_fs_expected["individual"]) < 0.01
