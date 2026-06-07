"""理论分析验证脚本。

验证 D-1 到 D-12 的所有理论性质。
输出: output/theory_report.md
"""

import math
import json
from pathlib import Path


def s_curve(x: float) -> float:
    """S 曲线非线性映射。"""
    return (x - 0.5) ** 3 * 4 + 0.5


def s_curve_derivative(x: float) -> float:
    """S 曲线导数。"""
    return 12 * (x - 0.5) ** 2


def anchor_strength(n: int, anchor_base: float = 0.3, anchor_decay: float = 3000) -> float:
    """基线引力强度。"""
    return anchor_base * (1.0 / (1.0 + n / anchor_decay))


def pressure_decay(p0: float, hours: float, rate: float = 0.08) -> float:
    """良心压力衰减。

    rate=0.08/hr → 半衰期约 8.3h
    理论依据：自尊稳定性研究 (N=3180, 29年追踪) 显示指数衰减向非零渐近线；
    道德脱离研究显示预期愧疚可被抑制但事后愧疚重新出现；
    日常愧疚体验的"睡一觉好一半"时间尺度约数小时。
    """
    return p0 * (1 - rate) ** hours


def verify_d1_fixed_points() -> dict:
    """D-1: S曲线不动点。"""
    fixed_points = []
    for x_int in range(0, 1001):
        x = x_int / 1000
        if abs(s_curve(x) - x) < 0.001:
            fixed_points.append(round(x, 4))
    return {
        "id": "D-1",
        "name": "S曲线不动点",
        "found": fixed_points,
        "expected": [0.0, 0.5, 1.0],
        "passed": set(fixed_points) >= {0.0, 0.5, 1.0},
    }


def verify_d2_monotonicity() -> dict:
    """D-2: S曲线单调性。"""
    min_derivative = min(s_curve_derivative(x / 100) for x in range(101))
    return {
        "id": "D-2",
        "name": "S曲线单调性",
        "min_derivative": min_derivative,
        "passed": min_derivative >= 0,
    }


def verify_d3_endpoints() -> dict:
    """D-3: S曲线端点。"""
    return {
        "id": "D-3",
        "name": "S曲线端点",
        "f0": round(s_curve(0.0), 6),
        "f1": round(s_curve(1.0), 6),
        "f05": round(s_curve(0.5), 6),
        "passed": (
            abs(s_curve(0.0)) < 0.001
            and abs(s_curve(1.0) - 1.0) < 0.001
            and abs(s_curve(0.5) - 0.5) < 0.001
        ),
    }


def verify_d4_differentiation_gain() -> dict:
    """D-4: S曲线区分度增益。"""
    deep_vals = [0.65, 0.70, 0.95, 0.40, 0.20]
    surface_vals = [0.30, 0.85, 0.60, 0.70, 0.15, 0.90]

    linear_deep = sum(deep_vals) / len(deep_vals)
    linear_surface = sum(surface_vals) / len(surface_vals)
    linear_ratio = linear_deep / linear_surface if linear_surface > 0 else float("inf")

    s_deep = [s_curve(v) for v in deep_vals]
    s_surface = [s_curve(v) for v in surface_vals]
    s_deep_mean = sum(s_deep) / len(s_deep)
    s_surface_mean = sum(s_surface) / len(s_surface)
    s_ratio = s_deep_mean / s_surface_mean if s_surface_mean > 0 else float("inf")

    return {
        "id": "D-4",
        "name": "S曲线区分度增益",
        "linear_ratio": round(linear_ratio, 3),
        "s_curve_ratio": round(s_ratio, 3),
        "gain": round(s_ratio / linear_ratio, 3) if linear_ratio > 0 else 0,
        "passed": s_ratio > linear_ratio,
    }


