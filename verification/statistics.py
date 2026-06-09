"""统计检验和报告生成。

验证项:
1. 核心/边缘区分度 ≥ 3.0x (S曲线+Top-K)
2. 基线引力衰减趋势
3. 压力分布和衰减
4. tension 分类频率分布
5. 安全层触发频率
6. 人格漂移轨迹分析
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from simulation_runner import TurnSnapshot


def compute_core_peripheral_ratio(snapshots: list[TurnSnapshot]) -> dict[str, Any]:
    """计算核心/边缘区分度随交互次数的变化。

    验收标准更新 (基于知识库研究):
    - noncore_ratio=0.3 → 目标 ≥3.0x (Schwartz 价值观理论 + 价值-注意力研究)
    - 旧标准 ≥2.0x 基于 noncore_ratio=0.5，已不再适用
    """
    ratios = []
    for s in snapshots:
        if not s.weights:
            continue
        sorted_weights = sorted(s.weights.values(), reverse=True)
        if len(sorted_weights) < 6:
            continue
        core_mean = sum(sorted_weights[:5]) / 5
        peripheral_mean = sum(sorted_weights[5:]) / len(sorted_weights[5:])
        if peripheral_mean > 0:
            ratios.append((s.turn, core_mean / peripheral_mean))

    if not ratios:
        return {"mean_ratio": 0, "min_ratio": 0, "max_ratio": 0}

    ratio_values = [r for _, r in ratios]
    return {
        "mean_ratio": sum(ratio_values) / len(ratio_values),
        "min_ratio": min(ratio_values),
        "max_ratio": max(ratio_values),
        "convergence_turns": next(
            (i for i, (_, r) in enumerate(ratios) if r >= 3.0),
            len(ratios),
        ),
    }


def compute_anchor_decay(snapshots: list[TurnSnapshot]) -> dict[str, Any]:
    """分析基线引力衰减趋势。"""
    groups = {"0-100": [], "100-500": [], "500-1k": [], "1k-5k": [], "5k+": []}
    for s in snapshots:
        t = s.turn
        if t < 100: groups["0-100"].append(s)
        elif t < 500: groups["100-500"].append(s)
        elif t < 1000: groups["500-1k"].append(s)
        elif t < 5000: groups["1k-5k"].append(s)
        else: groups["5k+"].append(s)

    group_stats = {}
    for name, group in groups.items():
        if not group:
            group_stats[name] = {"mean_gap": None, "count": 0}
            continue
        gaps = [s.baseline_gap for s in group]
        group_stats[name] = {
            "mean_gap": round(sum(gaps) / len(gaps), 4),
            "max_gap": round(max(gaps), 4),
            "count": len(gaps),
        }

    return group_stats


def compute_pressure_distribution(snapshots: list[TurnSnapshot]) -> dict[str, Any]:
    """压力分布统计。

    验收标准更新:
    - critical(>0.6) 占比 <10% (基于 Anderson & Bushman 认知重评模型:
      良心压力应在事件后数小时内衰减, 不应持续累积)
    - pressure_decay_rate=0.08/hr → 半衰期 ~8.3h
    - alignment_base_relief=0.12 → 对齐行为有意义减压
    """
    pressures = [s.pressure for s in snapshots]
    if not pressures:
        return {"mean": 0, "p50": 0, "p95": 0, "max": 0, "critical_pct": 0}

    sorted_p = sorted(pressures)
    return {
        "mean": round(sum(pressures) / len(pressures), 4),
        "p50": round(sorted_p[len(sorted_p) // 2], 4),
        "p95": round(sorted_p[int(len(sorted_p) * 0.95)], 4),
        "max": round(max(pressures), 4),
        "critical_pct": round(sum(1 for p in pressures if p > 0.6) / len(pressures), 4),
    }


def compute_tension_distribution(snapshots: list[TurnSnapshot]) -> dict[str, Any]:
    """tension 类型分布统计。"""
    tension_counts: dict[str, int] = {}
    for s in snapshots:
        if s.tension_type:
            tension_counts[s.tension_type] = tension_counts.get(s.tension_type, 0) + 1

    total = sum(tension_counts.values()) or 1
    return {
        "counts": tension_counts,
        "percentages": {k: round(v / total * 100, 1) for k, v in tension_counts.items()},
    }


def compute_safety_level_distribution(snapshots: list[TurnSnapshot]) -> dict[str, Any]:
    """安全层触发分布。"""
    level_counts: dict[str, int] = {}
    for s in snapshots:
        level_counts[s.safety_level] = level_counts.get(s.safety_level, 0) + 1

    total = sum(level_counts.values()) or 1
    return {
        "counts": level_counts,
        "percentages": {k: round(v / total * 100, 1) for k, v in level_counts.items()},
    }


def compute_drift_trajectory(snapshots: list[TurnSnapshot]) -> dict[str, Any]:
    """人格漂移轨迹分析。"""
    if len(snapshots) < 10:
        return {"status": "insufficient_data"}

    samples = snapshots[::100]
    trajectory = [(s.turn, s.baseline_gap) for s in samples]

    first = snapshots[0]
    last = snapshots[-1]

    direction_changes: dict[str, str] = {}
    for layer in ("deep", "surface"):
        for dim in first.personality_deep if layer == "deep" else first.personality_surface:
            first_dict = first.personality_deep if layer == "deep" else first.personality_surface
            last_dict = last.personality_deep if layer == "deep" else last.personality_surface
            diff = last_dict.get(dim, 0.5) - first_dict.get(dim, 0.5)
            if abs(diff) > 0.01:
                direction_changes[f"{layer}.{dim}"] = f"+{diff:.3f}" if diff > 0 else f"{diff:.3f}"

    return {
        "trajectory": trajectory,
        "final_gap": last.baseline_gap,
        "initial_gap": first.baseline_gap,
        "direction_changes": direction_changes,
    }


def generate_simulation_report(snapshots: list[TurnSnapshot]) -> str:
    """生成模拟报告 Markdown。

    验收标准 (基于知识库研究更新):
    1. 核心/边缘区分度 ≥ 3.0x (Schwartz 价值观理论 + 价值-注意力研究 + noncore_ratio=0.3)
    2. critical(>0.6) 占比 <10% (良心压力应在数小时内衰减, decay=0.08/hr)
    3. tension 类型应有 guilt/doubt/shame 分布 (Magai et al. N=1118: 所有依恋类型都体验多种道德情绪)
    4. safety_level: normal >30%, warning <60%, critical <10%
    """
    lines = ["# 蒙特卡洛模拟报告\n"]
    lines.append(f"**总轮次**: {len(snapshots)}\n")
    lines.append("\n**参数版本**: v2 (基于知识库研究调整)")
    lines.append("- pressure_decay_rate=0.08/hr (半衰期~8.3h)")
    lines.append("- alignment_base_relief=0.12")
    lines.append("- noncore_ratio=0.3 (核心:边缘≈3.3:1)")
    lines.append("- righteous 阈值: alignment_ratio≥0.7 且 resistance≤0.5")
    lines.append("- _ACTION_MISALIGN: hold/explore/recover/observe 减少冲突维度")

    # 1. 核心/边缘区分度
    lines.append("\n## 1. 核心/边缘区分度\n")
    lines.append("验收标准: ≥3.0x (noncore_ratio=0.3)\n")
    ratio_stats = compute_core_peripheral_ratio(snapshots)
    lines.append(f"- 平均区分度: {ratio_stats['mean_ratio']:.2f}x")
    lines.append(f"- 最小区分度: {ratio_stats['min_ratio']:.2f}x")
    lines.append(f"- 最大区分度: {ratio_stats['max_ratio']:.2f}x")
    lines.append(f"- 达到 3.0x 的轮次: {ratio_stats['convergence_turns']}")
    lines.append(f"- **验收标准**: ≥ 3.0x → {'✅ 通过' if ratio_stats['mean_ratio'] >= 3.0 else '❌ 未通过'}")

    # 2. 基线引力衰减
    lines.append("\n## 2. 基线引力衰减\n")
    decay_stats = compute_anchor_decay(snapshots)
    for group_name, stats in decay_stats.items():
        if stats["mean_gap"] is not None:
            lines.append(f"- {group_name}: mean_gap={stats['mean_gap']:.4f}, max_gap={stats['max_gap']:.4f}, n={stats['count']}")

    # 3. 压力分布
    lines.append("\n## 3. 压力分布\n")
    lines.append("验收标准: critical(>0.6) 占比 <10%, 均值 <0.5\n")
    pressure_stats = compute_pressure_distribution(snapshots)
    lines.append(f"- 均值: {pressure_stats['mean']:.4f} {'✅' if pressure_stats['mean'] < 0.5 else '❌'} (目标: <0.5)")
    lines.append(f"- P50: {pressure_stats['p50']:.4f}")
    lines.append(f"- P95: {pressure_stats['p95']:.4f}")
    lines.append(f"- 最大: {pressure_stats['max']:.4f}")
    lines.append(f"- critical(>0.6)占比: {pressure_stats['critical_pct']:.2%} {'✅' if pressure_stats['critical_pct'] < 0.10 else '❌'} (目标: <10%)")

    # 4. tension 分布
    lines.append("\n## 4. Tension 分类分布\n")
    lines.append("验收标准: 应有 guilt/doubt/shame 分布, righteous ≤ 30%\n")
    tension_stats = compute_tension_distribution(snapshots)
    righteous_pct = tension_stats.get("percentages", {}).get("righteous", 0)
    has_distribution = len(tension_stats.get("percentages", {})) >= 2
    for ttype, pct in tension_stats["percentages"].items():
        lines.append(f"- {ttype}: {pct}%")
    lines.append(f"- **tension 分布**: {'✅ 多类型分布' if has_distribution else '❌ 分布过于单一'}")
    lines.append(f"- **righteous 占比**: {righteous_pct}% {'✅' if righteous_pct <= 30 else '❌'} (目标: ≤30%)")

    # 5. 安全层触发
    lines.append("\n## 5. 安全层触发分布\n")
    safety_stats = compute_safety_level_distribution(snapshots)
    for level, pct in safety_stats["percentages"].items():
        lines.append(f"- {level}: {pct}%")

    # 6. 漂移轨迹
    lines.append("\n## 6. 人格漂移轨迹\n")
    drift_stats = compute_drift_trajectory(snapshots)
    if "trajectory" in drift_stats:
        lines.append(f"- 初始基线距离: {drift_stats['initial_gap']:.4f}")
        lines.append(f"- 最终基线距离: {drift_stats['final_gap']:.4f}")
        lines.append(f"- 方向变化: {drift_stats['direction_changes']}")

    return "\n".join(lines)
