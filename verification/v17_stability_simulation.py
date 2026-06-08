"""v1.7 12 维人格稳定性 simulation。

目标: 验证 5 persona 在 1000 轮对话后 12 维都保持:
  1. 区分度 (spread 维持, 不塌缩)
  2. 无 clamp 卡死 (不全部到 0.0 或 1.0)
  3. EMA 回归有效 (激烈事件后回到 baseline)
  4. 长期无 drift collapse
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from verification.drift_simulator import DriftSimulator, DEEP_DIMS, SURFACE_DIMS


PERSONAS = [
    ("INFP-A",  {"mbti": "INFP",  "attachment": "焦虑型", "emotion_style": "表达型", "conflict_style": "顺应型", "time_focus": "活在未来"}),
    ("ISTJ-S",  {"mbti": "ISTJ",  "attachment": "安全型", "emotion_style": "压抑型", "conflict_style": "合作型", "time_focus": "活在当下"}),
    ("ENTP-AV", {"mbti": "ENTP",  "attachment": "回避型", "emotion_style": "表达型", "conflict_style": "攻击型", "time_focus": "活在未来"}),
    ("ISFJ-D",  {"mbti": "ISFJ",  "attachment": "混乱型", "emotion_style": "压抑型", "conflict_style": "顺应型", "time_focus": "活在当下"}),
    ("ESTP-A",  {"mbti": "ESTP",  "attachment": "焦虑型", "emotion_style": "表达型", "conflict_style": "攻击型", "time_focus": "活在当下"}),
]

# 8 场景 drift 方向 (BALANCED: 70% 无 drift, 30% 有方向但平衡)
SCENARIOS = {
    "daily_neutral":      {},  # 70%: 无 drift, 仅回归
    "safe_companionship": {"warmth_bias": +0.01, "intimacy_pull": +0.01},  # 8%
    "intimacy_growth":    {"intimacy_pull": +0.02, "relational_gravity": +0.01, "warmth_bias": +0.01},  # 5%
    "conflict":           {"relational_autonomy": +0.02, "boundary_permeability": -0.02, "inner_coherence": -0.01},  # 4% (v1.7)
    "recovery":           {"inner_coherence": +0.02, "patience": +0.01, "boundary_permeability": +0.01},  # 5%
    "boundary_invasion":  {"relational_autonomy": +0.03, "boundary_permeability": -0.03, "patience": -0.01},  # 3% (v1.7)
    "exploration":        {"exploration_openness": +0.02, "curiosity": +0.01, "boundary_permeability": +0.01},  # 3% (v1.7)
    "trauma":             {"inner_coherence": -0.03, "boundary_permeability": -0.02, "relational_autonomy": +0.02, "relational_gravity": -0.02},  # 2% (v1.7)
}

# 场景出现概率 (70% 中性 + 30% 平衡 drift, trauma 2%)
SCENARIO_WEIGHTS = [70, 8, 5, 4, 5, 3, 3, 2]


def run_simulation(n_turns: int = 1000, seed: int = 42) -> dict:
    """跑 5 persona × 1000 轮 simulation。"""
    import random
    rng = random.Random(seed)

    results = {}
    scenarios = list(SCENARIOS.keys())

    for name, labels in PERSONAS:
        sim = DriftSimulator(labels=labels)
        baseline = sim.baseline
        initial = sim.current

        # 1000 轮: 70% 低压力 (daily_neutral/safe_companionship), 25% 中压, 5% 高压
        max_drift = {dim: 0.0 for dim in SURFACE_DIMS}
        min_drift = {dim: 0.0 for dim in SURFACE_DIMS}
        stuck_at_boundary = {dim: 0 for dim in SURFACE_DIMS}  # 连续 100 轮 ≥0.99 或 ≤0.01

        for t in range(n_turns):
            # 99% 选正常场景, 1% 触发 trauma (cascade)
            scenario_name = rng.choices(scenarios, weights=SCENARIO_WEIGHTS)[0]
            scenario = SCENARIOS[scenario_name]
            is_trauma = (scenario_name == "trauma")

            sim.step(scenario_drift=scenario, is_trauma=is_trauma)

            current = sim.current["surface"]
            for dim in SURFACE_DIMS:
                val = current[dim]
                # track max/min
                if t == 0 or val > max_drift[dim]:
                    max_drift[dim] = val
                if t == 0 or val < min_drift[dim]:
                    min_drift[dim] = val

        # 检查 12 维
        final = sim.current["surface"]
        base = baseline["surface"]
        init = initial["surface"]

        result = {
            "name": name,
            "baseline": base,
            "initial": init,
            "final": final,
            "max_drift": max_drift,
            "min_drift": min_drift,
            "delta_from_baseline": {dim: final[dim] - base[dim] for dim in SURFACE_DIMS},
            "delta_from_initial": {dim: final[dim] - init[dim] for dim in SURFACE_DIMS},
        }
        results[name] = result

    return results


def analyze(results: dict, n_turns: int = 1000) -> None:
    """分析 simulation 结果。"""
    print("=" * 80)
    print(f"v1.7 12 维人格稳定性 simulation — 5 persona × {n_turns} turn")
    print("=" * 80)

    # 1. 5 persona baseline 区分度
    print("\n[1] 5 persona baseline 区分度 (初始)")
    print("-" * 80)
    print(f"{'Persona':<10} {'relational_autonomy':<22} {'exploration_openness':<22}")
    for name, r in results.items():
        print(f"{name:<10} {r['baseline']['relational_autonomy']:<22} {r['baseline']['exploration_openness']:<22}")
    ra_values = [r['baseline']['relational_autonomy'] for r in results.values()]
    eo_values = [r['baseline']['exploration_openness'] for r in results.values()]
    print(f"\n  RA spread: {max(ra_values) - min(ra_values):.3f}")
    print(f"  EO spread: {max(eo_values) - min(eo_values):.3f}")

    # 2. 1000 轮后最终值
    print("\n[2] 1000 轮后最终值")
    print("-" * 80)
    print(f"{'Persona':<10} {'relational_autonomy':<22} {'exploration_openness':<22}")
    for name, r in results.items():
        ra_final = r['final']['relational_autonomy']
        eo_final = r['final']['exploration_openness']
        ra_base = r['baseline']['relational_autonomy']
        eo_base = r['baseline']['exploration_openness']
        print(f"{name:<10} {ra_final:.3f} (Δ{ra_final-ra_base:+.3f})     {eo_final:.3f} (Δ{eo_final-eo_base:+.3f})")

    # 3. 1000 轮后 spread (区分度是否维持)
    print("\n[3] 1000 轮后 spread (区分度)")
    print("-" * 80)
    ra_finals = [r['final']['relational_autonomy'] for r in results.values()]
    eo_finals = [r['final']['exploration_openness'] for r in results.values()]
    print(f"  RA spread: {max(ra_finals) - min(ra_finals):.3f} (baseline: {max(ra_values) - min(ra_values):.3f})")
    print(f"  EO spread: {max(eo_finals) - min(eo_finals):.3f} (baseline: {max(eo_values) - min(eo_values):.3f})")

    # 4. 极端事件影响 (max/min)
    print("\n[4] 1000 轮内 max/min 漂移范围")
    print("-" * 80)
    for name, r in results.items():
        ra_max = r['max_drift']['relational_autonomy']
        ra_min = r['min_drift']['relational_autonomy']
        eo_max = r['max_drift']['exploration_openness']
        eo_min = r['min_drift']['exploration_openness']
        print(f"  {name:<8} RA: [{ra_min:.3f}, {ra_max:.3f}]  EO: [{eo_min:.3f}, {eo_max:.3f}]")

    # 5. Clamp 检查 (1.0/0.0 卡死)
    print("\n[5] Clamp 检查 (0 个维度触顶 0.0/1.0 是好的)")
    print("-" * 80)
    all_clean = True
    for name, r in results.items():
        for dim in SURFACE_DIMS:
            v = r['final'][dim]
            if v >= 0.99 or v <= 0.01:
                print(f"  [CLAMP] {name} {dim}={v:.4f} (clamp!)")
                all_clean = False
    if all_clean:
        print("  [OK] 所有 5 persona x 7 surface dim 最终值都在 (0.01, 0.99)")

    # 6. EMA 回归验证 (激烈事件后是否回 baseline)
    print("\n[6] EMA 回归验证 (从 baseline 偏移应 < 0.1)")
    print("-" * 80)
    all_within = True
    for name, r in results.items():
        for dim in SURFACE_DIMS:
            delta = abs(r['delta_from_baseline'][dim])
            if delta > 0.1:
                print(f"  [DRIFT] {name} {dim} delta={r['delta_from_baseline'][dim]:+.3f} (>0.1)")
                all_within = False
    if all_within:
        print("  [OK] 所有 12 dim 都回归到 baseline +/- 0.1 范围内")

    # 7. 综合评分
    print("\n[7] 综合评分")
    print("-" * 80)
    ra_spread_maintained = (max(ra_finals) - min(ra_finals)) / (max(ra_values) - min(ra_values))
    eo_spread_maintained = (max(eo_finals) - min(eo_finals)) / (max(eo_values) - min(eo_values))
    print(f"  RA 区分度维持率: {ra_spread_maintained*100:.1f}% (理想 >= 80%)")
    print(f"  EO 区分度维持率: {eo_spread_maintained*100:.1f}% (理想 >= 80%)")
    print(f"  Clamp 卡死: {'[OK] 无' if all_clean else '[WARN] 有'}")
    print(f"  EMA 回归: {'[OK] 有效' if all_within else '[WARN] 偏离'}")


def compare_turns_multiseed(turns_list: list[int], n_seeds: int = 5) -> None:
    """多轮对比 simulation: 100/200/500/1000 turn × n_seeds seeds 平均。"""
    print("=" * 80)
    print(f"v1.7.1 多轮多 seed 对比 — {n_seeds} seeds 平均")
    print("=" * 80)
    print(f"\n{'turns':<8} {'RA 维持%':<14} {'EO 维持%':<14} {'Clamps':<10} {'EMA OK':<10} {'距离':<10}")
    print("-" * 70)

    ra_base_spread = 0.700
    eo_base_spread = 0.800

    for n_turns in turns_list:
        ra_maintains = []
        eo_maintains = []
        clamp_counts = []
        distances = []  # 平均 |current - baseline|

        for seed in range(42, 42 + n_seeds):
            results = run_simulation(n_turns=n_turns, seed=seed)

            # Spread
            ra_final = [r['final']['relational_autonomy'] for r in results.values()]
            eo_final = [r['final']['exploration_openness'] for r in results.values()]
            ra_spread = max(ra_final) - min(ra_final)
            eo_spread = max(eo_final) - min(eo_final)
            ra_maintains.append(ra_spread / ra_base_spread * 100)
            eo_maintains.append(eo_spread / eo_base_spread * 100)

            # Clamps
            clamp = 0
            for r in results.values():
                for dim in SURFACE_DIMS:
                    v = r['final'][dim]
                    if v >= 0.99 or v <= 0.01:
                        clamp += 1
            clamp_counts.append(clamp)

            # Average distance from baseline (per persona per dim)
            total_dist = 0.0
            total_count = 0
            for r in results.values():
                for dim in SURFACE_DIMS:
                    total_dist += abs(r['delta_from_baseline'][dim])
                    total_count += 1
            distances.append(total_dist / total_count)

        # Average across seeds
        ra_avg = sum(ra_maintains) / n_seeds
        eo_avg = sum(eo_maintains) / n_seeds
        clamp_avg = sum(clamp_counts) / n_seeds
        dist_avg = sum(distances) / n_seeds

        # Std (just for RA to show variance)
        ra_std = (sum((x - ra_avg)**2 for x in ra_maintains) / n_seeds) ** 0.5

        ra_mark = "[OK]" if ra_avg >= 80 else ("[WARN]" if ra_avg >= 50 else "[FAIL]")
        eo_mark = "[OK]" if eo_avg >= 80 else ("[WARN]" if eo_avg >= 50 else "[FAIL]")

        print(f"{n_turns:<8} {ra_avg:5.1f}% ±{ra_std:4.1f} {ra_mark}  {eo_avg:5.1f}% {eo_mark}        {clamp_avg:5.1f}        {dist_avg:5.3f}")

    print("\n参考:")
    print("  RA baseline spread: 0.700 (INFP-A 0.20 - ISTJ-S 0.90)")
    print("  EO baseline spread: 0.800 (ISFJ-D 0.15 - ENTP-AV 0.95)")
    print("  [OK]    = 维持率 >= 80% (理想)")
    print("  [WARN]  = 维持率 50-80% (可接受)")
    print("  [FAIL]  = 维持率 < 50% (差)")
    print(f"  距离: 平均 |current - baseline| (越小 = 越稳定, 理想 < 0.1)")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("PART A: 100 turn (短时, 验证结构稳定性)")
    print("=" * 80)
    results_100 = run_simulation(n_turns=100, seed=42)
    analyze(results_100, n_turns=100)

    print("\n" + "=" * 80)
    print("PART B: 1000 turn (长期, 验证 drift 行为)")
    print("=" * 80)
    results_1000 = run_simulation(n_turns=1000, seed=42)
    analyze(results_1000, n_turns=1000)

    print("\n" + "=" * 80)
    print("PART C: 多轮多 seed 对比 (5 seed 平均, 100/200/500/1000 turn)")
    print("=" * 80)
    compare_turns_multiseed([100, 200, 500, 1000], n_seeds=5)
