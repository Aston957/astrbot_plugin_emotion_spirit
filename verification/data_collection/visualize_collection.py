"""数据收集可视化 — 基于 SurfaceLogger 输出的真实数据生成图表。

输入: data_collection/output/surface_log_*.csv
输出: data_collection/charts/*.png

图表:
  01: 5 persona 人格漂移对比 (5 个子图)
  02: 场景切换时间线 (按 persona)
  03: 关键维度随时间变化 (intimacy_pull/relational_autonomy/boundary_perm/inner_coherence)  # v1.7: autonomy_guard 拆分
  04: Persona 最终人格雷达图
  05: 基线距离 (漂移幅度) 累积图
"""

from __future__ import annotations

import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import csv
from collections import defaultdict

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


PERSONA_COLORS = {
    "INFP-A": "#e74c3c",
    "ISTJ-S": "#3498db",
    "ENTP-AV": "#2ecc71",
    "ISFJ-D": "#9b59b6",
    "ESTP-A": "#f39c12",
}

KEY_DIMS = [
    ("intimacy_pull", "亲密牵引"),
    # v1.7: autonomy_guard 拆分为 2 维
    ("relational_autonomy", "关系边界"),
    ("exploration_openness", "探索开放"),
    ("boundary_permeability", "边界通透"),
    ("inner_coherence", "内在一致"),
    ("expression_drive", "表达驱动"),
    ("warmth_bias", "温暖偏向"),
]


def load_csv(path: Path) -> list[dict[str, str]]:
    """读取 SurfaceLogger 输出的 CSV。"""
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def group_by_persona(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """按 session_id (persona) 分组。"""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        sid = row["session_id"]
        grouped[sid].append(row)
    for sid in grouped:
        grouped[sid].sort(key=lambda r: int(r["turn"]))
    return grouped


def plot_personality_drift(grouped: dict, output_dir: Path) -> None:
    """图 1: 5 persona 在 6 个关键维度上的漂移轨迹。"""
    fig, axes = plt.subplots(2, 3, figsize=(16, 10), sharex=True)
    axes = axes.flatten()

    for ax, (dim, zh) in zip(axes, KEY_DIMS):
        for persona_id, rows in grouped.items():
            turns = [int(r["turn"]) for r in rows]
            values = [float(r[dim]) for r in rows]
            label = persona_id.replace("data-", "")
            color = PERSONA_COLORS.get(label, "#7f8c8d")
            ax.plot(turns, values, color=color, alpha=0.8, linewidth=1.0, label=label)
        ax.set_title(f"{zh} ({dim})", fontsize=12)
        ax.set_ylabel("值", fontsize=10)
        ax.set_xlabel("轮次", fontsize=10)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, loc="best")

    fig.suptitle("5 Persona 关键维度漂移轨迹 (500 轮)", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "01_personality_drift_5personas.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 01_personality_drift_5personas.png")


def plot_action_distribution(grouped: dict, output_dir: Path) -> None:
    """图 2: 各 persona 的 action 分布。"""
    from collections import Counter

    fig, axes = plt.subplots(1, len(grouped), figsize=(4 * len(grouped), 4))
    if len(grouped) == 1:
        axes = [axes]

    for ax, (persona_id, rows) in zip(axes, sorted(grouped.items())):
        actions = Counter(r["action"] for r in rows)
        labels = list(actions.keys())
        sizes = list(actions.values())
        colors_map = {
            "express": "#2ecc71", "withdraw": "#e74c3c", "hold": "#95a5a6",
            "reach_out": "#3498db", "repair": "#f39c12", "observe": "#bdc3c7",
        }
        colors = [colors_map.get(l, "#7f8c8d") for l in labels]
        ax.pie(sizes, labels=labels, autopct="%1.0f%%", colors=colors,
               textprops={"fontsize": 9}, startangle=90)
        ax.set_title(persona_id.replace("data-", ""), fontsize=12, fontweight="bold")

    fig.suptitle("各 Persona Action 分布", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "02_action_distribution.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 02_action_distribution.png")


def plot_radar_comparison(grouped: dict, output_dir: Path) -> None:
    """图 3: 5 persona 最终人格雷达图。"""
    dims = [d for d, _ in KEY_DIMS]
    labels = [zh for _, zh in KEY_DIMS]
    angles = np.linspace(0, 2 * np.pi, len(dims), endpoint=False).tolist()
    angles += angles[:1]  # 闭合

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))

    for persona_id, rows in sorted(grouped.items()):
        if not rows:
            continue
        final = rows[-1]
        values = [float(final[d]) for d in dims]
        values += values[:1]  # 闭合
        label = persona_id.replace("data-", "")
        color = PERSONA_COLORS.get(label, "#7f8c8d")
        ax.plot(angles, values, color=color, linewidth=2, label=label)
        ax.fill(angles, values, color=color, alpha=0.1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=9)
    ax.grid(True)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.0), fontsize=10)
    ax.set_title("5 Persona 最终人格雷达图", fontsize=14, fontweight="bold", pad=20)

    fig.tight_layout()
    fig.savefig(output_dir / "03_radar_final_personality.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 03_radar_final_personality.png")


