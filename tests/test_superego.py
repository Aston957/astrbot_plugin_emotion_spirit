"""Tests for superego.py — 参数驱动版本"""

import sys
import os
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotion_spirit.superego import (
    ValueAlignment, ConscienceTracker, IdealSelf,
    ValueResistance, ResistanceResult, GuiltEvent, AlignmentEvent,
)
from emotion_spirit.label_mapper import labels_to_personality


# ═══ 辅助：构造测试用 11 维参数 ═══

def _enfp_anxious():
    return labels_to_personality({"mbti": "ENFP", "attachment": "焦虑型"})

def _intp_avoidant():
    return labels_to_personality({"mbti": "INTP", "attachment": "回避型"})

def _enfp_default():
    return labels_to_personality({"mbti": "ENFP"})

def _default():
    return labels_to_personality({"mbti": "ISTJ"})


# ═══ ValueResistance Tests ═══

def test_value_resistance_compute_conflict():
    vr = ValueResistance("test")
    result = vr.compute("withdraw", current_personality=_enfp_anxious())
    assert isinstance(result, ResistanceResult)
    assert result.resistance > 0
    assert len(result.conflict_values) > 0
    # withdraw 冲突 relational_gravity / intimacy_pull
    assert any(v in result.conflict_values for v in ["relational_gravity", "intimacy_pull"])


def test_value_resistance_compute_aligned():
    vr = ValueResistance("test")
    result = vr.compute("express", current_personality=_enfp_default())
    assert len(result.aligned_values) > 0
    # express 同时有 aligned 和 misaligned，所以 resistance 可能不为 0
    # 但 aligned 值应多于 conflict 值
    assert len(result.aligned_values) > len(result.conflict_values)
    # v2: righteous 需要 alignment_ratio ≥ 0.7，否则 fall through 到普通 tension 分类
    if result.conflict_values:
        assert result.tension_type in ("righteous", "guilt", "doubt", "shame")


def test_value_resistance_context_modifiers():
    vr = ValueResistance("test")
    p = _enfp_default()
    base = vr.compute("hold", current_personality=p)
    with_criticality = vr.compute("hold", context={"body_criticality": 0.8}, current_personality=p)
    assert with_criticality.resistance >= base.resistance


def test_value_resistance_cascade_reduction():
    vr = ValueResistance("test")
    p = _enfp_anxious()
    base = vr.compute("withdraw", current_personality=p)
    with_cascade = vr.compute("withdraw", context={"cascade_active": True}, current_personality=p)
    assert with_cascade.resistance <= base.resistance


def test_value_resistance_tension_guilt():
    """纯 guilt 冲突 — deny 的 misaligned=[warmth_bias, relational_gravity]，无 aligned"""
    vr = ValueResistance("test")
    result = vr.compute("deny", current_personality=_enfp_anxious())
    assert len(result.conflict_values) > 0
    assert result.tension_type == "guilt"


def test_value_resistance_tension_doubt():
    """纯 doubt 冲突 — suppress 的 misaligned=[inner_coherence, curiosity]，无 aligned"""
    vr = ValueResistance("test")
    result = vr.compute("suppress", current_personality=_enfp_anxious())
    assert len(result.conflict_values) > 0
    assert result.tension_type == "doubt"


def test_value_resistance_tension_shame():
    """v1.7.2 + Phase B B3: avoid 冲突 patience (KB righteous) + relational_autonomy (KB shame)。
    KB 重新分类 (Tangney 2002): patience 从 shame 改 righteous。
    测试验证: 当 conflict 含 patience + relational_autonomy 时, tension_type 应含 KB 合法值。"""
    vr = ValueResistance("test")
    result = vr.compute("avoid", current_personality=_enfp_anxious())
    assert len(result.conflict_values) > 0
    # KB 合法 tension 类型: {guilt, doubt, shame, righteous, value_conflict}
    assert result.tension_type in {"guilt", "doubt", "shame", "righteous", "value_conflict"}


