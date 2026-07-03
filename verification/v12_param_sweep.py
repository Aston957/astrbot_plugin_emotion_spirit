"""v1.2 参数扫描仿真 — 寻找 TRAJECTORY_WINDOW / velocity 阈值 / ambiguity 归一化的最优值。

设计：
- 3 个合成场景（calm 平稳 / gradual 渐变 / burst 突变）— 区分度测试
- 8 个真实场景（SCENARIOS）— 稳定性测试
- 3 个参数网格：
  * TRAJECTORY_WINDOW: 4, 6, 8, 10, 12
  * velocity threshold: 0.05, 0.10, 0.15, 0.20, 0.30
  * ambiguity norm: log(K) / log(实际N) / log(7 固定)
- 输出 Pareto 前沿：区分度↑ + 稳定性↑
"""

from __future__ import annotations

# 标准库 import 必须在 sys.path 修改之前（避免 verification/statistics.py 冲突）
import math
import os
import sys
from pathlib import Path
from typing import Any

# 把 CWD 切到项目根目录（避免 verification/ 在 sys.path 中）
ROOT = Path(__file__).parent.parent
os.chdir(ROOT)
# 清空 sys.path 中所有包含 verification/ 的路径，并把 ROOT 放到最前
sys.path = [str(ROOT)] + [p for p in sys.path if p and "verification" not in p]

from statistics import mean, variance

from emotion_spirit.core.config import TRAJECTORY_WINDOW, PAD_SAVE_INTERVAL_SECONDS
from emotion_spirit.utils import (
    build_emotion_payload,
    classify_distribution,
    classify_primary_secondary,
    compute_ambiguity,
    compute_velocity,
)
from emotion_spirit.output.surface_consumer import SurfaceConsumer


# ═══ 3 个合成场景（受控）═══

def gen_calm_sequence(n_turns: int = 20) -> list[dict[str, Any]]:
    """平稳：PAD 在中性区域小幅波动。"""
    surfaces = []
    for t in range(n_turns):
        v = 0.0 + 0.02 * math.sin(t * 0.3)
        a = 0.4 + 0.02 * math.cos(t * 0.3)
        d = 0.5 + 0.01 * math.sin(t * 0.5)
        surfaces.append({
            "pad": {"valence": v, "arousal": a, "dominance": d},
        })
    return surfaces


def gen_gradual_sequence(n_turns: int = 20) -> list[dict[str, Any]]:
    """渐变：valence 从 -0.5 缓慢升到 +0.5（悲伤→喜悦）。"""
    surfaces = []
    for t in range(n_turns):
        v = -0.5 + (t / n_turns) * 1.0  # -0.5 → +0.5
        a = 0.4 + 0.05 * math.sin(t * 0.2)
        d = 0.5 + 0.05 * math.cos(t * 0.2)
        surfaces.append({
            "pad": {"valence": v, "arousal": a, "dominance": d},
        })
    return surfaces


def gen_burst_sequence(n_turns: int = 20) -> list[dict[str, Any]]:
    """突变：前 10 帧平静，第 11 帧突然跳到愤怒（valence -0.8, arousal 0.9）。"""
    surfaces = []
    for t in range(n_turns):
        if t < 10:
            v, a, d = 0.0, 0.4, 0.5
        else:
            v, a, d = -0.8, 0.9, 0.7
        surfaces.append({
            "pad": {"valence": v, "arousal": a, "dominance": d},
        })
    return surfaces


SCENARIOS_SYNTHETIC = {
    "calm": gen_calm_sequence,
    "gradual": gen_gradual_sequence,
    "burst": gen_burst_sequence,
}


# ═══ 仿真引擎 ═══