def plot_baseline_gap(grouped: dict, output_dir: Path) -> None:
    """图 4: 各 persona 的基线距离随时间变化。"""
    fig, ax = plt.subplots(figsize=(14, 6))

    for persona_id, rows in sorted(grouped.items()):
        turns = [int(r["turn"]) for r in rows]
        gaps = []
        for r in rows:
            # 假设 baseline = 0.5 (ISTJ-安全型默认)
            # 实际计算当前与初始的差
            dist = 0.0
            for d in [d for d, _ in KEY_DIMS]:
                dist += (float(r[d]) - 0.5) ** 2
            gaps.append(np.sqrt(dist))
        label = persona_id.replace("data-", "")
        color = PERSONA_COLORS.get(label, "#7f8c8d")
        ax.plot(turns, gaps, color=color, alpha=0.8, linewidth=1.2, label=label)

    ax.set_xlabel("轮次", fontsize=12)
    ax.set_ylabel("与基线的欧氏距离 (6 维)", fontsize=12)
    ax.set_title("5 Persona 漂移幅度累积", fontsize=14, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / "04_baseline_gap.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 04_baseline_gap.png")


def plot_phi_timeline(grouped: dict, output_dir: Path) -> None:
    """图 5: phi_smoothed (涌现度) 随时间变化 — 跨 persona 比较。"""
    fig, ax = plt.subplots(figsize=(14, 5))

    for persona_id, rows in sorted(grouped.items()):
        turns = [int(r["turn"]) for r in rows]
        phis = [float(r["phi_smoothed"]) for r in rows]
        label = persona_id.replace("data-", "")
        color = PERSONA_COLORS.get(label, "#7f8c8d")
        # 平滑
        window = 10
        if len(phis) > window:
            smoothed = np.convolve(phis, np.ones(window) / window, mode="valid")
            ax.plot(turns[window - 1:], smoothed, color=color, linewidth=1.5, label=label, alpha=0.9)
        else:
            ax.plot(turns, phis, color=color, linewidth=1.5, label=label, alpha=0.9)

    ax.set_xlabel("轮次", fontsize=12)
    ax.set_ylabel("φ_smoothed (涌现度, 10 轮平滑)", fontsize=12)
    ax.set_title("涌现度 φ 时间序列", fontsize=14, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / "05_phi_timeline.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 05_phi_timeline.png")


def plot_guard_safety(grouped: dict, output_dir: Path) -> None:
    """图 6: guard 拒绝率 + guard_risk_score 随时间变化。"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    for persona_id, rows in sorted(grouped.items()):
        turns = [int(r["turn"]) for r in rows]
        # guard_allowed=True 表示允许
        reject_rate = [0.0 if r["guard_allowed"] == "True" else 1.0 for r in rows]
        risk_scores = [float(r["guard_risk_score"]) for r in rows]
        label = persona_id.replace("data-", "")
        color = PERSONA_COLORS.get(label, "#7f8c8d")

        # 滑动平均拒绝率
        window = 10
        if len(reject_rate) > window:
            smoothed_r = np.convolve(reject_rate, np.ones(window) / window, mode="valid")
            ax1.plot(turns[window - 1:], smoothed_r, color=color, linewidth=1.2, label=label, alpha=0.8)
        if len(risk_scores) > window:
            smoothed_s = np.convolve(risk_scores, np.ones(window) / window, mode="valid")
            ax2.plot(turns[window - 1:], smoothed_s, color=color, linewidth=1.2, label=label, alpha=0.8)

    ax1.set_ylabel("Guard 拒绝率 (10 轮平滑)", fontsize=11)
    ax1.set_title("Guard 拒绝率时间序列", fontsize=13, fontweight="bold")
    ax1.set_ylim(-0.05, 1.05)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    ax2.set_xlabel("轮次", fontsize=12)
    ax2.set_ylabel("Guard Risk Score (10 轮平滑)", fontsize=11)
    ax2.set_title("Guard Risk Score 时间序列", fontsize=13, fontweight="bold")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / "06_guard_safety.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ✅ 06_guard_safety.png")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="数据收集可视化")
    parser.add_argument("--input", type=str, required=True, help="SurfaceLogger CSV 路径")
    parser.add_argument("--output-dir", type=str, default="verification/data_collection/charts")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"读取数据: {args.input}")
    rows = load_csv(Path(args.input))
    print(f"  总行数: {len(rows)}")

    grouped = group_by_persona(rows)
    print(f"  Persona 数: {len(grouped)}")
    for pid, prs in sorted(grouped.items()):
        print(f"    {pid}: {len(prs)} 轮")
    print()

    print("生成图表:")
    plot_personality_drift(grouped, output_dir)
    plot_action_distribution(grouped, output_dir)
    plot_radar_comparison(grouped, output_dir)
    plot_baseline_gap(grouped, output_dir)
    plot_phi_timeline(grouped, output_dir)
    plot_guard_safety(grouped, output_dir)

    print(f"\n所有图表已保存到: {output_dir}")


if __name__ == "__main__":
    main()