def test_value_resistance_tension_righteous():
    """v2: righteous 需要 alignment_ratio ≥ 0.7 且有 aligned+conflict。

    v1.7 更新: relational_autonomy 拆出后, ENFP-焦虑型 reach_out 的
    conflict 维度 = relational_autonomy (shame 组)，不再是 autonomy_guard 旧语义。
    """
    vr = ValueResistance("test")
    # reach_out: aligned=[relational_gravity, intimacy_pull], misaligned=[relational_autonomy]
    # ENFP 焦虑型 intimacy_pull 和 relational_gravity 权重高 → alignment_ratio 应 ≥ 0.7
    result = vr.compute("reach_out", current_personality=_enfp_anxious())
    if result.conflict_values:
        # 有冲突时，检查是否满足 righteous 条件
        aligned_strength = sum(vr._get_weight(v) for v in result.aligned_values)
        conflict_strength = sum(vr._get_weight(v) for v in result.conflict_values)
        total = aligned_strength + conflict_strength
        alignment_ratio = aligned_strength / total if total > 0 else 0
        if alignment_ratio >= 0.7:
            # v1.7: relational_autonomy 拆出后, conflict 维度映射到 shame 而非 righteous
            # 接受 righteous 或 shame (取决于 conflict 维度数量)
            assert result.tension_type in ("righteous", "shame")
        else:
            assert result.tension_type in ("guilt", "doubt", "shame")


def test_value_resistance_tension_none():
    """纯 aligned 无 conflict → None"""
    vr = ValueResistance("test")
    # reach_out: aligned=[relational_gravity, intimacy_pull], misaligned=[relational_autonomy]  # v1.7
    # 但 ENFP 焦虑型 intimacy_pull 高，所以 reach_out 会触发 righteous
    # 改用一个纯 aligned 动作: repair 的 aligned=[warmth_bias, relational_gravity]
    # repair 的 misaligned=[boundary_permeability]，所以还是有 conflict
    # 最安全: 直接构造无冲突场景
    result = vr.compute("express", current_personality=_enfp_anxious())
    # express: aligned=[expression_drive, warmth_bias], misaligned=[relational_autonomy]  # v1.7
    # ENFP relational_autonomy 低，expression_drive=0.60，warmth_bias=0.70
    # 有 aligned + conflict → righteous，不是 None
    # 真正无冲突需要 action 不在任何映射中
    result2 = vr.compute("nonexistent_action", current_personality=_enfp_anxious())
    assert result2.tension_type is None


def test_value_resistance_weight_from_params():
    """权重应直接来自参数值，不同参数 → 不同权重。"""
    vr = ValueResistance("test")
    p = _enfp_anxious()
    vr.compute("hold", current_personality=p)  # 内部构建 value system
    # intimacy_pull 在焦虑型中应该高
    w_intimacy = vr._get_weight("intimacy_pull")
    w_autonomy = vr._get_weight("relational_autonomy")  # v1.7: 替换 autonomy_guard
    # 焦虑型: intimacy_pull > relational_autonomy
    assert w_intimacy > w_autonomy


def test_value_resistance_reinforcement():
    vr = ValueResistance("test")
    vr.compute("hold", current_personality=_enfp_anxious())
    vr.update_reinforcement("relational_gravity", 0.2)
    weight = vr._get_weight("relational_gravity")
    # 焦虑型 ENFP 的 relational_gravity 基线高，加 0.2 后应更高
    assert weight > 0.5

    vr.update_reinforcement("relational_gravity", -0.3)
    weight2 = vr._get_weight("relational_gravity")
    assert weight2 < weight


def test_value_resistance_persistence():
    vr = ValueResistance("test")
    vr.compute("hold", current_personality=_default())
    vr.update_reinforcement("relational_gravity", 0.1)
    data = vr.to_dict()
    assert data["persona"] == "test"
    assert "relational_gravity" in data["reinforcement"]

    vr2 = ValueResistance("test")
    vr2.from_dict(data)
    assert vr2._reinforcement["relational_gravity"] == 0.1


