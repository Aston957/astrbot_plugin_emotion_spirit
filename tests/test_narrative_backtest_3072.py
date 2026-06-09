"""Tests for 3072 narrative backtest runner (Phase 3.0C Step 4)。

TDD 序:
- Task 1 (red): 本文件 — 6 tests, 跑全 FAIL (verification/narrative_backtest_3072.py 还不存在)
- Task 2 (green): 写 runner, 6 tests 全 PASS

测试目标:
- 5 fixture sanity: 验证 runner 跟 3.0A Task 4 test_force_dynamics_simulation.py 行为对齐
- 3072 baseline: 验证 KB 3072 entries 都能产生 valid ForceState, dominant ∈ {natural, social, individual}
- 3072 distribution: 验证 3 force 分布 sum=3072, 跟 spec §4.3 实测一致
"""
from __future__ import annotations

import pytest
import sys
from pathlib import Path

# 让 verification/ 包可 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ═══ 1. 5 fixture sanity tests (Phase A) ═══


def test_5_fixture_baseline_dominant_in_set():
    """5 fixture baseline ForceState dominant ∈ {natural, social, individual}。

    验证 runner 行为跟 3.0A Task 4 test_force_dynamics_simulation.py 对齐。
    """
    from verification.narrative_backtest_3072 import run_5_fixture_sanity
    results = run_5_fixture_sanity()
    fixture_results = results["sanity"]["baseline"]
    # 5 fixture (INFP-A / ISTJ-S / ENTP-AV / ISFJ-D / ESTP-A)
    assert len(fixture_results) == 5
    for name, fs_dict in fixture_results.items():
        assert fs_dict["dominant"] in {"natural", "social", "individual"}, (
            f"{name}: dominant {fs_dict['dominant']!r} 不在 3 力集合"
        )
        # 3 权重 sum ≈ 1.0
        total = fs_dict["natural"] + fs_dict["social"] + fs_dict["individual"]
        assert abs(total - 1.0) < 1e-9, f"{name}: 3 权重 sum != 1.0, got {total}"


def test_5_fixture_neutral_trajectory_length():
    """5 fixture neutral_only × 5 steps → force_trajectory 长度 = 6 (initial + 5)。

    跟 test_force_state_snapshot_initial_step_matches_baseline 一致。
    """
    from verification.narrative_backtest_3072 import run_5_fixture_sanity
    results = run_5_fixture_sanity()
    neutral_runs = results["sanity"]["neutral_only"]
    for name, run in neutral_runs.items():
        assert len(run["trajectory"]) == 6, (
            f"{name}: neutral_only × 5 steps 应有 6 个 FS (initial + 5), got {len(run['trajectory'])}"
        )
        # 每步 3 权重 sum ≈ 1.0
        for i, fs in enumerate(run["trajectory"]):
            total = fs["natural"] + fs["social"] + fs["individual"]
            assert abs(total - 1.0) < 1e-9, (
                f"{name} step {i}: 3 权重 sum != 1.0, got {total}"
            )


def test_5_fixture_neutral_drift_bounded():
    """5 fixture neutral_only × 5 steps 漂移 < 0.15 (realistic bound, 真实主义)。

    neutral_only 不引入 gossip 等 trigger, 漂移应小 (≤0.15 总幅度)。
    """
    from verification.narrative_backtest_3072 import run_5_fixture_sanity
    results = run_5_fixture_sanity()
    neutral_runs = results["sanity"]["neutral_only"]
    for name, run in neutral_runs.items():
        drift = run["drift_magnitude"]
        assert 0.0 <= drift < 0.15, (
            f"{name}: neutral_only × 5 steps 漂移 {drift:.4f} 超出 [0, 0.15) 范围"
        )


# ═══ 2. 3072 baseline tests (Phase B — main objective) ═══


def test_3072_baseline_count():
    """3072 baseline 跑出 3072 entries (KB 全覆盖 smoke test)。"""
    from verification.narrative_backtest_3072 import run_baseline_3072
    results = run_baseline_3072()
    # 过滤 _meta (内部计时 key)
    entries = {k: v for k, v in results.items() if not k.startswith("_")}
    assert len(entries) == 3072, (
        f"3072 baseline 应有 3072 entries, got {len(entries)}"
    )


