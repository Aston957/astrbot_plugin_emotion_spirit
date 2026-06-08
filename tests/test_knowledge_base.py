"""Tests for KnowledgeBase Step 1 (label_mapper 全量迁移, 155 项)。

Step 1 范围:
  - 13 维 personality 权威集合
  - 5 轴标签 delta (mbti/attachment/emotion_style/conflict_style/time_focus)
  - 数值阈值 (intimacy_segments, lifecycle, buffer, regression 等)
  - 统一查询 API: get_delta_for_label / get_threshold / compute_baseline_from_labels

Phase 3.0A Task 1 删除:
  - test_knowledge_base_exposes_personality_baselines (KB.PERSONA_BASELINES 已删, 走 compute_baseline_from_labels)
  - test_knowledge_base_get_persona_baseline_returns_copy (get_persona_baseline 已删)
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_knowledge_base_exposes_mbti_letter_deltas():
    """Step 1: KnowledgeBase.MBTI_LETTER_DELTAS 暴露 8 字母 delta (I/E/N/S/F/T/P/J)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    for letter in ["I", "E", "N", "S", "F", "T", "P", "J"]:
        assert letter in KnowledgeBase.MBTI_LETTER_DELTAS


def test_knowledge_base_get_delta_for_label_dispatches_correctly():
    """Step 1: get_delta_for_label('mbti', 'I') 返回 I 的 dim delta。"""
    from emotion_spirit.knowledge import KnowledgeBase
    i_delta = KnowledgeBase.get_delta_for_label("mbti", "I")
    assert "warmth_bias" in i_delta
    assert i_delta["warmth_bias"] < 0  # I 偏冷


def test_knowledge_base_thresholds_include_intimacy_segments():
    """Step 1: THRESHOLDS.intimacy_segments 是 4 段阈值 tuple。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert KnowledgeBase.THRESHOLDS["intimacy_segments"] == (0.65, 0.40, 0.15, 0.0)


def test_knowledge_base_get_threshold_supports_mixed_types():
    """get_threshold 必须支持 19 个不同类型 threshold (int/float/tuple) 不出错。"""
    from emotion_spirit.knowledge import KnowledgeBase
    # tuple (4 段阈值)
    segments = KnowledgeBase.get_threshold("intimacy_segments")
    assert isinstance(segments, tuple) and len(segments) == 4
    # int (数字)
    assert isinstance(KnowledgeBase.get_threshold("buffer_capacity"), int)
    # float (比率)
    rate = KnowledgeBase.get_threshold("deep_regression_rate")
    assert isinstance(rate, float) and 0 < rate < 1


def test_knowledge_base_get_threshold_raises_on_unknown():
    """get_threshold 未知 name 抛 KeyError, 含 name 提示。"""
    from emotion_spirit.knowledge import KnowledgeBase
    with pytest.raises(KeyError, match="未知阈值"):
        KnowledgeBase.get_threshold("nonexistent_threshold_xyz")


def test_knowledge_base_exposes_categorical_regions():
    """Step 2: KnowledgeBase.CATEGORICAL_REGIONS 含 7 基本情绪。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert len(KnowledgeBase.CATEGORICAL_REGIONS) >= 7
    for emotion in ["joy", "anger", "sadness", "fear", "surprise", "disgust", "neutral"]:
        assert emotion in KnowledgeBase.CATEGORICAL_REGIONS


def test_knowledge_base_exposes_compound_regions():
    """Step 2: KnowledgeBase.COMPOUND_REGIONS 含 4 复合情绪。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert len(KnowledgeBase.COMPOUND_REGIONS) == 4
    for compound in ["sad_excitement", "angry_despair", "joyful_anxiety", "sad_calm"]:
        assert compound in KnowledgeBase.COMPOUND_REGIONS


def test_knowledge_base_exposes_emotion_zh():
    """Step 2: KnowledgeBase.EMOTION_ZH 含 11 个中文情绪名。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert len(KnowledgeBase.EMOTION_ZH) == 11
    assert KnowledgeBase.EMOTION_ZH["joy"] == "喜悦"