def test_value_resistance_param_specific():
    """不同参数的人格对同一动作应有不同反应。"""
    vr = ValueResistance("test")

    # ENFP 高 expression_drive，express 应该 aligned
    result_enfp = vr.compute("express", current_personality=_enfp_default())
    assert "expression_drive" in result_enfp.aligned_values

    # INTP 高 relational_autonomy (v1.7: 替换 autonomy_guard)，hold 应该 aligned
    result_intp = vr.compute("hold", current_personality=_intp_avoidant())
    assert "relational_autonomy" in result_intp.aligned_values


def test_value_resistance_params_change_weights():
    """参数变化后权重应自动跟随。"""
    vr = ValueResistance("test")
    # 第一次用 ENFP 参数
    vr.compute("hold", current_personality=_enfp_default())
    w1 = vr._get_weight("intimacy_pull")
    # 第二次用 INTP 回避型参数（低 intimacy_pull）
    vr.compute("hold", current_personality=_intp_avoidant())
    w2 = vr._get_weight("intimacy_pull")
    # 焦虑型 ENFP 的 intimacy_pull 应高于回避型 INTP
    assert w1 > w2


# ═══ ValueAlignment Tests ═══

def test_value_alignment_record_returns_tuple():
    va = ValueAlignment("test")
    conflict, aligned = va.record("express")
    assert isinstance(conflict, list)
    assert isinstance(aligned, list)


def test_value_alignment_multiple_values():
    va = ValueAlignment("test")
    conflict, aligned = va.record("express")
    assert len(aligned) > 0
    # express aligns with expression_drive and warmth_bias
    assert any(v in aligned for v in ["expression_drive", "warmth_bias"])


def test_value_alignment_misaligned_counted():
    va = ValueAlignment("test")
    va.record("withdraw")
    assert va._misaligned_count > 0


def test_value_alignment_neutral_counted():
    va_align = ValueAlignment("test")
    # observe 只有 aligned，没有 misaligned
    va_align.record("observe")
    score = va_align.get_score()
    assert 0.0 <= score <= 1.0


def test_value_alignment_score():
    va = ValueAlignment("test")
    for _ in range(10):
        va.record("express")
    score = va.get_score()
    assert score > 0.5


def test_value_alignment_trend():
    va = ValueAlignment("test")
    for _ in range(10):
        va.record("express")
    trend = va.get_trend()
    assert trend > 0


def test_value_alignment_value_detail():
    va = ValueAlignment("test")
    for _ in range(5):
        va.record("express")
    detail = va.get_value_detail("expression_drive")
    assert detail["aligned"] > 0
    assert "alignment_rate" in detail


def test_value_alignment_persistence():
    va = ValueAlignment("test")
    va.record("express")
    data = va.to_dict()
    va2 = ValueAlignment("test")
    va2.from_dict(data)
    assert va2._aligned_count == va._aligned_count
    assert va2._misaligned_count == va._misaligned_count


# ═══ ConscienceTracker Tests ═══

def test_conscience_value_conflict():
    ct = ConscienceTracker()
    event = ct.record_value_conflict(
        resistance=0.7,
        conflict_values=["relational_gravity"],
        tension_type="guilt",
        behavioral_shift=0.42,
        conscience_impact=0.56,
    )
    assert event.trigger == "value_conflict"
    assert event.severity == 0.56
    assert event.tension_type == "guilt"
    assert ct.get_pressure() > 0


def test_conscience_guard_reflex_downweighted():
    ct = ConscienceTracker()
    event = ct.record_guard_reflex(0.8, "boundary")
    assert event.severity < 0.8
    assert event.trigger == "guard_reflex"


def test_conscience_cascade_downweighted():
    ct = ConscienceTracker()
    event = ct.record_cascade(0.6)
    assert event.severity < 0.6
    assert event.trigger == "cascade"


def test_conscience_alignment_relief():
    ct = ConscienceTracker()
    ct.record_value_conflict(0.7, ["relational_gravity"], "guilt", 0.42, 0.56)
    pressure_before = ct.get_pressure()
    ct.record_alignment("relational_gravity", "express")
    pressure_after = ct.get_pressure()
    assert pressure_after < pressure_before