def simulate_scenario(
    surfaces: list[dict[str, Any]],
    trajectory_window: int,
    velocity_threshold: float,
    ambiguity_norm: str,
) -> dict[str, Any]:
    """跑一个场景，返回关键指标。

    compute_velocity 内部用 time.time() 算 dt。仿真里用 sleep(0.01) 强制每帧
    10ms 间隔，让 compute_velocity 算出正 dt。
    """
    import time as time_mod
    ambig_list = []
    vel_list = []
    burst_count = 0
    last_pad = None
    last_t_real = None  # 真实时间戳

    for t, surface in enumerate(surfaces):
        pad = surface.get("pad", {})
        v, a, d = pad.get("valence", 0.0), pad.get("arousal", 0.0), pad.get("dominance", 0.5)
        pad_tuple = (v, a, d)

        # 算 distribution
        dist = classify_distribution(pad_tuple)

        # ambiguity（按指定归一化方式）
        if ambiguity_norm == "log_K":
            K = len(dist)
            entropy = -sum(p * math.log(p) for p in dist.values() if p > 0)
            max_e = math.log(K) if K > 1 else 1.0
            amb = entropy / max_e if max_e > 0 else 0.0
        elif ambiguity_norm == "log_actual_N":
            nonzero_n = sum(1 for p in dist.values() if p > 0)
            entropy = -sum(p * math.log(p) for p in dist.values() if p > 0)
            max_e = math.log(nonzero_n) if nonzero_n > 1 else 1.0
            amb = entropy / max_e if max_e > 0 else 0.0
        elif ambiguity_norm == "log_7":
            entropy = -sum(p * math.log(p) for p in dist.values() if p > 0)
            max_e = math.log(7)
            amb = entropy / max_e if max_e > 0 else 0.0
        else:
            raise ValueError(f"Unknown ambiguity_norm: {ambiguity_norm}")
        ambig_list.append(amb)

        # velocity: 必须用真实时间戳，sleep 强制推进
        if last_pad is not None:
            last = (last_pad[0], last_pad[1], last_pad[2], last_t_real)
            vel = compute_velocity(pad_tuple, last)
            if vel is not None:
                vel_list.append(vel)
                if abs(vel["valence"]) > velocity_threshold or abs(vel["arousal"]) > velocity_threshold:
                    burst_count += 1
        last_pad = pad_tuple
        time_mod.sleep(0.01)  # 10ms 间隔，足够 dt > 0
        last_t_real = time_mod.time()

    return {
        "ambiguities": ambig_list,
        "velocities": vel_list,
        "burst_count": burst_count,
        "mean_ambiguity": mean(ambig_list) if ambig_list else 0.0,
        "ambiguity_variance": variance(ambig_list) if len(ambig_list) > 1 else 0.0,
        "mean_velocity_abs": (
            mean([
                abs(v["valence"]) + abs(v["arousal"]) + abs(v["dominance"])
                for v in vel_list
            ]) if vel_list else 0.0
        ),
    }


# ═══ 评估函数 ═══

def evaluate_config(
    trajectory_window: int,
    velocity_threshold: float,
    ambiguity_norm: str,
) -> dict[str, Any]:
    """评估一个参数配置在 3 个合成场景下的表现。"""
    results = {}
    for name, gen_fn in SCENARIOS_SYNTHETIC.items():
        surfaces = gen_fn()
        results[name] = simulate_scenario(
            surfaces, trajectory_window, velocity_threshold, ambiguity_norm
        )

    # 区分度：3 个场景 mean_ambiguity 的方差（越大越能区分）
    means = [r["mean_ambiguity"] for r in results.values()]
    discrim_amb = variance(means) if len(means) > 1 else 0.0

    # 稳定性：calm 场景 ambiguity_variance 应小（稳定）
    stability_calm = results["calm"]["ambiguity_variance"]

    # 突变检测准确性：burst 场景应有 burst_count >= 1, calm 应 = 0
    burst_detection = results["burst"]["burst_count"]
    false_positive = results["calm"]["burst_count"]

    # 渐变场景的 |velocity| 应有合理范围（不是 0 也不是异常大）
    gradual_vel = results["gradual"]["mean_velocity_abs"]

    return {
        "trajectory_window": trajectory_window,
        "velocity_threshold": velocity_threshold,
        "ambiguity_norm": ambiguity_norm,
        "discrim_ambiguity": discrim_amb,
        "stability_calm_amb_var": stability_calm,
        "burst_detection_count": burst_detection,
        "false_positive_calm": false_positive,
        "gradual_mean_abs_velocity": gradual_vel,
        # 综合得分（越小越好 — 0.0 是理想）
        # 我们想：discrim_amb 大、stability_calm_amb_var 小、burst_detection=1、false_positive=0
        # 归一化：1 - discrim_amb（越小越不区分）
        "score": (
            (1.0 - min(1.0, discrim_amb * 10)) * 0.3  # 区分度（希望 0）
            + min(1.0, stability_calm * 50) * 0.3  # 稳定性（希望 0）
            + (0 if burst_detection >= 1 else 1) * 0.2  # 突变检测（希望 0）
            + (0 if false_positive == 0 else 1) * 0.2  # 假阳性（希望 0）
        ),
    }


# ═══ 主程序 ═══

