"""数据收集器 — 完整超我链路版本。

完整管线 (v2):
  DriftSimulator.step()                       ← 真实漂移
  → SurfaceConsumer.consume()                 ← 真实管线入口
  → ValueResistance.compute()                 ← 价值抵抗 (核心)
  → ConscienceTracker.record_*()              ← 良心事件
  → tick_pressure()                           ← 压力衰减 (关键!)
  → ValueAlignment.record()                   ← 对齐追踪
  → SuperegoGuard.assess()                    ← 安全层评估
  → SurfaceLogger.log()                       ← CSV 落盘

用法:
    python -m verification.data_collection.run_collection
    python -m verification.data_collection.run_collection --turns 200 --seed 7
    python -m verification.data_collection.run_collection --pipeline partial  # 对照旧版
"""

from __future__ import annotations

import io
import sys
import time
import argparse
from pathlib import Path
from collections import Counter, defaultdict

# Windows 控制台 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_this_dir = Path(__file__).parent
sys.path.insert(0, str(_this_dir.parent.parent))
sys.path.insert(0, str(_this_dir.parent))

from emotion_spirit.label_mapper import labels_to_personality
from emotion_spirit.surface_consumer import SurfaceConsumer
from emotion_spirit.superego import (
    ValueResistance, ValueAlignment, ConscienceTracker, IdealSelf,
)
from emotion_spirit.superego_guard import SuperegoGuard
from verification.surface_generator import (
    generate_bursty_scenario_sequence,
    SCENARIOS,
)
from verification.drift_simulator import DriftSimulator
from verification.surface_logger import SurfaceLogger


# ═══ 5 种代表性人格 ═══
PERSONAS: dict[str, dict[str, str]] = {
    "INFP-A": {
        "mbti": "INFP", "attachment": "焦虑型", "emotion_style": "表达型",
        "conflict_style": "顺应型", "time_focus": "活在当下",
        "note": "漂移方向已验证 (验证 A 阶段)",
    },
    "ISTJ-S": {
        "mbti": "ISTJ", "attachment": "安全型", "emotion_style": "混合型",
        "conflict_style": "合作型", "time_focus": "活在当下",
        "note": "基线对照 (压力低、漂移少)",
    },
    "ENTP-AV": {
        "mbti": "ENTP", "attachment": "回避型", "emotion_style": "表达型",
        "conflict_style": "攻击型", "time_focus": "活在未来",
        "note": "攻击型策略 (高 relational_autonomy)",  # v1.7: autonomy_guard 拆分
    },
    "ISFJ-D": {
        "mbti": "ISFJ", "attachment": "混乱型", "emotion_style": "压抑型",
        "conflict_style": "顺应型", "time_focus": "活在当下",
        "note": "压抑型策略 (低 expression_drive)",
    },
    "ESTP-A": {
        "mbti": "ESTP", "attachment": "焦虑型", "emotion_style": "表达型",
        "conflict_style": "攻击型", "time_focus": "活在当下",
        "note": "高唤醒 + 高行动力",
    },
}