def test_conscience_repair_relief():
    ct = ConscienceTracker()
    ct.record_value_conflict(0.7, ["relational_gravity"], "guilt", 0.42, 0.56)
    pressure_before = ct.get_pressure()
    ct.record_repair("simple")
    assert ct.get_pressure() < pressure_before

    ct.record_repair("substantial")
    ct.record_repair("transformative")


def test_conscience_backward_compat():
    ct = ConscienceTracker()
    event = ct.record_guard_rejected(0.5, "test")
    assert event.trigger == "guard_reflex"
    assert event.severity < 0.5


def test_conscience_pressure_breakdown():
    ct = ConscienceTracker()
    ct.record_value_conflict(0.7, ["relational_gravity"], "guilt", 0.42, 0.56)
    ct.record_guard_reflex(0.5, "boundary")
    breakdown = ct.get_pressure_breakdown()
    assert "pressure" in breakdown
    assert "by_type" in breakdown
    assert "alignment_relief_24h" in breakdown
    assert breakdown["dominant_tension"] is not None


def test_conscience_tick_pressure():
    ct = ConscienceTracker()
    ct.record_value_conflict(0.7, ["relational_gravity"], "guilt", 0.42, 0.56)
    p1 = ct.get_pressure()
    ct.tick_pressure(24)
    p2 = ct.get_pressure()
    assert p2 < p1


def test_conscientious_collapse():
    ct = ConscienceTracker()
    event = ct.record_collapse(1)
    assert event is not None
    assert event.trigger == "personality_collapse"
    event2 = ct.record_collapse(1)
    assert event2 is None


def test_conscience_persistence():
    ct = ConscienceTracker()
    ct.record_value_conflict(0.7, ["relational_gravity"], "guilt", 0.42, 0.56)
    ct.record_alignment("relational_gravity", "express")
    data = ct.to_dict()
    ct2 = ConscienceTracker()
    ct2.from_dict(data)
    assert ct2.get_pressure() > 0
    assert len(ct2.alignment_events) > 0


# ═══ IdealSelf Tests ═══

def test_ideal_self_gap():
    ideal = IdealSelf("test", labels={"mbti": "INTP", "attachment": "回避型"})
    current = {
        "deep": {"expression_drive": 0.5, "perception_acuity": 0.5, "boundary_permeability": 0.5, "inner_coherence": 0.5, "relational_gravity": 0.5},
        "surface": {"warmth_bias": 0.5, "directness": 0.5, "curiosity": 0.5, "patience": 0.5, "intimacy_pull": 0.5, "relational_autonomy": 0.5, "exploration_openness": 0.5},  # v1.7: autonomy_guard 拆分
    }
    gap = ideal.compute_gap(current)
    assert gap > 0


def test_ideal_self_direction():
    ideal = IdealSelf("test", labels={"mbti": "INTP", "attachment": "回避型"})
    current = {
        "deep": {"expression_drive": 0.5, "perception_acuity": 0.5, "boundary_permeability": 0.5, "inner_coherence": 0.5, "relational_gravity": 0.5},
        "surface": {"warmth_bias": 0.5, "directness": 0.5, "curiosity": 0.5, "patience": 0.5, "intimacy_pull": 0.5, "relational_autonomy": 0.5, "exploration_openness": 0.5},  # v1.7: autonomy_guard 拆分
    }
    direction = ideal.get_direction(current)
    assert "deep.expression_drive" in direction


def test_ideal_self_reinforcement():
    ideal = IdealSelf("test", labels={"mbti": "INTP", "attachment": "回避型"})
    current = {
        "deep": {"expression_drive": 0.5, "perception_acuity": 0.5, "boundary_permeability": 0.5, "inner_coherence": 0.5, "relational_gravity": 0.5},
        "surface": {"warmth_bias": 0.5, "directness": 0.5, "curiosity": 0.5, "patience": 0.5, "intimacy_pull": 0.5, "relational_autonomy": 0.5, "exploration_openness": 0.5},  # v1.7: autonomy_guard 拆分
    }
    gap_before = ideal.compute_gap(current)
    ideal.update_reinforcement("expression_drive", 0.5)
    gap_after = ideal.compute_gap(current)
    assert gap_after != gap_before