def verify_d5_topk_differentiation() -> dict:
    """D-5: Top-K 核心维度区分度。"""
    from emotion_spirit.label_mapper import _BASELINE
    from emotion_spirit.superego import ValueResistance

    labels = {
        "mbti": "INFP", "attachment": "焦虑型",
        "emotion_style": "表达型", "conflict_style": "顺应型", "time_focus": "活在当下",
    }
    personality = {
        "deep": {
            "expression_drive": 0.65,
            "perception_acuity": 0.65,
            "boundary_permeability": 0.75,
            "inner_coherence": 0.55,
            "relational_gravity": 0.55,
        },
        "surface": {
            "warmth_bias": 0.65,
            "directness": 0.60,
            "curiosity": 0.75,
            "patience": 0.55,
            "intimacy_pull": 0.45,
            # v1.7: autonomy_guard 拆分为 2 维
            "relational_autonomy": 0.40,
            "exploration_openness": 0.50,
        },
    }

    vr = ValueResistance("test_persona")
    vr._baseline_personality = personality
    vr._interaction_count = 100

    weights = vr._build_value_system(personality, stress_level=0.0)

    sorted_dims = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    core = sorted_dims[:5]
    peripheral = sorted_dims[5:]

    core_mean = sum(w for _, w in core) / len(core) if core else 0
    peripheral_mean = sum(w for _, w in peripheral) / len(peripheral) if peripheral else 0

    ratio = core_mean / peripheral_mean if peripheral_mean > 0 else float("inf")

    return {
        "id": "D-5",
        "name": "Top-K 核心维度区分度",
        "core_dims": [(d, round(w, 4)) for d, w in core],
        "peripheral_dims": [(d, round(w, 4)) for d, w in peripheral],
        "core_mean": round(core_mean, 4),
        "peripheral_mean": round(peripheral_mean, 4),
        "ratio": round(ratio, 2),
        "passed": ratio >= 2.0,
    }


def verify_d6_anchor_decay() -> dict:
    """D-6: 基线引力衰减趋向 0。"""
    values = [anchor_strength(n) for n in [0, 100, 1000, 3000, 10000, 100000]]
    return {
        "id": "D-6",
        "name": "基线引力衰减趋向0",
        "values": {str(n): round(v, 6) for n, v in zip(
            [0, 100, 1000, 3000, 10000, 100000], values
        )},
        "passed": values[-1] < 0.01,
    }


def verify_d7_anchor_half_life() -> dict:
    """D-7: 基线引力半衰期。"""
    a0 = anchor_strength(0)
    a3000 = anchor_strength(3000)
    return {
        "id": "D-7",
        "name": "基线引力半衰期",
        "a0": round(a0, 6),
        "a3000": round(a3000, 6),
        "ratio": round(a3000 / a0, 6) if a0 > 0 else 0,
        "passed": abs(a3000 / a0 - 0.5) < 0.01 if a0 > 0 else False,
    }


def verify_d8_gravity_direction() -> dict:
    """D-8: 基线引力方向 — 当前值>基线时引力拉回。"""
    baseline_val = 0.5
    current_high = 0.8
    current_low = 0.2
    current_equal = 0.5

    anchor = 0.3
    stress_boost = 1.0

    deviation_high = current_high - baseline_val
    gravity_high = deviation_high * anchor * stress_boost

    deviation_low = current_low - baseline_val
    gravity_low = deviation_low * anchor * stress_boost

    deviation_equal = current_equal - baseline_val
    gravity_equal = deviation_equal * anchor * stress_boost

    return {
        "id": "D-8",
        "name": "基线引力方向",
        "above_baseline": {
            "deviation": round(deviation_high, 4),
            "gravity": round(gravity_high, 4),
            "effect": "weight decreases (pulls toward baseline)",
        },
        "below_baseline": {
            "deviation": round(deviation_low, 4),
            "gravity": round(gravity_low, 4),
            "effect": "weight increases (pulls toward baseline)",
        },
        "at_baseline": {
            "deviation": 0.0,
            "gravity": 0.0,
            "effect": "no gravity",
        },
        "passed": gravity_high > 0 and gravity_low < 0 and gravity_equal == 0,
    }


def verify_d9_pressure_decay() -> dict:
    """D-9: 压力指数衰减半衰期。

    rate=0.08/hr → 半衰期约 8.3h
    理论依据：
    - 自尊稳定性研究 (N=3180) 显示指数衰减向渐近线 0.43
    - Roberts 元分析: 成人稳定性 r≈0.65, 半衰期约 7 年 (人格层面)
    - 良心压力是事件驱动的短期信号, 半衰期在小时级别更合理
    - "睡一觉好一半" 的日常体验对应约 8h 半衰期
    """
    decay_rate = 0.08
    half_life = math.log(2) / math.log(1 / (1 - decay_rate))
    p_24h = pressure_decay(1.0, 24, decay_rate)
    p_8h = pressure_decay(1.0, 8, decay_rate)
    return {
        "id": "D-9",
        "name": "压力指数衰减",
        "decay_rate": decay_rate,
        "half_life_hours": round(half_life, 1),
        "expected_half_life": "~8.3h",
        "p_8h": round(p_8h, 4),
        "p_24h": round(p_24h, 4),
        "p_48h": round(pressure_decay(1.0, 48, decay_rate), 4),
        "passed": 8 < half_life < 10,
    }