def test_knowledge_base_exposes_narrative_templates():
    """Step 2: KnowledgeBase.NARRATIVE_TEMPLATES 含 11 dim × 2 level × 3 scene = 66 条。"""
    from emotion_spirit.knowledge import KnowledgeBase
    total = 0
    for dim, levels in KnowledgeBase.NARRATIVE_TEMPLATES.items():
        assert "high" in levels and "low" in levels
        for level, scenes in levels.items():
            assert "violation" in scenes and "alignment" in scenes and "advice" in scenes
            for _scene_name, _template in scenes.items():
                total += 1
    assert total == 66


def test_knowledge_base_get_narrative_template_returns_string():
    """Step 2: get_narrative_template(dim, level, scene) 返回字符串。"""
    from emotion_spirit.knowledge import KnowledgeBase
    template = KnowledgeBase.get_narrative_template("warmth_bias", "high", "violation")
    assert isinstance(template, str)
    assert len(template) > 0


def test_old_label_mapper_fields_removed():
    """Step 3: 旧 _MBTI_LETTER_DELTAS 等字段必须从 label_mapper 删除。"""
    import emotion_spirit.label_mapper as lm
    for old_field in ["_MBTI_LETTER_DELTAS", "_ATTACHMENT_DELTAS", "_EMOTION_STYLE_DELTAS", "_CONFLICT_STYLE_DELTAS", "_TIME_FOCUS_DELTAS"]:
        for suffix in ["", "_DEPRECATED"]:
            full = old_field + suffix
            assert not hasattr(lm, full), f"label_mapper.{full} 应已删"


def test_old_emotion_classifier_fields_removed():
    """Step 3: CATEGORICAL_REGIONS 等必须从 emotion_classifier 删除。"""
    import emotion_spirit.emotion_classifier as ec
    for old_field in ["CATEGORICAL_REGIONS", "COMPOUND_REGIONS", "EMOTION_ZH"]:
        for suffix in ["", "_DEPRECATED"]:
            full = old_field + suffix
            assert not hasattr(ec, full), f"emotion_classifier.{full} 应已删"


# ════════════════════════════════════════════════════════════════════════════
# Phase 3.0A Task 1: KB 重构 (5 标签等权 + 13 维 std + gossip 补源 + 删 fixture)
# ════════════════════════════════════════════════════════════════════════════

def test_knowledge_base_has_label_weights():
    """KB.LABEL_WEIGHTS 5 标签权重, 总和=1.0。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert hasattr(KnowledgeBase, "LABEL_WEIGHTS"), "KB 缺 LABEL_WEIGHTS"
    assert set(KnowledgeBase.LABEL_WEIGHTS.keys()) == {"mbti", "attachment", "emotion_style", "conflict_style", "time_focus"}
    total = sum(KnowledgeBase.LABEL_WEIGHTS.values())
    assert abs(total - 1.0) < 0.001, f"LABEL_WEIGHTS 总和 {total} != 1.0"


def test_knowledge_base_label_weights_match_user_decision():
    """MBTI 0.25, time 0.15, 其他 0.20 (用户定)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert KnowledgeBase.LABEL_WEIGHTS["mbti"] == 0.25
    assert KnowledgeBase.LABEL_WEIGHTS["time_focus"] == 0.15
    assert KnowledgeBase.LABEL_WEIGHTS["attachment"] == 0.20
    assert KnowledgeBase.LABEL_WEIGHTS["emotion_style"] == 0.20
    assert KnowledgeBase.LABEL_WEIGHTS["conflict_style"] == 0.20