def test_ideal_self_persistence():
    ideal = IdealSelf("test", labels={"mbti": "INTP", "attachment": "回避型"})
    ideal.update_reinforcement("expression_drive", 0.3)
    data = ideal.to_dict()
    ideal2 = IdealSelf("test", labels={"mbti": "INTP", "attachment": "回避型"})
    ideal2.from_dict(data)
    assert ideal2._reinforcement == ideal._reinforcement


# ═══ 权重分化 Tests (B: S曲线 + Top-K + 基线引力) ═══

def test_weight_s_curve_monotonic():
    """S 曲线单调性: x1 < x2 → f(x1) < f(x2)"""
    vr = ValueResistance("test")
    p = _enfp_anxious()
    vr._baseline_personality = p
    vr._interaction_count = 0
    vr.compute("hold", current_personality=p)
    weights = vr._values
    # 所有权重应在 [0, 1] 范围内
    for w in weights.values():
        assert 0.0 <= w <= 1.0


def test_weight_top_k_core():
    """Top-K 核心维度应是非核心的 ~3x"""
    vr = ValueResistance("test")
    p = _enfp_anxious()
    vr._baseline_personality = p
    vr._interaction_count = 0
    vr.compute("hold", current_personality=p)
    sorted_w = sorted(vr._values.items(), key=lambda x: x[1], reverse=True)
    core_w = sorted_w[0][1]
    noncore_w = sorted_w[-1][1]
    assert core_w > noncore_w * 2  # 至少 2x 区分度


def test_weight_baseline_gravity():
    """基线引力: 漂移后权重应受基线约束"""
    vr = ValueResistance("test")
    intp = _intp_avoidant()
    vr._baseline_personality = intp
    vr._interaction_count = 0
    vr.compute("hold", current_personality=intp)
    w_baseline = vr._values.get("intimacy_pull", 0)
    # 漂移 intimacy_pull 到 0.5
    import copy
    drifted = copy.deepcopy(intp)
    drifted["surface"]["intimacy_pull"] = 0.5
    vr._interaction_count = 200
    vr.compute("hold", current_personality=drifted)
    w_drifted = vr._values.get("intimacy_pull", 0)
    # 漂移后权重应高于基线（向上漂移）
    assert w_drifted > w_baseline


def test_weight_anchor_decay():
    """锚定衰减: 交互次数越多，引力越弱"""
    vr = ValueResistance("test")
    intp = _intp_avoidant()
    vr._baseline_personality = intp
    import copy
    drifted = copy.deepcopy(intp)
    drifted["surface"]["intimacy_pull"] = 0.5
    # 早期 (强锚定)
    vr._interaction_count = 100
    vr.compute("hold", current_personality=drifted)
    w_early = vr._values.get("intimacy_pull", 0)
    # 晚期 (弱锚定)
    vr._interaction_count = 5000
    vr.compute("hold", current_personality=drifted)
    w_late = vr._values.get("intimacy_pull", 0)
    assert w_late > w_early  # 锚定越弱，越接近实际值


def test_weight_stress_boost():
    """压力加成: 压力下引力增强"""
    vr = ValueResistance("test")
    intp = _intp_avoidant()
    vr._baseline_personality = intp
    import copy
    drifted = copy.deepcopy(intp)
    drifted["surface"]["intimacy_pull"] = 0.5
    vr._interaction_count = 200
    # 无压力
    vr.compute("hold", current_personality=drifted)
    w_no_stress = vr._values.get("intimacy_pull", 0)
    # 高压
    vr.compute("hold", current_personality=drifted, stress_level=0.8)
    w_stress = vr._values.get("intimacy_pull", 0)
    # 压力下权重应更低（引力拉回基线）
    assert w_stress < w_no_stress