def verify_d10_ema_convergence() -> dict:
    """D-10: EMA fast/slow 收敛时间常量。"""
    tau_fast = 1 / 0.039
    tau_slow = 1 / 0.004
    return {
        "id": "D-10",
        "name": "EMA 收敛时间常量",
        "alpha_fast": 0.039,
        "alpha_slow": 0.004,
        "tau_fast": round(tau_fast, 1),
        "tau_slow": round(tau_slow, 1),
        "passed": 20 < tau_fast < 35 and 200 < tau_slow < 280,
    }


def verify_d11_tension_mapping() -> dict:
    """D-11: tension 分类映射。"""
    from emotion_spirit.knowledge import KnowledgeBase

    tension_map = KnowledgeBase.TENSION_INCLINATION
    checks = {
        "autonomy_guard_is_shame": tension_map.get("relational_autonomy") == "shame",  # v1.7: 替换 autonomy_guard
        "relational_gravity_is_guilt": tension_map.get("relational_gravity") == "guilt",
        "inner_coherence_is_doubt": tension_map.get("inner_coherence") == "doubt",
        "all_dims_covered": len(tension_map) >= 8,
        "only_valid_types": all(
            v in ("guilt", "doubt", "shame", "righteous", "value_conflict") for v in tension_map.values()
        ),
    }
    return {
        "id": "D-11",
        "name": "tension 分类映射",
        "tension_map": tension_map,
        "checks": checks,
        "passed": all(checks.values()),
    }


def verify_d12_slope_direction() -> dict:
    """D-12: EMA slope 方向与趋势一致。"""
    from emotion_spirit.trend_utils import TrendDetector

    td_inc = TrendDetector(0.1, 0.01)
    for v in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        td_inc.update(v)

    td_dec = TrendDetector(0.1, 0.01)
    for v in [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0]:
        td_dec.update(v)

    td_flat = TrendDetector(0.1, 0.01)
    for _ in range(10):
        td_flat.update(0.5)

    return {
        "id": "D-12",
        "name": "EMA slope 方向",
        "increasing_slope": round(td_inc.slope(7), 6),
        "decreasing_slope": round(td_dec.slope(7), 6),
        "stable_slope": round(td_flat.slope(7), 6),
        "passed": td_inc.slope(7) > 0 and td_dec.slope(7) < 0 and abs(td_flat.slope(7)) < 0.01,
    }


def run_all_proofs() -> list[dict]:
    """运行所有理论验证。"""
    verifiers = [
        verify_d1_fixed_points,
        verify_d2_monotonicity,
        verify_d3_endpoints,
        verify_d4_differentiation_gain,
        verify_d5_topk_differentiation,
        verify_d6_anchor_decay,
        verify_d7_anchor_half_life,
        verify_d8_gravity_direction,
        verify_d9_pressure_decay,
        verify_d10_ema_convergence,
        verify_d11_tension_mapping,
        verify_d12_slope_direction,
    ]
    results = []
    for v in verifiers:
        try:
            results.append(v())
        except Exception as e:
            results.append({"id": "?", "name": v.__name__, "passed": False, "error": str(e)})
    return results


def generate_theory_report(results: list[dict]) -> str:
    """生成 Markdown 报告。"""
    lines = ["# 理论分析验证报告\n"]
    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    lines.append(f"**通过率**: {passed}/{total} ({passed/total*100:.0f}%)\n")

    for r in results:
        status = "✅" if r.get("passed") else "❌"
        lines.append(f"\n## {status} {r['id']}: {r['name']}\n")
        for k, v in r.items():
            if k not in ("id", "name", "passed"):
                lines.append(f"- **{k}**: {v}")
        lines.append(f"- **结果**: {'通过' if r.get('passed') else '失败'}\n")

    return "\n".join(lines)


if __name__ == "__main__":
    results = run_all_proofs()
    report = generate_theory_report(results)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    (output_dir / "theory_report.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"\n报告已写入 output/theory_report.md")