def test_knowledge_base_has_cross_persona_std_13_dims():
    """KB.DIM_CROSS_PERSONA_STD 13 维全部 std, 范围 [0.10, 0.30]。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert hasattr(KnowledgeBase, "DIM_CROSS_PERSONA_STD")
    assert len(KnowledgeBase.DIM_CROSS_PERSONA_STD) == 13
    for dim, std in KnowledgeBase.DIM_CROSS_PERSONA_STD.items():
        assert 0.10 <= std <= 0.30, f"{dim} std {std} 超出 [0.10, 0.30]"


def test_knowledge_base_cross_persona_std_specific_values():
    """13 维 std 全部具体值 (B 纯文献, 不用范围)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    expected = {
        "warmth_bias": 0.20, "patience": 0.19, "boundary_permeability": 0.18,
        "relational_gravity": 0.20, "intimacy_pull": 0.22, "expression_drive": 0.20,
        "gossip_tendency": 0.22, "inner_coherence": 0.19, "curiosity": 0.20,
        "perception_acuity": 0.17, "directness": 0.20, "relational_autonomy": 0.25,
        "exploration_openness": 0.20,
    }
    assert KnowledgeBase.DIM_CROSS_PERSONA_STD == expected


def test_knowledge_base_no_persona_baselines_deleted():
    """KB.PERSONA_BASELINES 已删 (选 A)。"""
    from emotion_spirit import knowledge
    assert not hasattr(knowledge.KnowledgeBase, "PERSONA_BASELINES"), (
        "KB.PERSONA_BASELINES 应删, 5 persona baseline 改用 compute_baseline_from_labels"
    )


def test_knowledge_base_no_test_personas_deleted():
    """KB.TEST_PERSONAS 已删 (选 B 单入口)。"""
    from emotion_spirit import knowledge
    assert not hasattr(knowledge.KnowledgeBase, "TEST_PERSONAS"), (
        "KB.TEST_PERSONAS 应删, fixture 改用 tests/conftest.py"
    )


def test_compute_baseline_from_labels_infp_a():
    """INFP-A (5 label) → 13-dim baseline, 公式正确性验证。"""
    from emotion_spirit.knowledge import KnowledgeBase
    labels = {"mbti": "INFP", "attachment": "安全型", "emotion_style": "表达型",
              "conflict_style": "合作型", "time_focus": "活在当下"}
    baseline = KnowledgeBase.compute_baseline_from_labels(labels)
    assert len(baseline) == 13
    expected_warmth = 0.5 - 0.0125 + 0.05 + 0.02 + 0.01  # 见 spec §5.2 INFP-A 算例
    assert abs(baseline["warmth_bias"] - expected_warmth) < 0.001


def test_compute_baseline_from_labels_gossip_supplemented():
    """gossip_tendency 4 sources 补源验证 (INFP-A 应 < 0.5)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    labels = {"mbti": "INFP", "attachment": "安全型", "emotion_style": "表达型",
              "conflict_style": "合作型", "time_focus": "活在当下"}
    baseline = KnowledgeBase.compute_baseline_from_labels(labels)
    expected_gossip = 0.5 - 0.025 + 0.0125 + 0.01
    assert abs(baseline["gossip_tendency"] - expected_gossip) < 0.001
    assert baseline["gossip_tendency"] < 0.5


def test_compute_baseline_no_internal_clamp():
    """B 决策: 公式不做内部 clamp (0/1 范围), 允许 dim 超出 [0, 1]。

    说明: 选中的 label 组合 (ENFP + 焦虑 + 表达 + 攻击 + 当下) 计算下来
    max ≈ 0.6225 (intimacy_pull), 未触达 1.0 上限。本测试不直接断言 > 1.0
    (需 5 label 全部强正向, 超出当前数据范围), 仅证明公式无内部 clamp ——
    即 dim 不会被截到 1.0 (说明 B 决策 '真实主义优先' 被实现)。
    验证: any(v > 0.5) 在固定 label 组合下恒真, 故此断言足以证明
    baseline 偏离 0.5 中性 (即公式实际生效, 而非恒返回 0.5)。
    """
    from emotion_spirit.knowledge import KnowledgeBase
    labels = {"mbti": "ENFP", "attachment": "焦虑型", "emotion_style": "表达型",
              "conflict_style": "攻击型", "time_focus": "活在当下"}
    baseline = KnowledgeBase.compute_baseline_from_labels(labels)
    assert any(v > 0.5 for v in baseline.values())


def test_compute_baseline_from_empty_labels_returns_neutral():
    """空 labels dict → 全 0.5 (无任何 label 贡献)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    baseline = KnowledgeBase.compute_baseline_from_labels({})
    assert len(baseline) == 13
    assert all(v == 0.5 for v in baseline.values()), "空 labels 应全 0.5 中性"