def run_one_persona_full(
    persona_id: str,
    labels: dict[str, str],
    n_turns: int,
    seed: int,
    logger: SurfaceLogger,
    tick_hours: float = 5.0 / 60.0,  # 5 分钟/轮 (默认)
) -> dict[str, any]:
    """运行一个 persona 的完整管线数据收集。"""
    import random
    random.seed(seed)
    drift_sim = DriftSimulator(labels=labels)
    baseline = drift_sim.baseline

    # 真实 SurfaceConsumer
    consumer = SurfaceConsumer()

    # ★ 完整超我链路
    conscience = ConscienceTracker()
    alignment = ValueAlignment(f"data-{persona_id}")
    vr = ValueResistance(f"data-{persona_id}")
    vr._baseline_personality = baseline
    vr._interaction_count = 0
    ideal = IdealSelf(f"data-{persona_id}", labels)
    guard = SuperegoGuard(conscience, alignment, ideal, f"data-{persona_id}")

    # 突发式场景序列
    sequence = generate_bursty_scenario_sequence(n_turns, seed=seed)

    # 状态追踪
    scenario_counter: Counter = Counter()
    burst_turns: list[int] = []
    recovery_turns: list[int] = []
    peace_turns: list[int] = []
    tension_counter: Counter = Counter()
    safety_counter: Counter = Counter()
    guard_reject_count = 0
    cascade_count = 0
    final_personality: dict[str, float] = {}
    pressure_max = 0.0
    pressure_series: list[float] = []

    for turn, (scenario_name, profile) in enumerate(sequence, 1):
        scenario_counter[scenario_name] += 1

        if scenario_name in ("conflict", "boundary_invasion", "cascading", "trauma"):
            burst_turns.append(turn)
        elif scenario_name == "recovery":
            recovery_turns.append(turn)
        else:
            peace_turns.append(turn)

        is_cascade = scenario_name == "cascading"
        is_trauma = scenario_name == "trauma"
        if is_cascade or is_trauma:
            cascade_count += 1

        # 推进漂移
        personality = drift_sim.step(
            scenario_drift=profile.drift_direction,
            is_cascade=is_cascade,
            is_trauma=is_trauma,
        )

        # 表面消费
        surface = profile.generate_surface(personality, turn, noise=0.05)
        signals = consumer.consume(surface)

        # ★ 价值抵抗计算
        vr._interaction_count = turn
        vr._baseline_personality = labels_to_personality(labels)
        context = {
            "body_criticality": signals.body_criticality,
            "cascade_active": signals.cascade_active,
            "boundary_paused": signals.boundary_paused,
            "guard_risk_score": signals.guard_risk_score,
            "intimacy": 0.5,
        }
        stress_level = min(1.0, signals.body_criticality + (0.5 if signals.cascade_active else 0.0))
        resistance_result = vr.compute(
            action=signals.decision_action,
            context=context,
            current_personality=personality,
            stress_level=stress_level,
        )

        tension_counter[resistance_result.tension_type or "none"] += 1

        # ★ 良心事件记录
        if resistance_result.conflict_values:
            conscience.record_value_conflict(
                resistance=resistance_result.resistance,
                conflict_values=resistance_result.conflict_values,
                tension_type=resistance_result.tension_type or "guilt",
                behavioral_shift=resistance_result.behavioral_shift,
                conscience_impact=resistance_result.conscience_impact,
            )
        elif resistance_result.aligned_values:
            for v in resistance_result.aligned_values:
                conscience.record_alignment(v, signals.decision_action)

        if not signals.guard_allowed:
            conscience.record_guard_reflex(signals.guard_risk_score, signals.decision_reason)
            guard_reject_count += 1

        if signals.cascade_active:
            conscience.record_cascade(signals.cascade_intensity)

        conscience.record_collapse(signals.collapse_count)

        # ★ 关键: 压力衰减 (否则会锁死 1.0)
        conscience.tick_pressure(tick_hours)

        # ★ 对齐追踪
        alignment.record(signals.decision_action)

        # ★ 安全层评估 (传空 dict 代替 None, 与 simulation_runner 保持一致)
        intervention = guard.assess({}, personality)
        safety_counter[intervention.level] += 1

        # 收集压力
        current_pressure = conscience.get_pressure()
        pressure_series.append(current_pressure)
        if current_pressure > pressure_max:
            pressure_max = current_pressure

        # 记录到 CSV
        logger.log(
            session_id=f"data-{persona_id}",
            turn=turn,
            personality=personality,
            action=signals.decision_action,
            resistance=resistance_result.resistance,
            tension_type=resistance_result.tension_type or "",
            conflict_values=resistance_result.conflict_values or None,
            aligned_values=resistance_result.aligned_values or None,
            pressure=current_pressure,
            alignment_score=alignment.get_score(),
            safety_level=intervention.level,
            phi_smoothed=signals.phi_smoothed,
            body_criticality=signals.body_criticality,
            cascade_active=signals.cascade_active,
            guard_allowed=signals.guard_allowed,
            guard_risk_score=signals.guard_risk_score,
        )

        if turn == n_turns:
            final_personality = {
                "persona": persona_id,
                "expression_drive": personality["deep"]["expression_drive"],
                "perception_acuity": personality["deep"]["perception_acuity"],
                "boundary_permeability": personality["deep"]["boundary_permeability"],
                "inner_coherence": personality["deep"]["inner_coherence"],
                "relational_gravity": personality["deep"]["relational_gravity"],
                "warmth_bias": personality["surface"]["warmth_bias"],
                "directness": personality["surface"]["directness"],
                "curiosity": personality["surface"]["curiosity"],
                "patience": personality["surface"]["patience"],
                "intimacy_pull": personality["surface"]["intimacy_pull"],
                # v1.7: autonomy_guard 拆分为 2 维
                "relational_autonomy": personality["surface"]["relational_autonomy"],
                "exploration_openness": personality["surface"]["exploration_openness"],
            }

    return {
        "persona_id": persona_id,
        "n_turns": n_turns,
        "scenario_counts": dict(scenario_counter),
        "burst_turns": burst_turns,
        "recovery_turns": recovery_turns,
        "peace_turns": peace_turns,
        "n_burst": len(burst_turns),
        "n_recovery": len(recovery_turns),
        "n_peace": len(peace_turns),
        "tension_counts": dict(tension_counter),
        "safety_counts": dict(safety_counter),
        "guard_reject_count": guard_reject_count,
        "cascade_count": cascade_count,
        "pressure_max": pressure_max,
        "pressure_mean": sum(pressure_series) / len(pressure_series) if pressure_series else 0.0,
        "final_personality": final_personality,
        "baseline_personality": baseline,
    }


