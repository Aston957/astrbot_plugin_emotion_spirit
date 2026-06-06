"""可视化脚本 — 生成蒙特卡洛模拟的趋势图。

用法:
    python visualize.py
    python visualize.py --turns 2000 --labels "ISTJ-安全"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# Windows 中文字体
for fname in ["Microsoft YaHei", "SimHei", "STHeiti"]:
    if any(fname.lower() in f.name.lower() for f in fm.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [fname]
        break
plt.rcParams["axes.unicode_minus"] = False

from simulation_runner import SimulationRunner, TurnSnapshot
from statistics import (
    compute_core_peripheral_ratio,
    compute_pressure_distribution,
    compute_tension_distribution,
    compute_anchor_decay,
    compute_drift_trajectory,
)


def plot_personality_drift(
    snapshots: list[TurnSnapshot],
    output_dir: Path,
) -> None:
    """图 1: 11 维人格参数漂移轨迹。"""
    fig, (ax_deep, ax_surface) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    turns = [s.turn for s in snapshots]

    # 深层维度 (5 维)
    deep_dims = ["expression_drive", "perception_acuity", "boundary_permeability",
                 "inner_coherence", "relational_gravity"]
    deep_colors = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f39c12"]
    for dim, color in zip(deep_dims, deep_colors):
        values = [s.personality_deep.get(dim, 0.5) for s in snapshots]
        ax_deep.plot(turns, values, color=color, alpha=0.7, linewidth=0.8, label=dim)

    ax_deep.set_ylabel("深层维度值", fontsize=12)
    ax_deep.set_title("深层人格维度漂移轨迹 (deep)", fontsize=14)
    ax_deep.legend(loc="upper right", fontsize=8, ncol=2)
    ax_deep.set_ylim(-0.05, 1.05)
    ax_deep.grid(True, alpha=0.3)

    # 表层维度 (7 维, v1.7: 6→7)
    surface_dims = ["warmth_bias", "directness", "curiosity",
                    "patience", "intimacy_pull",
                    "relational_autonomy", "exploration_openness"]
    surface_colors = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#f39c12", "#1abc9c", "#e67e22"]
    for dim, color in zip(surface_dims, surface_colors):
        values = [s.personality_surface.get(dim, 0.5) for s in snapshots]
        ax_surface.plot(turns, values, color=color, alpha=0.7, linewidth=0.8, label=dim)

    ax_surface.set_ylabel("表层维度值", fontsize=12)
    ax_surface.set_xlabel("交互轮次", fontsize=12)
    ax_surface.set_title("表层人格维度漂移轨迹 (surface)", fontsize=14)
    ax_surface.legend(loc="upper right", fontsize=8, ncol=2)
    ax_surface.set_ylim(-0.05, 1.05)
    ax_surface.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / "01_personality_drift.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 01_personality_drift.png")


def plot_weight_ratio(snapshots: list[TurnSnapshot], output_dir: Path) -> None:
    """图 2: 核心/边缘权重区分度随时间变化。"""
    fig, ax = plt.subplots(figsize=(12, 5))

    turns = []
    ratios = []
    for s in snapshots:
        if not s.weights:
            continue
        sorted_w = sorted(s.weights.values(), reverse=True)
        if len(sorted_w) >= 6:
            core_mean = sum(sorted_w[:5]) / 5
            periph_mean = sum(sorted_w[5:]) / len(sorted_w[5:])
            if periph_mean > 0:
                turns.append(s.turn)
                ratios.append(core_mean / periph_mean)

    # 平滑 (移动平均)
    window = 50
    if len(ratios) > window:
        smoothed = np.convolve(ratios, np.ones(window) / window, mode="valid")
        ax.plot(turns[window - 1:], smoothed, color="#2c3e50", linewidth=1.5, label=f"平滑 (window={window})")
    ax.plot(turns, ratios, color="#bdc3c7", alpha=0.4, linewidth=0.5, label="原始")

    ax.axhline(y=2.0, color="#e74c3c", linestyle="--", alpha=0.7, label="验收线 (2.0x)")
    ax.set_xlabel("交互轮次", fontsize=12)
    ax.set_ylabel("核心/边缘比值", fontsize=12)
    ax.set_title("核心维度 vs 边缘维度权重区分度", fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / "02_weight_ratio.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 02_weight_ratio.png")


def plot_pressure_and_safety(snapshots: list[TurnSnapshot], output_dir: Path) -> None:
    """图 3: 良心压力 + 安全层级别。"""
    fig, (ax_p, ax_s) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    turns = [s.turn for s in snapshots]
    pressures = [s.pressure for s in snapshots]

    ax_p.fill_between(turns, pressures, alpha=0.3, color="#e74c3c")
    ax_p.plot(turns, pressures, color="#e74c3c", linewidth=0.8)
    ax_p.axhline(y=0.6, color="#f39c12", linestyle="--", alpha=0.7, label="critical 阈值 (0.6)")
    ax_p.set_ylabel("良心压力", fontsize=12)
    ax_p.set_title("良心压力变化趋势", fontsize=14)
    ax_p.set_ylim(-0.05, 1.05)
    ax_p.legend(fontsize=10)
    ax_p.grid(True, alpha=0.3)

    # 安全层级别 (编码: normal=0, warning=1, critical=2)
    level_map = {"normal": 0, "warning": 1, "critical": 2}
    level_values = [level_map.get(s.safety_level, 0) for s in snapshots]
    level_colors = ["#2ecc71", "#f39c12", "#e74c3c"]

    for i, (label, color) in enumerate(zip(["normal", "warning", "critical"], level_colors)):
        mask = [v == i for v in level_values]
        if any(mask):
            ax_s.scatter(
                [t for t, m in zip(turns, mask) if m],
                [v for v, m in zip(level_values, mask) if m],
                color=color, alpha=0.3, s=2, label=label,
            )

    ax_s.set_yticks([0, 1, 2])
    ax_s.set_yticklabels(["normal", "warning", "critical"])
    ax_s.set_xlabel("交互轮次", fontsize=12)
    ax_s.set_title("安全层触发级别", fontsize=14)
    ax_s.legend(fontsize=10, markerscale=5)
    ax_s.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / "03_pressure_safety.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 03_pressure_safety.png")


def plot_baseline_gap(snapshots: list[TurnSnapshot], output_dir: Path) -> None:
    """图 4: 基线距离 (人格漂移幅度)。"""
    fig, ax = plt.subplots(figsize=(12, 5))

    turns = [s.turn for s in snapshots]
    gaps = [s.baseline_gap for s in snapshots]

    # 平滑
    window = 50
    if len(gaps) > window:
        smoothed = np.convolve(gaps, np.ones(window) / window, mode="valid")
        ax.plot(turns[window - 1:], smoothed, color="#8e44ad", linewidth=1.5, label=f"平滑 (window={window})")
    ax.plot(turns, gaps, color="#d5b8e8", alpha=0.4, linewidth=0.5, label="原始")

    ax.set_xlabel("交互轮次", fontsize=12)
    ax.set_ylabel("欧氏距离", fontsize=12)
    ax.set_title("当前人格与初始基线的距离 (漂移幅度)", fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / "04_baseline_gap.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 04_baseline_gap.png")


def plot_scenario_distribution(snapshots: list[TurnSnapshot], output_dir: Path) -> None:
    """图 5: 场景分布 (饼图)。"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # 场景分布
    scenario_counts: dict[str, int] = {}
    for s in snapshots:
        scenario_counts[s.scenario] = scenario_counts.get(s.scenario, 0) + 1

    colors_sc = ["#2ecc71", "#e74c3c", "#9b59b6", "#3498db", "#95a5a6", "#f39c12", "#1abc9c", "#34495e"]
    labels = list(scenario_counts.keys())
    sizes = list(scenario_counts.values())
    ax1.pie(sizes, labels=labels, autopct="%1.1f%%", colors=colors_sc[:len(labels)],
            textprops={"fontsize": 9}, startangle=90)
    ax1.set_title("场景分布", fontsize=14)

    # tension 分布
    tension_counts: dict[str, int] = {}
    for s in snapshots:
        t = s.tension_type or "none"
        tension_counts[t] = tension_counts.get(t, 0) + 1

    colors_tn = {"guilt": "#e74c3c", "doubt": "#3498db", "shame": "#f39c12",
                 "righteous": "#2ecc71", "none": "#95a5a6"}
    t_labels = list(tension_counts.keys())
    t_sizes = list(tension_counts.values())
    t_colors = [colors_tn.get(l, "#bdc3c7") for l in t_labels]
    ax2.pie(t_sizes, labels=t_labels, autopct="%1.1f%%", colors=t_colors,
            textprops={"fontsize": 9}, startangle=90)
    ax2.set_title("Tension 类型分布", fontsize=14)

    fig.tight_layout()
    fig.savefig(output_dir / "05_scenario_tension.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 05_scenario_tension.png")


