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
    assert len(p["surface"]) == 8  # v1.7: 6→7 (autonomy_guard 拆为 2 维); v1.7.2: 7→8 (+gossip_tendency)
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


def test_all_personality_dims_is_13():
    """v1.7.2: label_mapper 必须暴露 13 维权威集合 (含 gossip_tendency)。"""
    from emotion_spirit.label_mapper import (
        ALL_PERSONALITY_DIMS,
        PERSONALITY_DIMS_DEEP,
        PERSONALITY_DIMS_SURFACE,
    )
    # 5 deep + 7 surface + gossip_tendency = 13
    assert len(PERSONALITY_DIMS_DEEP) == 5
    assert len(PERSONALITY_DIMS_SURFACE) == 8  # 7 原 + gossip_tendency
    assert len(ALL_PERSONALITY_DIMS) == 13
    # gossip_tendency 必须在 surface
    assert "gossip_tendency" in PERSONALITY_DIMS_SURFACE
    print("[OK] test_all_personality_dims_is_13")


def test_5_persona_gossip_tendency_baseline_within_hexaco_range():
    """v1.7.2: 5 persona gossip_tendency baseline 必须在 HEXACO 预测区间内。

    区间依据:
    - Erdoğan, Bauer, & Walter (2014): gossip_tendency 实证构念
    - Ashton & Lee (2007) HEXACO: H (Honesty-Humility) 反向 + E 正向 + A 反向
    - 5 persona 推断见 spec §三 P0-2a

    v1.7.2 (review fix): gossip_tendency 是 I/E 维度主导 (HEXACO E)
    公式: final = _BASELINE (0.40) + I/E delta
      - I-personas (ISTJ/INFP/ISFJ): 0.40 + (-0.25) = 0.15
      - E-personas (ENTP/ESTP): 0.40 + 0.30 = 0.70
    """
    from emotion_spirit.label_mapper import _BASELINE, PERSONA_BASELINES

    # (1) default baseline 是中位 0.40 (中性 default)
    assert _BASELINE["surface"].get("gossip_tendency") == 0.40, (
        f"default gossip_tendency 应是 0.40, 实际 {_BASELINE['surface'].get('gossip_tendency')}"
    )

    # (2) 5 persona gossip_tendency 值在 HEXACO 预测区间内
    # 区间: I-personas 0.10-0.20, E-personas 0.65-0.75
    hexaco_intervals = {
        "ISTJ-S":  (0.10, 0.20),  # I + S + T + J → 低 E
        "INFP-A":  (0.10, 0.20),  # I + F + P + A → 低 E
        "ISFJ-D":  (0.10, 0.20),  # I + S + F + D → 低 E
        "ENTP-AV": (0.65, 0.75),  # E + N + T + AV → 高 E
        "ESTP-A":  (0.65, 0.75),  # E + S + T + P → 高 E
    }
    for persona, (lo, hi) in hexaco_intervals.items():
        assert persona in PERSONA_BASELINES, f"{persona} 缺 PERSONA_BASELINES"
        actual = PERSONA_BASELINES[persona]["gossip_tendency"]
        assert lo <= actual <= hi, (
            f"{persona} gossip_tendency {actual} 不在 HEXACO 区间 [{lo}, {hi}]"
        )

    # (3) spread 验证: max - min >= 0.50 (I-vs-E 强烈对比)
    vals = [PERSONA_BASELINES[p]["gossip_tendency"] for p in hexaco_intervals]
    spread = max(vals) - min(vals)
    assert spread >= 0.50, f"5 persona gossip_tendency spread 应 >= 0.50, 实际 {spread}"


if __name__ == "__main__":
    test_clamp()
    test_labels_to_personality()
    test_labels_enfp()
    test_personality_to_labels()
    test_all_personality_dims_is_13()
    test_5_persona_gossip_tendency_baseline_within_hexaco_range()
    print("\n[OK] 所有测试通过")