def run_one_persona_partial(
    persona_id: str,
    labels: dict[str, str],
    n_turns: int,
    seed: int,
    logger: SurfaceLogger,
) -> dict[str, any]:
    """运行一个 persona 的 partial 管线 (旧版, 仅 drift + consume + log)。"""
    import random
    random.seed(seed)
    drift_sim = DriftSimulator(labels=labels)
    baseline = drift_sim.baseline
    consumer = SurfaceConsumer()
    sequence = generate_bursty_scenario_sequence(n_turns, seed=seed)

    scenario_counter: Counter = Counter()
    burst_turns: list[int] = []
    recovery_turns: list[int] = []
    peace_turns: list[int] = []
    final_personality: dict[str, float] = {}

    for turn, (scenario_name, profile) in enumerate(sequence, 1):
        scenario_counter[scenario_name] += 1
        if scenario_name in ("conflict", "boundary_invasion", "cascading", "trauma"):
            burst_turns.append(turn)
        elif scenario_name == "recovery":
            recovery_turns.append(turn)
        else:
            peace_turns.append(turn)

        personality = drift_sim.step(
            scenario_drift=profile.drift_direction,
            is_cascade=scenario_name == "cascading",
            is_trauma=scenario_name == "trauma",
        )
        surface = profile.generate_surface(personality, turn, noise=0.05)
        signals = consumer.consume(surface)

        logger.log(
            session_id=f"data-{persona_id}",
            turn=turn,
            personality=personality,
            action=signals.decision_action,
            phi_smoothed=signals.phi_smoothed,
            body_criticality=signals.body_criticality,
            cascade_active=signals.cascade_active,
            guard_allowed=signals.guard_allowed,
            guard_risk_score=signals.guard_risk_score,
        )

        if turn == n_turns:
            final_personality = {
                "persona": persona_id,
                "expression_drive": personality["deep"]["expression_drive"],
                "boundary_permeability": personality["deep"]["boundary_permeability"],
                "inner_coherence": personality["deep"]["inner_coherence"],
                "intimacy_pull": personality["surface"]["intimacy_pull"],
                # v1.7: autonomy_guard 拆分为 2 维
                "relational_autonomy": personality["surface"]["relational_autonomy"],
                "exploration_openness": personality["surface"]["exploration_openness"],
            }

    return {
        "persona_id": persona_id,
        "n_turns": n_turns,
        "scenario_counts": dict(scenario_counter),
        "n_burst": len(burst_turns),
        "n_recovery": len(recovery_turns),
        "n_peace": len(peace_turns),
        "final_personality": final_personality,
    }