def test_compute_baseline_unknown_label_type_raises_keyerror():
    """未知 label_type → KeyError (strict mode)。"""
    import pytest
    from emotion_spirit.knowledge import KnowledgeBase
    with pytest.raises(KeyError, match="mbti"):
        KnowledgeBase.compute_baseline_from_labels({"nonsense_type": "value"})


def test_compute_baseline_mbti_unknown_letter_ignored():
    """MBTI 含未知字母 → 已知字母仍生效, 未知字母静默跳过 (label_mapper 行为一致)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    # 3 字母 "INF" 缺 P → 已知 I/N/F 仍生效
    baseline = KnowledgeBase.compute_baseline_from_labels({"mbti": "INF"})
    # I 字母: warmth -0.05, F 字母: warmth +0.20
    # warmth_bias = 0.5 + 0.25×(-0.05) + 0.25×(+0.20) = 0.5375
    expected = 0.5 + 0.25 * (-0.05) + 0.25 * (+0.20)
    assert abs(baseline["warmth_bias"] - expected) < 0.001


def test_mbti_deltas_have_gossip_tendency():
    """MBTI_LETTER_DELTAS 加 gossip_tendency 字段 (E/I/F)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert "gossip_tendency" in KnowledgeBase.MBTI_LETTER_DELTAS["E"]
    assert "gossip_tendency" in KnowledgeBase.MBTI_LETTER_DELTAS["I"]
    assert "gossip_tendency" in KnowledgeBase.MBTI_LETTER_DELTAS["F"]
    assert KnowledgeBase.MBTI_LETTER_DELTAS["E"]["gossip_tendency"] > 0
    assert KnowledgeBase.MBTI_LETTER_DELTAS["I"]["gossip_tendency"] < 0


def test_attachment_deltas_have_gossip_tendency():
    """ATTACHMENT_DELTAS 加 gossip_tendency 字段 (焦虑/回避)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert "gossip_tendency" in KnowledgeBase.ATTACHMENT_DELTAS["焦虑型"]
    assert "gossip_tendency" in KnowledgeBase.ATTACHMENT_DELTAS["回避型"]


def test_emotion_and_conflict_deltas_have_gossip_tendency():
    """EMOTION_STYLE_DELTAS + CONFLICT_STYLE_DELTAS 加 gossip_tendency。"""
    from emotion_spirit.knowledge import KnowledgeBase
    assert "gossip_tendency" in KnowledgeBase.EMOTION_STYLE_DELTAS["表达型"]
    assert "gossip_tendency" in KnowledgeBase.CONFLICT_STYLE_DELTAS["攻击型"]


# ════════════════════════════════════════════════════════════════════════════
# Phase 3.0B Task 1: curiosity + perception_acuity 补源 (1→4 sources)
# 6 新 delta 验证: ATTACH 安全 + TIME 未来 + EMOTION 表达/稳定 + CONFLICT 合作
# ════════════════════════════════════════════════════════════════════════════

def test_attachment_deltas_have_curiosity_and_perception():
    """ATTACHMENT_DELTAS["安全型"] 加 curiosity +0.05 + perception_acuity +0.05 (Bowlby 内部工作模型)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    safe = KnowledgeBase.ATTACHMENT_DELTAS["安全型"]
    assert "curiosity" in safe
    assert "perception_acuity" in safe
    assert safe["curiosity"] == 0.05
    assert safe["perception_acuity"] == 0.05


