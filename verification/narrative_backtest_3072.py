"""3072 大规模 narrative 回测 runner (Phase 3.0C Step 4)。

复用 3.0A + 3.0B + 3.0C 既有代码, 0 新算法:
- 3.0C `force_state_from_persona_id()`: KB hit 主入口 (PersonaId → ForceState)
- 3.0A `simulate_persona()`: 5 标签 + scenario + steps → force_trajectory
- 3.0A `KnowledgeBase.DIM_FORCE` 3-4-6 映射 (算法 H)

API 4 个:
- run_baseline_3072() → 3072 persona baseline ForceState (主目标: spec §4.3)
- run_neutral_3072(steps=5) → 3072 × neutral_only × N steps (Phase 3.5 dataset)
- run_5_fixture_sanity() → 5 fixture × 2 scenarios × 5 steps (3.0A regression)
- aggregate_dominant_distribution(baseline) → 3 force 分布 (含 confidence / MBTI breakdown)

CLI: python -m verification.narrative_backtest_3072 {baseline|neutral|sanity|all|analyze}
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from emotion_spirit.persona_labels_db import (
    force_state_from_persona_id,
    list_persona_ids,
    get_persona_entry,
)
from emotion_spirit.force_dynamics import ForceDynamics
from verification.drift_simulator import simulate_persona


# ═══ 1. baseline 3072 (主目标: spec §4.3 验证) ═══


def run_baseline_3072() -> dict[str, dict[str, Any]]:
    """3072 persona → baseline ForceState (无 scenario drift, 无 body_state, 无 conscience)。

    Returns:
        {persona_id: {
            "natural": float, "social": float, "individual": float,
            "dominant": str, "confidence": str,
        }}

    Performance:
        - KB 加载: ~32ms (3.0C 实测)
        - 3072 lookups: < 1s (1.0ms / 4 lookups, 线性)
    """
    t0 = time.perf_counter()
    results: dict[str, dict[str, Any]] = {}
    stats = {"kb_hit": 0, "fallback": 0}

    for persona_id in list_persona_ids():
        fs = force_state_from_persona_id(persona_id)
        # KB entry 拿 confidence (metadata)
        entry = get_persona_entry(persona_id)
        confidence = entry.get("confidence", "D") if entry else "D"
        results[persona_id] = {
            "natural": fs.natural,
            "social": fs.social,
            "individual": fs.individual,
            "dominant": fs.dominant,
            "confidence": confidence,
        }

    elapsed_ms = (time.perf_counter() - t0) * 1000
    results_meta = {
        "_meta": {
            "elapsed_ms": round(elapsed_ms, 2),
            "count": len(results),
            "stats": stats,
        }
    }
    # meta 跟 results 一起返回 (但保持 dict[str, dict] 形状, meta 作 special key)
    return {**results, **results_meta}


# ═══ 2. neutral_only 3072 (Phase 3.5 dataset) ═══


def run_neutral_3072(steps: int = 5) -> dict[str, dict[str, Any]]:
    """3072 persona × neutral_only × N steps → force_trajectory。

    Returns:
        {persona_id: {
            "trajectory": [ForceState.to_dict() × (steps+1)],
            "initial_fs": {natural, social, individual},
            "final_fs": {natural, social, individual},
            "drift_magnitude": float (sum of |FS_final - FS_initial| across 3 forces),
        }}

    Performance:
        - 3072 × 5 steps = 15360 step ops, expected ~5-15s (single-thread)

    Note:
        3.0C labels 用新词 (内敛型/竞争型/着眼未来) 跟 3.0A KnowledgeBase
        命名 (压抑型/攻击型/活在未来) 不兼容, simulate_persona 走 3.0A
        API 收 3.0C labels 会 KeyError. 本函数做 3.0C → 3.0A 翻译:
        - 表达型 → 表达型
        - 内敛型 → 压抑型
        - 稳定型 → 稳定型
        - 易变型 → 波动型
        - 合作型 → 合作型
        - 竞争型 → 攻击型
        - 回避型 → 回避型
        - 妥协型 → 顺应型
        - 关注过去 → 活在过去
        - 活在当下 → 活在当下
        - 着眼未来 → 活在未来
    """
    # 3.0C → 3.0A label translation (避免动 3.0A frozen 代码)
    LABEL_TRANSLATION = {
        "emotion_style": {
            "表达型": "表达型",
            "内敛型": "压抑型",
            "稳定型": "稳定型",
            "易变型": "波动型",
        },
        "conflict_style": {
            "合作型": "合作型",
            "竞争型": "攻击型",
            "回避型": "回避型",
            "妥协型": "顺应型",
        },
        "time_focus": {
            "关注过去": "活在过去",
            "活在当下": "活在当下",
            "着眼未来": "活在未来",
        },
    }

    t0 = time.perf_counter()
    results: dict[str, dict[str, Any]] = {}

    for persona_id in list_persona_ids():
        from emotion_spirit.persona_labels_db import parse_persona_id
        labels_3c = parse_persona_id(persona_id)
        if labels_3c is None:
            continue
        # 翻译 3.0C labels → 3.0A labels (3 段需翻译)
        labels_3a = {
            "mbti": labels_3c["mbti"],
            "attachment": labels_3c["attachment"],
            "emotion_style": LABEL_TRANSLATION["emotion_style"][labels_3c["emotion_style"]],
            "conflict_style": LABEL_TRANSLATION["conflict_style"][labels_3c["conflict_style"]],
            "time_focus": LABEL_TRANSLATION["time_focus"][labels_3c["time_focus"]],
        }
        # 跑 simulate_persona (3.0A + 3.0B Task 3 内含 force_trajectory)
        sim = simulate_persona(
            labels=labels_3a, scenario="neutral_only", steps=steps, persona_id=persona_id,
        )
        # 计算 drift magnitude: sum |final - initial| across 3 forces
        traj = sim.get("force_trajectory", [])
        if len(traj) >= 2:
            initial = traj[0]
            final = traj[-1]
            drift = (
                abs(final["natural"] - initial["natural"])
                + abs(final["social"] - initial["social"])
                + abs(final["individual"] - initial["individual"])
            )
        else:
            drift = 0.0
        results[persona_id] = {
            "trajectory": traj,
            "initial_fs": traj[0] if traj else None,
            "final_fs": traj[-1] if traj else None,
            "drift_magnitude": drift,
        }

    elapsed_ms = (time.perf_counter() - t0) * 1000
    results_meta = {
        "_meta": {
            "elapsed_ms": round(elapsed_ms, 2),
            "count": len(results),
            "steps": steps,
        }
    }
    return {**results, **results_meta}


# ═══ 3. 5 fixture sanity (3.0A Task 4 regression) ═══


def run_5_fixture_sanity(steps: int = 5) -> dict[str, Any]:
    """5 fixture × 2 scenarios (neutral_only, gossip_topic_heavy) × 5 steps。

    验证 runner 跟 3.0A Task 4 test_force_dynamics_simulation.py 行为对齐。

    Returns:
        {
            "sanity": {
                "baseline": {fixture_name: ForceState dict (含 dominant)},
                "neutral_only": {fixture_name: trajectory dict},
                "gossip_topic_heavy": {fixture_name: trajectory dict},
            }
        }
    """
    from tests.fixture_labels import (
        INFP_A_LABELS, ISTJ_S_LABELS, ENTP_AV_LABELS, ISFJ_D_LABELS, ESTP_A_LABELS,
        ALL_5_FIXTURE_NAMES,
    )
    fixture_labels = [
        INFP_A_LABELS, ISTJ_S_LABELS, ENTP_AV_LABELS, ISFJ_D_LABELS, ESTP_A_LABELS,
    ]

    # baseline (3.0A 直接走 force_state_from_labels)
    fd = ForceDynamics()
    baseline_results: dict[str, dict[str, Any]] = {}
    for name, labels in zip(ALL_5_FIXTURE_NAMES, fixture_labels):
        fs = fd.force_state_from_labels(labels)
        baseline_results[name] = {
            "natural": fs.natural,
            "social": fs.social,
            "individual": fs.individual,
            "dominant": fs.dominant,
        }

    # neutral_only + gossip_topic_heavy (3.0A + 3.0B Task 3)
    scenario_results: dict[str, dict[str, Any]] = {
        "neutral_only": {},
        "gossip_topic_heavy": {},
    }
    for scenario_name in ("neutral_only", "gossip_topic_heavy"):
        for name, labels in zip(ALL_5_FIXTURE_NAMES, fixture_labels):
            sim = simulate_persona(
                labels=labels, scenario=scenario_name, steps=steps, persona_id=name,
            )
            traj = sim.get("force_trajectory", [])
            if len(traj) >= 2:
                initial = traj[0]
                final = traj[-1]
                drift = (
                    abs(final["natural"] - initial["natural"])
                    + abs(final["social"] - initial["social"])
                    + abs(final["individual"] - initial["individual"])
                )
            else:
                drift = 0.0
            scenario_results[scenario_name][name] = {
                "trajectory": traj,
                "initial_fs": traj[0] if traj else None,
                "final_fs": traj[-1] if traj else None,
                "drift_magnitude": drift,
            }

    return {"sanity": {
        "baseline": baseline_results,
        "neutral_only": scenario_results["neutral_only"],
        "gossip_topic_heavy": scenario_results["gossip_topic_heavy"],
    }}


# ═══ 4. aggregate_dominant_distribution (Phase D: 分析) ═══


def aggregate_dominant_distribution(
    baseline: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """3072 baseline 聚合 dominant 分布 (含 confidence / MBTI / attachment breakdown)。

    Args:
        baseline: run_baseline_3072() 输出, 含 3072 persona_id → {natural, social, individual, dominant, confidence}

    Returns:
        {
            "overall": {natural: N1, social: N2, individual: N3, total: 3072},
            "by_confidence": {A: {...}, B: {...}, C: {...}, D: {...}},
            "by_mbti": {INFP: {...}, ENFP: ..., ISTJ: ..., ...},
            "by_attachment": {SE: {...}, AP: {...}, AV: {...}, DS: {...}},
        }
    """
    # 过滤 meta
    entries = {k: v for k, v in baseline.items() if not k.startswith("_")}

    def _init_count() -> dict[str, int]:
        return {"natural": 0, "social": 0, "individual": 0, "total": 0}

    def _accumulate(distribution: dict[str, int], dominant: str) -> None:
        distribution[dominant] += 1
        distribution["total"] += 1

    overall = _init_count()
    by_confidence: dict[str, dict[str, int]] = {
        "A": _init_count(), "B": _init_count(), "C": _init_count(), "D": _init_count(),
    }
    # 16 MBTI
    mbti_types = [
        "INFP", "ENFP", "INFJ", "ENFJ", "INTJ", "ENTJ", "INTP", "ENTP",
        "ISFP", "ESFP", "ISFJ", "ESFJ", "ISTP", "ESTP", "ISTJ", "ESTJ",
    ]
    by_mbti: dict[str, dict[str, int]] = {m: _init_count() for m in mbti_types}
    by_attachment: dict[str, dict[str, int]] = {
        "SE": _init_count(), "AP": _init_count(), "AV": _init_count(), "DS": _init_count(),
    }

    for persona_id, fs_dict in entries.items():
        dominant = fs_dict["dominant"]
        confidence = fs_dict["confidence"]
        _accumulate(overall, dominant)
        _accumulate(by_confidence[confidence], dominant)
        # 解析 persona_id: 5 段, 段 1 = MBTI, 段 2 = attachment
        parts = persona_id.split("-")
        mbti = parts[0]
        attach = parts[1]
        if mbti in by_mbti:
            _accumulate(by_mbti[mbti], dominant)
        if attach in by_attachment:
            _accumulate(by_attachment[attach], dominant)

    return {
        "overall": overall,
        "by_confidence": by_confidence,
        "by_mbti": by_mbti,
        "by_attachment": by_attachment,
    }


# ═══ 5. CLI 入口 ═══


def _save_json(data: dict[str, Any], output_path: Path) -> None:
    """写 JSON 到 output_path, 自动创建父目录。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, default=str)
    print(f"[saved] {output_path} ({output_path.stat().st_size / 1024 / 1024:.2f} MB)")