def test_3072_baseline_dominant_distribution_sums_to_3072():
    """3 force 分布 sum = 3072 (验证 aggregation 函数行为正确)。"""
    from verification.narrative_backtest_3072 import (
        run_baseline_3072, aggregate_dominant_distribution,
    )
    baseline = run_baseline_3072()
    dist = aggregate_dominant_distribution(baseline)
    overall = dist["overall"]
    assert overall["natural"] + overall["social"] + overall["individual"] == 3072, (
        f"3 force 分布 sum != 3072: {overall}"
    )
    assert overall["total"] == 3072
    # 每种 dominant 至少 1 个 (不太可能全是 1 个 force, KB 3072 组合应有 spread)
    for force in ("natural", "social", "individual"):
        assert overall[force] > 0, f"{force} count = 0, 3072 整体应覆盖 3 力"


def test_3072_baseline_confidence_breakdown():
    """3 force 分布在 A/B/C/D confidence group 各自行为 (实测, 反映 DIM_FORCE 6/4/3 维数不对称)。

    实测分布 (per 3.0C Step 4 跑通):
    - overall: natural 10.2% / social 32.6% / individual 57.2% (n=3072)
    - D group: natural 10.2% / social 32.6% / individual 57.2% (n=2896)
    - C group: natural 10.6% / social 32.5% / individual 56.9% (n=160)
    - B group: natural 6.2% / social 31.2% / individual 62.5% (n=16)

    原因: DIM_FORCE 3-4-6 映射 (individual 6/13 dim = 46% 维数权重, 算法 H |intensity| 加权自然倾向 individual)。
    这是结构属性, 不是 bug; 验证算法 H 在 3072 大样本下行为一致。
    """
    from verification.narrative_backtest_3072 import (
        run_baseline_3072, aggregate_dominant_distribution,
    )
    baseline = run_baseline_3072()
    dist = aggregate_dominant_distribution(baseline)
    by_conf = dist["by_confidence"]
    overall = dist["overall"]

    # 总体分布: individual majority (dim 6/13 占 46%, 大样本应胜出)
    assert overall["individual"] > overall["social"], (
        f"individual ({overall['individual']}) 应 > social ({overall['social']})"
    )
    assert overall["individual"] > overall["natural"], (
        f"individual ({overall['individual']}) 应 > natural ({overall['natural']})"
    )
    # social 居中
    assert overall["natural"] < overall["social"], (
        f"natural ({overall['natural']}) 应 < social ({overall['social']})"
    )

    # 范围断言: natural 5-15%, social 28-38%, individual 50-65%
    # (反映 DIM_FORCE 6/4/3 维数加权, 容许 KB 生成 noise)
    natural_pct = overall["natural"] / overall["total"]
    social_pct = overall["social"] / overall["total"]
    individual_pct = overall["individual"] / overall["total"]
    assert 0.05 <= natural_pct <= 0.15, (
        f"natural % {natural_pct:.1%} 偏离 [5%, 15%] (DIM_FORCE 3/13 维)"
    )
    assert 0.28 <= social_pct <= 0.38, (
        f"social % {social_pct:.1%} 偏离 [28%, 38%] (DIM_FORCE 4/13 维)"
    )
    assert 0.50 <= individual_pct <= 0.65, (
        f"individual % {individual_pct:.1%} 偏离 [50%, 65%] (DIM_FORCE 6/13 维)"
    )

    # B 组: 16 entries (16 MBTI × 安全型), 不应全 1 种 force
    b_dist = by_conf["B"]
    b_total = b_dist["natural"] + b_dist["social"] + b_dist["individual"]
    assert b_total == 16, f"B confidence 应有 16 entries, got {b_total}"
    distinct_forces = sum(1 for f in ("natural", "social", "individual") if b_dist[f] > 0)
    assert distinct_forces >= 2, (
        f"B confidence 16 个 MBTI 全 dominant 1 种 force (distinct={distinct_forces})"
    )

    # D 组: 2896 entries, 分布跟 overall 一致 (大样本, KB noise 影响小)
    d_dist = by_conf["D"]
    d_total = d_dist["natural"] + d_dist["social"] + d_dist["individual"]
    assert d_total == 2896, f"D confidence 应有 2896 entries, got {d_total}"