def plot_alignment_and_gap(snapshots: list[TurnSnapshot], output_dir: Path) -> None:
    """图 6: 对齐分数 + 理想自我差距。"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    turns = [s.turn for s in snapshots]
    alignment = [s.alignment_score for s in snapshots]
    ideal_gap = [s.ideal_gap for s in snapshots]

    # 对齐分数
    window = 50
    if len(alignment) > window:
        smoothed_a = np.convolve(alignment, np.ones(window) / window, mode="valid")
        ax1.plot(turns[window - 1:], smoothed_a, color="#27ae60", linewidth=1.5, label=f"平滑 (window={window})")
    ax1.plot(turns, alignment, color="#a9dfbf", alpha=0.4, linewidth=0.5)
    ax1.axhline(y=0.5, color="#95a5a6", linestyle="--", alpha=0.5, label="基线 (0.5)")
    ax1.set_ylabel("对齐分数", fontsize=12)
    ax1.set_title("价值对齐分数趋势", fontsize=14)
    ax1.set_ylim(-0.05, 1.05)
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)

    # 理想自我差距
    if len(ideal_gap) > window:
        smoothed_g = np.convolve(ideal_gap, np.ones(window) / window, mode="valid")
        ax2.plot(turns[window - 1:], smoothed_g, color="#c0392b", linewidth=1.5, label=f"平滑 (window={window})")
    ax2.plot(turns, ideal_gap, color="#f5b7b1", alpha=0.4, linewidth=0.5)
    ax2.set_xlabel("交互轮次", fontsize=12)
    ax2.set_ylabel("欧氏距离", fontsize=12)
    ax2.set_title("当前人格与理想自我的差距", fontsize=14)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / "06_alignment_ideal.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 06_alignment_ideal.png")


def plot_scenario_timeline(snapshots: list[TurnSnapshot], output_dir: Path) -> None:
    """图 7: 场景时间线 (前 200 轮)。"""
    fig, ax = plt.subplots(figsize=(14, 3))

    subset = snapshots[:200]
    scenario_colors = {
        "safe_companionship": "#2ecc71", "conflict": "#e74c3c",
        "cascading": "#9b59b6", "recovery": "#3498db",
        "daily_neutral": "#95a5a6", "boundary_invasion": "#f39c12",
        "intimacy_growth": "#1abc9c", "trauma": "#34495e",
    }

    for i, s in enumerate(subset):
        color = scenario_colors.get(s.scenario, "#bdc3c7")
        ax.barh(0, 1, left=i, color=color, edgecolor="white", linewidth=0.1)

    # 图例
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=c, label=n) for n, c in scenario_colors.items()]
    ax.legend(handles=legend_elements, loc="upper center", ncol=4, fontsize=8,
              bbox_to_anchor=(0.5, 1.5))

    ax.set_yticks([])
    ax.set_xlabel("交互轮次", fontsize=12)
    ax.set_title("场景切换时间线 (前 200 轮)", fontsize=14)
    ax.set_xlim(0, 200)

    fig.tight_layout()
    fig.savefig(output_dir / "07_scenario_timeline.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 07_scenario_timeline.png")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="蒙特卡洛模拟可视化")
    parser.add_argument("--turns", type=int, default=1000, help="模拟轮次")
    parser.add_argument("--labels", default="INFP-焦虑", help="人格标签组合")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    output_dir = Path(__file__).parent / "output" / "charts"
    output_dir.mkdir(parents=True, exist_ok=True)

    LABELS_MAP = {
        "INFP-焦虑": {"mbti": "INFP", "attachment": "焦虑型", "emotion_style": "表达型", "conflict_style": "顺应型", "time_focus": "活在当下"},
        "ISTJ-安全": {"mbti": "ISTJ", "attachment": "安全型", "emotion_style": "混合型", "conflict_style": "合作型", "time_focus": "活在当下"},
        "ENTP-回避": {"mbti": "ENTP", "attachment": "回避型", "emotion_style": "表达型", "conflict_style": "攻击型", "time_focus": "活在未来"},
    }

    labels = LABELS_MAP.get(args.labels, LABELS_MAP["INFP-焦虑"])

    print(f"运行模拟: N={args.turns}, 标签={args.labels}, seed={args.seed}")
    runner = SimulationRunner(labels=labels, n_turns=args.turns, seed=args.seed)
    snapshots = runner.run()
    print(f"模拟完成，共 {len(snapshots)} 轮\n")

    print("生成图表:")
    plot_personality_drift(snapshots, output_dir)
    plot_weight_ratio(snapshots, output_dir)
    plot_pressure_and_safety(snapshots, output_dir)
    plot_baseline_gap(snapshots, output_dir)
    plot_scenario_distribution(snapshots, output_dir)
    plot_alignment_and_gap(snapshots, output_dir)
    plot_scenario_timeline(snapshots, output_dir)

    print(f"\n所有图表已保存到: {output_dir}")


if __name__ == "__main__":
    main()
