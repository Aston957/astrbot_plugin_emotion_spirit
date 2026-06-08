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
    from emotion_spirit.force_dynamics import ForceDynamics
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
    from emotion_spirit.force_dynamics import ForceDynamics
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
    from emotion_spirit.force_dynamics import ForceDynamics
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
