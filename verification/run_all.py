"""一键运行所有验证: D(理论) + C(属性测试) + A(模拟)

用法:
    cd astrbot_plugin_emotion_spirit
    python -m verification.run_all

    # 仅运行某阶段:
    python -m verification.run_all --phase D
    python -m verification.run_all --phase C
    python -m verification.run_all --phase A
    python -m verification.run_all --phase A --turns 5000 --labels INFP
"""

import argparse
import io
import sys
from pathlib import Path

# Windows 控制台 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 确保可以导入 emotion_spirit 和 verification 子模块
_this_dir = Path(__file__).parent
sys.path.insert(0, str(_this_dir.parent))
sys.path.insert(0, str(_this_dir))


def run_theory():
    """运行阶段 D: 理论分析。"""
    print("\n" + "=" * 60)
    print("阶段 D: 理论分析")
    print("=" * 60 + "\n")

    from theory_proofs import run_all_proofs, generate_theory_report

    results = run_all_proofs()
    report = generate_theory_report(results)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    (output_dir / "theory_report.md").write_text(report, encoding="utf-8")

    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    print(f"\n理论分析: {passed}/{total} 通过")
    print(report)

    return passed == total


def run_property_tests():
    """运行阶段 C: 属性测试。"""
    print("\n" + "=" * 60)
    print("阶段 C: 属性测试")
    print("=" * 60 + "\n")

    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "property_tests.py", "-v", "--tb=short", "-x"],
        cwd=str(Path(__file__).parent),
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    (output_dir / "property_test_report.txt").write_text(
        result.stdout + "\n" + result.stderr, encoding="utf-8"
    )

    return result.returncode == 0


def run_simulation(turns: int = 1000, labels_name: str = "INFP-焦虑"):
    """运行阶段 A: 蒙特卡洛模拟。"""
    print("\n" + "=" * 60)
    print(f"阶段 A: 蒙特卡洛模拟 (N={turns}, 标签={labels_name})")
    print("=" * 60 + "\n")

    from simulation_runner import SimulationRunner
    from statistics import generate_simulation_report

    LABELS_MAP = {
        "INFP-焦虑": {"mbti": "INFP", "attachment": "焦虑型", "emotion_style": "表达型", "conflict_style": "顺应型", "time_focus": "活在当下"},
        "ISTJ-安全": {"mbti": "ISTJ", "attachment": "安全型", "emotion_style": "混合型", "conflict_style": "合作型", "time_focus": "活在当下"},
        "ENTP-回避": {"mbti": "ENTP", "attachment": "回避型", "emotion_style": "表达型", "conflict_style": "攻击型", "time_focus": "活在未来"},
        "ISFJ-混乱": {"mbti": "ISFJ", "attachment": "混乱型", "emotion_style": "压抑型", "conflict_style": "顺应型", "time_focus": "活在当下"},
        "ESTP-焦虑": {"mbti": "ESTP", "attachment": "焦虑型", "emotion_style": "表达型", "conflict_style": "攻击型", "time_focus": "活在当下"},
    }

    labels = LABELS_MAP.get(labels_name, LABELS_MAP["INFP-焦虑"])

    runner = SimulationRunner(labels=labels, n_turns=turns, seed=42)
    snapshots = runner.run()

    # 保存数据
    csv_path = runner.save_csv()

    # 生成报告
    report = generate_simulation_report(snapshots)
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    (output_dir / "simulation_report.md").write_text(report, encoding="utf-8")

    print(report)
    print(f"\n数据已保存到: {csv_path}")

    # 验收检查
    from statistics import compute_core_peripheral_ratio
    ratio = compute_core_peripheral_ratio(snapshots)
    critical_pct = sum(1 for s in snapshots if s.safety_level == "critical") / len(snapshots) if snapshots else 1

    print(f"\n验收检查:")
    print(f"  核心/边缘区分度: {ratio['mean_ratio']:.2f}x {'✅' if ratio['mean_ratio'] >= 3.0 else '❌'} (目标: ≥3.0x)")
    print(f"  critical 触发率: {critical_pct:.2%} {'✅' if critical_pct < 0.10 else '❌'} (目标: <10%)")

    return ratio["mean_ratio"] >= 3.0 and critical_pct < 0.10


def main():
    parser = argparse.ArgumentParser(description="emotion_spirit 长期漂移验证")
    parser.add_argument("--phase", choices=["D", "C", "A", "all"], default="all")
    parser.add_argument("--turns", type=int, default=1000, help="模拟轮次")
    parser.add_argument("--labels", default="INFP-焦虑", help="人格标签组合")
    args = parser.parse_args()

    results = {}

    if args.phase in ("D", "all"):
        results["D"] = run_theory()

    if args.phase in ("C", "all"):
        results["C"] = run_property_tests()

    if args.phase in ("A", "all"):
        results["A"] = run_simulation(turns=args.turns, labels_name=args.labels)

    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    for phase, passed in results.items():
        print(f"  阶段 {phase}: {'✅ 通过' if passed else '❌ 失败'}")

    all_passed = all(results.values())
    print(f"\n总体结果: {'✅ 全部通过' if all_passed else '❌ 存在失败'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