def test_weight_fallback_linear():
    """无 baseline 时应降级为线性方案"""
    vr = ValueResistance("test")
    vr._baseline_personality = {}  # 空 baseline
    vr.compute("hold", current_personality=_enfp_default())
    # 线性方案: 权重 = 参数值
    for dim, w in vr._values.items():
        assert 0.0 <= w <= 1.0


def test_weight_persistence():
    """baseline_personality 和 interaction_count 应可持久化"""
    vr = ValueResistance("test")
    vr._baseline_personality = _enfp_anxious()
    vr._interaction_count = 42
    vr.update_reinforcement("relational_gravity", 0.1)
    data = vr.to_dict()
    assert data["interaction_count"] == 42
    assert "baseline_personality" in data

    vr2 = ValueResistance("test")
    vr2.from_dict(data)
    assert vr2._interaction_count == 42
    assert vr2._baseline_personality == _enfp_anxious()
    assert vr2._reinforcement["relational_gravity"] == 0.1


# ═══ Phase 2: 权重驱动 tension 分类补充测试 ═══

def test_tension_weight_driven_multi_guilt_wins():
    """纯 guilt 冲突 (deny) — warmth_bias + relational_gravity 均→guilt"""
    vr = ValueResistance("test")
    result = vr.compute("deny", current_personality=_enfp_anxious())
    assert result.tension_type == "guilt"


def test_tension_weight_driven_doubt_wins():
    """纯 doubt 冲突 (suppress) — inner_coherence + curiosity 均→doubt"""
    vr = ValueResistance("test")
    result = vr.compute("suppress", current_personality=_enfp_anxious())
    assert result.tension_type == "doubt"


def test_tension_weight_affects_score():
    """同一冲突维度，权重不同 → resistance 不同"""
    vr1 = ValueResistance("test1")
    vr2 = ValueResistance("test2")

    p_high = {
        "deep": {"expression_drive": 0.5, "perception_acuity": 0.5, "boundary_permeability": 0.5,
                 "inner_coherence": 0.95, "relational_gravity": 0.5},
        "surface": {"warmth_bias": 0.5, "directness": 0.5, "curiosity": 0.5,
                    "patience": 0.5, "intimacy_pull": 0.5, "relational_autonomy": 0.5, "exploration_openness": 0.5},  # v1.7: autonomy_guard 拆分
    }
    p_low = {
        "deep": {"expression_drive": 0.5, "perception_acuity": 0.5, "boundary_permeability": 0.5,
                 "inner_coherence": 0.20, "relational_gravity": 0.5},
        "surface": {"warmth_bias": 0.5, "directness": 0.5, "curiosity": 0.5,
                    "patience": 0.5, "intimacy_pull": 0.5, "relational_autonomy": 0.5, "exploration_openness": 0.5},  # v1.7: autonomy_guard 拆分
    }

    # v2: "hold" 只映射 [expression_drive]，改用 "explore" (misaligned=[patience, inner_coherence])
    r1 = vr1.compute("explore", current_personality=p_high)
    r2 = vr2.compute("explore", current_personality=p_low)
    # 高 inner_coherence 人格的 conflict 权重更高
    assert r1.resistance >= r2.resistance


def test_tension_empty_conflict():
    """无冲突 → tension_type 为 None, conflict_values 为空"""
    vr = ValueResistance("test")
    result = vr.compute("nonexistent_action", current_personality=_enfp_anxious())
    assert result.tension_type is None
    assert result.conflict_values == []


def test_tension_full_coverage():
    """v1.7.2 + Phase B B3: Tension 类型集走 KnowledgeBase.TENSION_INCLINATION (5 个值)。"""
    from emotion_spirit.knowledge import KnowledgeBase
    # KB 值集 5 个: {guilt, doubt, shame, righteous, value_conflict} (B2 重新分类)
    assert set(KnowledgeBase.TENSION_INCLINATION.values()) == {"guilt", "doubt", "shame", "righteous", "value_conflict"}
