"""v1.3: 真实场景 ambiguity 区分度测试。

v1.2 仿真发现问题：所有 8 个 SCENARIOS 的 ambiguity 都在 0.74-0.91，
区分度极差。v1.3 用 1 - max(p) 应能让不同场景有显著不同的 ambiguity。
"""

import sys
from pathlib import Path

# 添加项目根到 path（必须在导入 SCENARIOS 之前）
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from emotion_spirit.emotion_classifier import compute_ambiguity, classify_distribution
from verification.surface_generator import SCENARIOS


def _get_scenario_ambiguity(name: str) -> float:
    """辅助: 算指定 SCENARIOS 的 ambiguity。"""
    profile = SCENARIOS[name]
    pad_dict = profile.base_surface.get("pad", {})
    v = pad_dict.get("valence", 0.0)
    a = pad_dict.get("arousal", 0.0)
    d = pad_dict.get("dominance", 0.5)
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