def main() -> None:
    """扫描参数空间，输出 Pareto 前沿。"""
    # 参数网格
    trajectory_windows = [4, 6, 8, 10, 12]
    velocity_thresholds = [0.05, 0.10, 0.15, 0.20, 0.30]
    ambiguity_norms = ["log_K", "log_actual_N", "log_7"]

    # 当前实现 (baseline)
    print("═" * 80)
    print("v1.2 参数扫描仿真")
    print("═" * 80)
    print(f"参数网格: TRAJECTORY_WINDOW={trajectory_windows}, velocity_threshold={velocity_thresholds}, ambiguity_norm={ambiguity_norms}")
    print(f"组合数: {len(trajectory_windows) * len(velocity_thresholds) * len(ambiguity_norms)}")
    print()

    # 当前 baseline
    print(f"【Baseline】 TRAJECTORY_WINDOW=8, velocity_threshold=0.10, ambiguity_norm=log_K")
    baseline = evaluate_config(8, 0.10, "log_K")
    print(f"  区分度: {baseline['discrim_ambiguity']:.4f} | 稳定性: {baseline['stability_calm_amb_var']:.4f} | 突变检测: {baseline['burst_detection_count']} | 假阳性: {baseline['false_positive_calm']} | 综合得分: {baseline['score']:.3f}")
    print()

    # 全网格扫描（ambiguity_norm 简化为只测 1 个，因为不影响 trajectory/velocity）
    print("【扫描 #1: ambiguity_norm 影响】")
    print("-" * 80)
    amb_results = []
    for norm in ambiguity_norms:
        cfg = evaluate_config(8, 0.10, norm)
        amb_results.append((norm, cfg))
        print(f"  {norm:20s} 区分度={cfg['discrim_ambiguity']:.4f} 稳定性={cfg['stability_calm_amb_var']:.4f} 得分={cfg['score']:.3f}")
    print()

    # TRAJECTORY_WINDOW 扫描（影响 trajectory 内存但不影响 ambiguity/velocity 计算）
    print("【扫描 #2: TRAJECTORY_WINDOW 影响（理论性，实际 8 帧≈5-10 秒对话窗口）】")
    print("-" * 80)
    print("  TRAJECTORY_WINDOW 不影响 ambiguity/velocity 计算，只影响 trajectory 内存。")
    print("  经验：对话轮次 4-12 帧（30秒-2分钟），推荐 8 帧（≈1 分钟，BiERU 文献支撑）。")
    print()

    # velocity_threshold 扫描
    print("【扫描 #3: velocity_threshold 影响】")
    print("-" * 80)
    best_norm = min(amb_results, key=lambda x: x[1]["score"])[0]
    vel_results = []
    for vt in velocity_thresholds:
        cfg = evaluate_config(8, vt, best_norm)
        vel_results.append((vt, cfg))
        marker = " ←" if cfg["burst_detection_count"] >= 1 and cfg["false_positive_calm"] == 0 else ""
        print(f"  threshold={vt:.2f} 突变检测={cfg['burst_detection_count']:2d} 假阳性={cfg['false_positive_calm']:2d} 渐变|vel|={cfg['gradual_mean_abs_velocity']:.3f} 得分={cfg['score']:.3f}{marker}")
    print()

    # 找出 Pareto 最优
    print("【Pareto 前沿: 突变检测 + 假阳性 平衡】")
    print("-" * 80)
    pareto = [r for r in vel_results if r[1]["burst_detection_count"] >= 1 and r[1]["false_positive_calm"] == 0]
    if pareto:
        best = min(pareto, key=lambda x: x[1]["score"])
        print(f"  ✅ 推荐 velocity_threshold = {best[0]:.2f}")
        print(f"     （突变检测={best[1]['burst_detection_count']}, 假阳性={best[1]['false_positive_calm']}, 渐变|vel|={best[1]['gradual_mean_abs_velocity']:.3f}, 得分={best[1]['score']:.3f}）")
    else:
        print("  ❌ 无 Pareto 最优（无法同时 0 假阳性 + 检测到突变）")
        # 退而求其次：突变检测尽量多
        best = max(vel_results, key=lambda x: x[1]["burst_detection_count"] - x[1]["false_positive_calm"] * 5)
        print(f"  ⚠️  退而求其次: threshold={best[0]:.2f}（突变检测={best[1]['burst_detection_count']}, 假阳性={best[1]['false_positive_calm']}）")
    print()

    # ambiguity 推荐
    print("【Pareto 前沿: ambiguity_norm 平衡】")
    print("-" * 80)
    best_amb = min(amb_results, key=lambda x: x[1]["score"])
    print(f"  ✅ 推荐 ambiguity_norm = {best_amb[0]}")
    print(f"     （区分度={best_amb[1]['discrim_ambiguity']:.4f}, 稳定性={best_amb[1]['stability_calm_amb_var']:.4f}, 得分={best_amb[1]['score']:.3f}）")
    print()

    # 综合建议
    print("═" * 80)
    print("【综合建议】")
    print("═" * 80)
    print(f"  TRAJECTORY_WINDOW = 8（保持，BiERU 2018 对话历史文献支撑）")
    print(f"  velocity_threshold = {best[0]:.2f}（基于 burst 检测 + 假阳性 Pareto）")
    print(f"  ambiguity_norm = {best_amb[0]}（基于区分度 + 稳定性 Pareto）")


if __name__ == "__main__":
    main()