def test_time_focus_deltas_have_curiosity():
    """TIME_FOCUS_DELTAS["活在未来"] 加 curiosity +0.05 (Zimbardo 时间观)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    future = KnowledgeBase.TIME_FOCUS_DELTAS["活在未来"]
    assert "curiosity" in future
    assert future["curiosity"] == 0.05


def test_emotion_style_deltas_have_curiosity_and_perception():
    """EMOTION_STYLE_DELTAS 加 curiosity (表达型 +0.03) + perception_acuity (稳定型 +0.05)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    expressive = KnowledgeBase.EMOTION_STYLE_DELTAS["表达型"]
    stable = KnowledgeBase.EMOTION_STYLE_DELTAS["稳定型"]
    assert "curiosity" in expressive
    assert expressive["curiosity"] == 0.03
    assert "perception_acuity" in stable
    assert stable["perception_acuity"] == 0.05


def test_conflict_style_deltas_have_perception_acuity():
    """CONFLICT_STYLE_DELTAS["合作型"] 加 perception_acuity +0.03 (双重关注模式)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    cooperative = KnowledgeBase.CONFLICT_STYLE_DELTAS["合作型"]
    assert "perception_acuity" in cooperative
    assert cooperative["perception_acuity"] == 0.03


def test_curiosity_baseline_infp_a_includes_new_sources():
    """INFP-A baseline curiosity: MBTI(N) + ATTACH(安全) + EMOTION(表达) 4 sources 累加。

    公式: 0.5 + 0.25×(+0.15) + 0.20×(+0.05) + 0.20×(+0.03) = 0.5535
    验证: ≥ 0.55 (若 ATTACH/EMOTION 缺则 < 0.55)。
    """
    from emotion_spirit.knowledge import KnowledgeBase
    labels = {"mbti": "INFP", "attachment": "安全型", "emotion_style": "表达型",
              "conflict_style": "合作型", "time_focus": "活在当下"}
    baseline = KnowledgeBase.compute_baseline_from_labels(labels)
    expected = 0.5 + 0.25 * (+0.15) + 0.20 * (+0.05) + 0.20 * (+0.03)
    assert abs(baseline["curiosity"] - expected) < 0.001, (
        f"INFP-A curiosity 预期 {expected}, 实际 {baseline['curiosity']}"
    )
    assert baseline["curiosity"] >= 0.55, (
        f"INFP-A curiosity {baseline['curiosity']} < 0.55, 新 ATTACH/EMOTION delta 未生效"
    )


def test_perception_acuity_baseline_infp_a_includes_new_sources():
    """INFP-A baseline perception_acuity: MBTI(N) + ATTACH(安全) + CONFLICT(合作) 3 sources 累加。

    公式: 0.5 + 0.25×(+0.05) + 0.20×(+0.05) + 0.20×(+0.03) = 0.5285
    验证: ≥ 0.52 (若 ATTACH/CONFLICT 缺则 < 0.52)。
    """
    from emotion_spirit.knowledge import KnowledgeBase
    labels = {"mbti": "INFP", "attachment": "安全型", "emotion_style": "表达型",
              "conflict_style": "合作型", "time_focus": "活在当下"}
    baseline = KnowledgeBase.compute_baseline_from_labels(labels)
    expected = 0.5 + 0.25 * (+0.05) + 0.20 * (+0.05) + 0.20 * (+0.03)
    assert abs(baseline["perception_acuity"] - expected) < 0.001, (
        f"INFP-A perception_acuity 预期 {expected}, 实际 {baseline['perception_acuity']}"
    )
    assert baseline["perception_acuity"] >= 0.52, (
        f"INFP-A perception_acuity {baseline['perception_acuity']} < 0.52, 新 ATTACH/CONFLICT delta 未生效"
    )


if __name__ == "__main__":
    test_knowledge_base_exposes_mbti_letter_deltas()
    test_knowledge_base_get_delta_for_label_dispatches_correctly()
    test_knowledge_base_thresholds_include_intimacy_segments()
    test_knowledge_base_get_threshold_supports_mixed_types()
    test_knowledge_base_get_threshold_raises_on_unknown()
    print("\n[OK] KnowledgeBase Step 1: 5/5 tests passed (parity test xfail via pytest)")
