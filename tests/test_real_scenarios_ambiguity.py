"""v1.3: 真实场景 ambiguity 区分度测试。

v1.2 仿真发现问题：所有场景的 ambiguity 都在 0.74-0.91，
区分度极差。v1.3 用 1 - max(p) 应能让不同场景有显著不同的 ambiguity。

注：场景数据内联（不依赖 verification/），确保三目录同步后能跑。
源数据来自 verification/surface_generator.py SCENARIOS (PAD base_surface)。
"""

import os
import sys
from pathlib import Path

# 添加项目根到 path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from emotion_spirit.emotion_classifier import compute_ambiguity, classify_distribution


# 8 个 SCENARIOS 的 PAD 中心点（来自 verification/surface_generator.py）
SCENARIOS = {
    "safe_companionship":   (0.60, 0.30, 0.60),
    "conflict":             (-0.40, 0.70, 0.30),
    "cascading":            (-0.70, 0.90, 0.10),
    "recovery":             (0.30, 0.30, 0.50),
    "daily_neutral":        (0.00, 0.30, 0.50),
    "boundary_invasion":    (-0.50, 0.60, 0.20),
    "intimacy_growth":      (0.70, 0.40, 0.60),
    "trauma":               (-0.90, 0.95, 0.00),
}


def _get_scenario_ambiguity(name: str) -> float:
    """辅助: 算指定 SCENARIOS 的 ambiguity。"""
    v, a, d = SCENARIOS[name]
    dist = classify_distribution((v, a, d))
    return compute_ambiguity(dist)


def test_real_scenarios_have_meaningful_ambiguity_spread():
    """v1.3 验证: 8 个 SCENARIOS 的 ambiguity 应该有显著差异 (max - min > 0.15)。"""
    results = []
    for name in SCENARIOS:
        amb = _get_scenario_ambiguity(name)
        results.append((name, amb))
        print(f"  {name:25s} amb={amb:.3f}")

    amb_values = [amb for _, amb in results]
    spread = max(amb_values) - min(amb_values)
    print(f"\n  max={max(amb_values):.3f}  min={min(amb_values):.3f}  spread={spread:.3f}")
    # v1.3 区分度门槛: spread > 0.15
    assert spread > 0.15, (
        f"区分度不足: spread={spread:.3f} <= 0.15\n"
        f"结果: {results}"
    )


def test_daily_neutral_is_more_determined_than_conflict():
    """v1.3 验证: daily_neutral 应当比 conflict 更"确定" (ambiguity 更低)。"""
    daily_amb = _get_scenario_ambiguity("daily_neutral")
    conflict_amb = _get_scenario_ambiguity("conflict")
    assert daily_amb < conflict_amb, (
        f"daily_neutral ({daily_amb}) 应比 conflict ({conflict_amb}) 更确定"
    )


if __name__ == "__main__":
    test_real_scenarios_have_meaningful_ambiguity_spread()
    test_daily_neutral_is_more_determined_than_conflict()
    print("\nAll real scenarios ambiguity tests passed!")