def _print_distribution_report(dist: dict[str, Any]) -> None:
    """打印 3072 dominant 分布报告 (CLI 友好)."""
    overall = dist["overall"]
    total = overall["total"]
    print(f"\n=== 3072 dominant 分布 (n={total}) ===")
    for force in ("natural", "social", "individual"):
        n = overall[force]
        pct = n / total * 100 if total else 0
        print(f"  {force:11s}: {n:4d} ({pct:5.1f}%)")

    print(f"\n=== by confidence (A=0, B=16, C=160, D=2896) ===")
    for conf, d in dist["by_confidence"].items():
        t = d["total"]
        if t == 0:
            print(f"  {conf}: 0 entries (skip)")
            continue
        line = f"  {conf} (n={t:4d}): "
        for force in ("natural", "social", "individual"):
            n = d[force]
            pct = n / t * 100
            line += f"{force}={n:3d} ({pct:4.1f}%)  "
        print(line)

    print(f"\n=== by MBTI (16 types × 192 entries each) ===")
    for mbti, d in dist["by_mbti"].items():
        t = d["total"]
        line = f"  {mbti} (n={t:3d}): "
        for force in ("natural", "social", "individual"):
            n = d[force]
            pct = n / t * 100 if t else 0
            line += f"{force[:3]}={n:3d} ({pct:4.1f}%) "
        print(line)

    print(f"\n=== by attachment (4 types × 768 entries each) ===")
    for attach, d in dist["by_attachment"].items():
        t = d["total"]
        line = f"  {attach} (n={t:4d}): "
        for force in ("natural", "social", "individual"):
            n = d[force]
            pct = n / t * 100 if t else 0
            line += f"{force[:3]}={n:3d} ({pct:4.1f}%) "
        print(line)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="3072 narrative backtest runner (Phase 3.0C Step 4)"
    )
    parser.add_argument(
        "command",
        choices=["baseline", "neutral", "sanity", "all", "analyze"],
        help="baseline=3072 baseline only | neutral=3072 × neutral_only × 5 steps | "
             "sanity=5 fixture × 2 scenarios | all=baseline+neutral+sanity | analyze=baseline+distribution report",
    )
    parser.add_argument("--steps", type=int, default=5, help="scenario steps (default 5)")
    parser.add_argument(
        "--output", type=str,
        default="verification/output/narrative_backtest_3072.json",
        help="output JSON path (default verification/output/narrative_backtest_3072.json)",
    )
    args = parser.parse_args()

    output_path = Path(args.output)

    if args.command == "baseline":
        results = run_baseline_3072()
        print(f"[baseline] {len(results) - 1} entries (excl _meta), "
              f"elapsed {results['_meta']['elapsed_ms']:.2f}ms")
        _save_json(results, output_path)

    elif args.command == "neutral":
        results = run_neutral_3072(steps=args.steps)
        print(f"[neutral] {len(results) - 1} entries, "
              f"elapsed {results['_meta']['elapsed_ms']:.2f}ms, "
              f"steps={args.steps}")
        _save_json(results, output_path)

    elif args.command == "sanity":
        results = run_5_fixture_sanity(steps=args.steps)
        print(f"[sanity] 5 fixture × 2 scenarios × {args.steps} steps")
        for scenario, runs in results["sanity"].items():
            if scenario == "baseline":
                print(f"  {scenario}:")
                for name, fs in runs.items():
                    print(f"    {name}: dominant={fs['dominant']}, "
                          f"({fs['natural']:.3f}/{fs['social']:.3f}/{fs['individual']:.3f})")
            else:
                print(f"  {scenario}:")
                for name, run in runs.items():
                    print(f"    {name}: drift={run['drift_magnitude']:.4f}, "
                          f"initial=({run['initial_fs']['natural']:.3f}/"
                          f"{run['initial_fs']['social']:.3f}/"
                          f"{run['initial_fs']['individual']:.3f}), "
                          f"final=({run['final_fs']['natural']:.3f}/"
                          f"{run['final_fs']['social']:.3f}/"
                          f"{run['final_fs']['individual']:.3f})")
        _save_json(results, output_path)

    elif args.command == "analyze":
        if not output_path.exists():
            print(f"[analyze] {output_path} 不存在, 先跑 'baseline'")
            return
        with open(output_path, "r", encoding="utf-8") as f:
            baseline = json.load(f)
        dist = aggregate_dominant_distribution(baseline)
        _print_distribution_report(dist)

    elif args.command == "all":
        # baseline → neutral → sanity, 合并写一个 JSON
        sanity_results = run_5_fixture_sanity(steps=args.steps)
        baseline_results = run_baseline_3072()
        neutral_results = run_neutral_3072(steps=args.steps)
        all_results = {
            "sanity": sanity_results["sanity"],
            "baseline": {k: v for k, v in baseline_results.items() if not k.startswith("_")},
            "neutral_only_5steps": {k: v for k, v in neutral_results.items() if not k.startswith("_")},
            "_meta": {
                "sanity_elapsed_ms": 0,  # sanity 不计
                "baseline_elapsed_ms": baseline_results["_meta"]["elapsed_ms"],
                "neutral_elapsed_ms": neutral_results["_meta"]["elapsed_ms"],
                "total_entries": len(baseline_results) - 1,
                "neutral_steps": args.steps,
            },
        }
        print(f"[all] 5 fixture sanity + {len(baseline_results) - 1} baseline + "
              f"{len(neutral_results) - 1} neutral_only × {args.steps} steps")
        _save_json(all_results, output_path)


if __name__ == "__main__":
    main()
