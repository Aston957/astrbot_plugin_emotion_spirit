"""label_mapper 测试。"""

import sys
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotion_spirit.label_mapper import (
    clamp,
    labels_to_personality,
    personality_to_labels,
)


def test_clamp():
    assert clamp(0.5) == 0.5
    assert clamp(-0.1) == 0.0
    assert clamp(1.1) == 1.0
    assert clamp(0.7, 0.0, 0.5) == 0.5
    print("[OK] test_clamp")


def test_labels_to_personality():
    """测试标签到 12 维参数的映射 (v1.7: 11→12)。"""
    # ISTJ 基线
    labels = {
        "mbti": "ISTJ",
        "attachment": "安全型",
        "emotion_style": "混合型",
        "conflict_style": "合作型",
        "time_focus": "活在当下",
    }
    p = labels_to_personality(labels)
    assert "deep" in p
    assert "surface" in p
    assert len(p["deep"]) == 5
    assert len(p["surface"]) == 7  # v1.7: 6→7 (autonomy_guard 拆为 2 维)
    assert all(0.0 <= v <= 1.0 for v in p["deep"].values())
    assert all(0.0 <= v <= 1.0 for v in p["surface"].values())
    print("[OK] test_labels_to_personality (ISTJ baseline, 12 dims)")


def test_labels_enfp():
    """测试 ENFP 标签映射。"""
    labels = {
        "mbti": "ENFP",
        "attachment": "焦虑型",
        "emotion_style": "表达型",
        "conflict_style": "顺应型",
        "time_focus": "活在当下",
    }
    p = labels_to_personality(labels)
    # ENFP 应该有较高的 warmth_bias 和 intimacy_pull
    assert p["surface"]["warmth_bias"] > 0.7
    assert p["surface"]["intimacy_pull"] > 0.5
    print("[OK] test_labels_enfp")


def test_personality_to_labels():
    """测试 12 维参数到标签的反向推断 (v1.7: 11→12)。"""
    p = {
        "deep": {
            "expression_drive": 0.75,
            "perception_acuity": 0.85,
            "boundary_permeability": 0.90,
            "inner_coherence": 0.75,
            "relational_gravity": 0.35,
        },
        "surface": {
            "warmth_bias": 0.90,
            "directness": 0.75,
            "curiosity": 0.75,
            "patience": 0.75,
            "intimacy_pull": 0.80,
            # v1.7: autonomy_guard 拆为 relational_autonomy + exploration_openness
            "relational_autonomy": 0.35,
            "exploration_openness": 0.50,
        },
    }
    labels = personality_to_labels(p)
    # 反向推断应该返回有效的标签
    assert "mbti" in labels
    assert len(labels["mbti"]) == 4
    print(f"[OK] test_personality_to_labels: {labels}")


if __name__ == "__main__":
    test_clamp()
    test_labels_to_personality()
    test_labels_enfp()
    test_personality_to_labels()
    print("\n[OK] 所有测试通过")