def main():
    parser = argparse.ArgumentParser(description="emotion_spirit 真实数据收集")
    parser.add_argument("--turns", type=int, default=100, help="每个 persona 轮次")
    parser.add_argument("--output-dir", type=str, default="verification/data_collection/output")
    parser.add_argument("--seed", type=int, default=7, help="随机种子")
    parser.add_argument("--pipeline", choices=["full", "partial"], default="full",
                        help="管线模式: full=完整超我链路, partial=仅 drift+consume")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 区分输出文件避免覆盖
    suffix = "_full" if args.pipeline == "full" else "_partial"
    log_filename_prefix = f"surface_log{suffix}_"

    # 找到或创建新的日志文件
    existing = list(output_dir.glob(f"{log_filename_prefix}*.csv"))
    if existing:
        # 复用最新文件 (追加模式)
        log_path = max(existing, key=lambda p: p.stat().st_mtime)
        print(f"⚠️  追加到现有日志: {log_path.name}")
        # 重置 logger 的 file 指针
        logger = SurfaceLogger.__new__(SurfaceLogger)
        logger._dir = output_dir
        logger._anonymize = False
        logger._max_age_days = 30
        logger._filepath = log_path
        logger._header_written = True  # 假设已写
        logger._fieldnames = [
            "timestamp", "session_id", "turn",
            "expression_drive", "perception_acuity", "boundary_permeability",
            "inner_coherence", "relational_gravity",
            "warmth_bias", "directness", "curiosity",
            "patience", "intimacy_pull",
            "relational_autonomy", "exploration_openness",  # v1.7: autonomy_guard 拆分
            "action", "phi_smoothed", "body_criticality", "cascade_active",
            "guard_allowed", "guard_risk_score",
            "resistance", "tension_type", "conflict_values", "aligned_values",
            "pressure", "alignment_score",
            "safety_level",
        ]
    else:
        logger = SurfaceLogger(
            output_dir=str(output_dir),
            anonymize=False,
            max_age_days=30,
        )
        # 重命名为 suffix 版本
        new_path = output_dir / f"{log_filename_prefix}{int(time.time())}.csv"
        logger._filepath = new_path
        # 重新创建文件
        if logger._filepath.exists():
            logger._filepath.unlink()

    print("=" * 60)
    print(f"emotion_spirit 数据收集 [{args.pipeline.upper()} 管线]")
    print("=" * 60)
    print(f"  人格数: {len(PERSONAS)}")
    print(f"  每人格轮次: {args.turns}")
    print(f"  总轮次: {len(PERSONAS) * args.turns}")
    print(f"  输出日志: {logger._filepath.name}")
    print(f"  随机种子: {args.seed}")
    print()

    start_time = time.time()
    all_results = []

    for i, (persona_id, labels) in enumerate(PERSONAS.items(), 1):
        print(f"[{i}/{len(PERSONAS)}] {persona_id}: {labels['note']}")
        if args.pipeline == "full":
            result = run_one_persona_full(
                persona_id=persona_id,
                labels=labels,
                n_turns=args.turns,
                seed=args.seed + i,
                logger=logger,
            )
        else:
            result = run_one_persona_partial(
                persona_id=persona_id,
                labels=labels,
                n_turns=args.turns,
                seed=args.seed + i,
                logger=logger,
            )
        all_results.append(result)
        print(f"  场景: {result['scenario_counts']}")
        if args.pipeline == "full":
            print(f"  Tension: {result['tension_counts']}")
            print(f"  Safety: {result['safety_counts']}")
            print(f"  Guard 拒绝: {result['guard_reject_count']} 次 | "
                  f"压力 max={result['pressure_max']:.3f} mean={result['pressure_mean']:.3f}")
        print()

    elapsed = time.time() - start_time
    total_turns = sum(r["n_turns"] for r in all_results)

    print("=" * 60)
    print(f"✅ 数据收集完成 [{args.pipeline}]")
    print("=" * 60)
    print(f"  总轮次: {total_turns}")
    print(f"  耗时: {elapsed:.2f}s")
    print(f"  日志文件: {logger._filepath.name}")
    print()

    if args.pipeline == "full":
        # 跨 persona 汇总
        print("跨 Persona 汇总 (FULL 管线):")
        print(f"  {'Persona':<10} {'Guard拒':<8} {'Tension':<35} {'Safety':<25} {'压力max':<8}")
        print(f"  {'-'*10} {'-'*8} {'-'*35} {'-'*25} {'-'*8}")
        for r in all_results:
            tension_str = ", ".join(f"{k}={v}" for k, v in r["tension_counts"].items())
            safety_str = ", ".join(f"{k}={v}" for k, v in r["safety_counts"].items())
            print(f"  {r['persona_id']:<10} "
                  f"{r['guard_reject_count']:<8} "
                  f"{tension_str[:33]:<35} "
                  f"{safety_str[:23]:<25} "
                  f"{r['pressure_max']:<8.3f}")

    # Persona 漂移对比
    print()
    print("Persona 最终人格参数对比 (关键维度):")
    print(f"  {'Persona':<10} {'intimacy':<10} {'autonomy':<10} {'bnd_perm':<10} {'inner_coh':<10}")
    print(f"  {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for r in all_results:
        fp = r["final_personality"]
        if fp:
            print(f"  {r['persona_id']:<10} "
                  f"{fp.get('intimacy_pull', 0):<10.3f} "
                  f"{fp.get('relational_autonomy', 0):<10.3f} "  # v1.7: autonomy_guard 拆分
                  f"{fp.get('boundary_permeability', 0):<10.3f} "
                  f"{fp.get('inner_coherence', 0):<10.3f}")


if __name__ == "__main__":
    main()
