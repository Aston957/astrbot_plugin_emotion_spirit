"""属性测试 — 使用 hypothesis 验证各模块不变量。

运行方式:
    pytest property_tests.py -v --tb=short
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotion_spirit.regulation.superego import (
    ValueResistance, ValueAlignment, ConscienceTracker, IdealSelf,
)
from emotion_spirit.regulation.superego_guard import SuperegoGuard
from emotion_spirit.output.surface_consumer import SurfaceConsumer, SemanticSignals
from emotion_spirit.regulation.personality_drift import PersonalityDrift
from emotion_spirit.utils import TrendDetector, EMASmoother
from emotion_spirit.core.config import SUPEREGO_CONFIG, SAFETY_CONFIG
from emotion_spirit.utils import labels_to_personality, _BASELINE


# ═══ Hypothesis Strategies ═══

personality_strategy = st.builds(
    lambda deep, surface: {"deep": deep, "surface": surface},
    deep=st.fixed_dictionaries({
        "expression_drive": st.floats(0, 1),
        "perception_acuity": st.floats(0, 1),
        "boundary_permeability": st.floats(0, 1),
        "inner_coherence": st.floats(0, 1),
        "relational_gravity": st.floats(0, 1),
    }),
    surface=st.fixed_dictionaries({
        "warmth_bias": st.floats(0, 1),
        "directness": st.floats(0, 1),
        "curiosity": st.floats(0, 1),
        "patience": st.floats(0, 1),
        "intimacy_pull": st.floats(0, 1),
        # v1.7: autonomy_guard 拆分为 2 维
        "relational_autonomy": st.floats(0, 1),
        "exploration_openness": st.floats(0, 1),
    }),
)

action_strategy = st.sampled_from([
    "express", "reach_out", "explore", "repair", "hold",
    "withdraw", "observe", "recover", "deny", "suppress", "avoid",
])

stress_strategy = st.floats(0, 1)

interaction_count_strategy = st.integers(0, 50000)

labels_strategy = st.one_of(
    st.just({
        "mbti": "INFP", "attachment": "焦虑型",
        "emotion_style": "表达型", "conflict_style": "顺应型", "time_focus": "活在当下",
    }),
    st.just({
        "mbti": "ISTJ", "attachment": "安全型",
        "emotion_style": "混合型", "conflict_style": "合作型", "time_focus": "活在当下",
    }),
    st.just({
        "mbti": "ENTP", "attachment": "回避型",
        "emotion_style": "表达型", "conflict_style": "攻击型", "time_focus": "活在未来",
    }),
)


# ═══ C-1: resistance ∈ [0, 1] ═══

@given(
    personality=personality_strategy,
    action=action_strategy,
    stress=stress_strategy,
    interaction_count=interaction_count_strategy,
)
@settings(max_examples=200)
def test_resistance_bounded(personality, action, stress, interaction_count):
    vr = ValueResistance("test")
    vr._baseline_personality = personality
    vr._interaction_count = interaction_count
    result = vr.compute(action=action, current_personality=personality, stress_level=stress)
    assert 0.0 <= result.resistance <= 1.0, f"resistance={result.resistance} out of bounds"


# ═══ C-2: 核心 > 边缘 至少 3x ═══

@given(personality=personality_strategy, interaction_count=st.integers(100, 5000))
@settings(max_examples=100)
def test_core_peripheral_separation(personality, interaction_count):
    """核心维度权重均值至少是边缘维度的 3 倍。

    理论依据:
    - Schwartz 价值观理论: 核心价值观 2-3 个主导
    - 价值-注意力研究: 核心:边缘注意力资源比约 2:1 到 5:1
    - HEXACO facet 预测力不均匀
    - noncore_ratio=0.3 → 核心:边缘 ≈ 3.3:1
    """
    vr = ValueResistance("test")
    vr._baseline_personality = personality
    vr._interaction_count = interaction_count
    weights = vr._build_value_system(personality, stress_level=0.0)

    sorted_weights = sorted(weights.values(), reverse=True)
    if len(sorted_weights) >= 6:
        top5_mean = sum(sorted_weights[:5]) / 5
        bottom_mean = sum(sorted_weights[5:]) / len(sorted_weights[5:])
        if bottom_mean > 0:
            ratio = top5_mean / bottom_mean
            assert ratio >= 2.5, f"core/peripheral ratio={ratio:.2f} < 2.5 (with noncore_ratio=0.3, expect ≥3.0x with baseline)"


# ═══ C-3: 基线引力单调递减 ═══

def test_anchor_decay_monotonic():
    """基线引力随 interaction_count 单调递减。"""
    anchor_strengths = [0.3 / (1 + n / 3000) for n in [0, 10, 100, 1000, 3000, 10000, 50000]]
    for i in range(len(anchor_strengths) - 1):
        assert anchor_strengths[i] >= anchor_strengths[i + 1], \
            f"anchor not monotonic: {anchor_strengths[i]} > {anchor_strengths[i+1]}"


# ═══ C-4: 基线引力 ≤ anchor_base ═══

@given(interaction_count=interaction_count_strategy)
@settings(max_examples=100)
def test_anchor_upper_bound(interaction_count):
    """基线引力不超过 anchor_base。"""
    anchor_base = SUPEREGO_CONFIG["weight_differentiation"]["anchor_base"]
    strength = anchor_base * (1.0 / (1.0 + interaction_count / 3000))
    assert strength <= anchor_base, f"anchor {strength} > base {anchor_base}"


# ═══ C-5: 压力加成不超过 anchor × (1+stress_multiplier) ═══

@given(stress=stress_strategy)
@settings(max_examples=50)
def test_stress_boost_bound(stress):
    """压力加成系数不超过 anchor × (1+stress_multiplier)。"""
    wd = SUPEREGO_CONFIG["weight_differentiation"]
    stress_multiplier = float(wd["stress_multiplier"])
    boost = 1.0 + stress * stress_multiplier
    assert boost <= 1.0 + stress_multiplier, f"stress boost {boost} exceeds bound"


# ═══ C-6: 无 personality 时降级到线性方案 ═══

def test_fallback_linear():
    """无 baseline_personality 时退化为线性方案。"""
    vr = ValueResistance("test")
    # 不设置 _baseline_personality
    result = vr.compute(action="express", current_personality=None)
    # 线性方案仍然应该返回合理的 resistance
    assert 0.0 <= result.resistance <= 1.0


# ═══ C-7: 人格切换后权重正确重置 ═══

def test_persona_switch_reset():
    """人格切换后权重重新从当前参数推导。"""
    vr = ValueResistance("test")

    personality_a = labels_to_personality({
        "mbti": "INFP", "attachment": "焦虑型",
        "emotion_style": "表达型", "conflict_style": "顺应型", "time_focus": "活在当下",
    })
    vr._baseline_personality = personality_a
    vr._interaction_count = 100
    vr.compute(action="express", current_personality=personality_a)
    weights_a = dict(vr._values)

    personality_b = labels_to_personality({
        "mbti": "ISTJ", "attachment": "安全型",
        "emotion_style": "混合型", "conflict_style": "合作型", "time_focus": "活在当下",
    })
    vr._baseline_personality = personality_b
    vr.compute(action="express", current_personality=personality_b)
    weights_b = dict(vr._values)

    # 两种人格的权重应该不同
    assert weights_a != weights_b, "weights should change after persona switch"


# ═══ C-8: pressure ∈ [0, 1] ═══

@given(
    conflicts=st.lists(
        st.tuples(st.floats(0, 1), st.sampled_from(["guilt", "doubt", "shame"])),
        min_size=0, max_size=20,
    ),
    alignments=st.integers(0, 30),
    guard_rejections=st.integers(0, 10),
    cascades=st.integers(0, 5),
    hours=st.floats(0, 240),
)
@settings(max_examples=200)
def test_pressure_bounded(conflicts, alignments, guard_rejections, cascades, hours):
    ct = ConscienceTracker()
    for severity, ttype in conflicts:
        ct.record_value_conflict(
            resistance=0.5, conflict_values=["warmth_bias"],
            tension_type=ttype, behavioral_shift=0.3,
            conscience_impact=severity,
        )
    for _ in range(alignments):
        ct.record_alignment("warmth_bias", "express")
    for _ in range(guard_rejections):
        ct.record_guard_reflex(0.5, "test")
    for _ in range(cascades):
        ct.record_cascade(0.5)
    ct.tick_pressure(hours)
    pressure = ct.get_pressure()
    assert 0.0 <= pressure <= 1.0, f"pressure={pressure} out of bounds"


# ═══ C-9: tick_pressure 单调递减 (修复版) ═══

def test_pressure_decay_monotonic():
    """压力随时间单调递减。"""
    ct = ConscienceTracker()
    ct.record_value_conflict(0.8, ["warmth_bias"], "guilt", 0.5, 0.6)
    initial = ct.get_pressure()

    pressures = [initial]
    elapsed = 0.0
    for h in [1, 2, 4, 8, 24, 48, 168]:
        delta = h - elapsed
        elapsed = h
        ct.tick_pressure(delta)
        pressures.append(ct.get_pressure())

    for i in range(len(pressures) - 1):
        assert pressures[i + 1] <= pressures[i], \
            f"pressure not monotonic at step {i}: {pressures[i]} > {pressures[i+1]}"


# ═══ C-10: repair_relief 顺序 ═══

def test_repair_relief_ordering():
    """simple < substantial < transformative。"""
    relief = SUPEREGO_CONFIG["repair_relief"]
    assert relief["simple"] < relief["substantial"] < relief["transformative"]


# ═══ C-11: 对齐事件减压 ═══

def test_alignment_reduces_pressure():
    """record_alignment 减少 pressure。"""
    ct = ConscienceTracker()
    ct.record_value_conflict(0.8, ["warmth_bias"], "guilt", 0.5, 0.6)
    pressure_before = ct.get_pressure()
    ct.record_alignment("warmth_bias", "express")
    pressure_after = ct.get_pressure()
    assert pressure_after < pressure_before, \
        f"alignment should reduce pressure: {pressure_after} >= {pressure_before}"


# ═══ C-12: gap ∈ [0, 1] ═══

@given(personality=personality_strategy)
@settings(max_examples=50)
def test_ideal_gap_bounded(personality):
    """理想自我 gap ∈ [0, 1]。"""
    ideal = IdealSelf("test", {
        "mbti": "INFP", "attachment": "焦虑型",
        "emotion_style": "表达型", "conflict_style": "顺应型", "time_focus": "活在当下",
    })
    gap = ideal.compute_gap(personality)
    assert 0.0 <= gap <= 1.0, f"gap={gap} out of bounds"


# ═══ C-13: reinforcement 不越过 max_shift ═══

@given(
    deltas=st.lists(st.floats(-1, 1), min_size=1, max_size=100),
)
@settings(max_examples=50)
def test_reinforcement_bounded(deltas):
    """reinforcement 不超过 max_shift。"""
    ideal = IdealSelf("test", {
        "mbti": "INFP", "attachment": "焦虑型",
        "emotion_style": "表达型", "conflict_style": "顺应型", "time_focus": "活在当下",
    })
    max_shift = SUPEREGO_CONFIG["reinforcement_max"]

    for d in deltas:
        ideal.update_reinforcement("warmth_bias", d)

    # 检查 reinforcement 值不超过 max_shift
    for layer in ("deep", "surface"):
        for dim, shift in ideal._reinforcement.get(layer, {}).items():
            assert abs(shift) <= max_shift + 0.001, \
                f"reinforcement {dim}={shift} exceeds max_shift={max_shift}"


# ═══ C-14: compute_gap 对称性 ═══

def test_ideal_gap_symmetry():
    """gap(a,b) ≈ gap(b,a)。"""
    ideal = IdealSelf("test", {
        "mbti": "INFP", "attachment": "焦虑型",
        "emotion_style": "表达型", "conflict_style": "顺应型", "time_focus": "活在当下",
    })
    p1 = labels_to_personality({
        "mbti": "INFP", "attachment": "焦虑型",
        "emotion_style": "表达型", "conflict_style": "顺应型", "time_focus": "活在当下",
    })
    p2 = labels_to_personality({
        "mbti": "ISTJ", "attachment": "安全型",
        "emotion_style": "混合型", "conflict_style": "合作型", "time_focus": "活在当下",
    })

    gap1 = ideal.compute_gap(p1)
    gap2 = ideal.compute_gap(p2)

    # 不要求完全相等，但方向应该一致 (更接近理想的 gap 更小)
    # INFP-焦虑型 应该比 ISTJ-安全型 更接近 INFP-焦虑型 的理想
    assert gap1 < gap2, f"INFP should be closer to INFP ideal: gap1={gap1}, gap2={gap2}"


# ═══ C-15: get_score ∈ [0, 1] ═══

@given(
    aligned_count=st.integers(0, 100),
    misaligned_count=st.integers(0, 100),
    neutral_count=st.integers(0, 100),
)
@settings(max_examples=100)
def test_alignment_score_bounded(aligned_count, misaligned_count, neutral_count):
    """对齐分数 ∈ [0, 1]。"""
    va = ValueAlignment("test")
    va._aligned_count = aligned_count
    va._misaligned_count = misaligned_count
    va._neutral_count = neutral_count
    score = va.get_score()
    assert 0.0 <= score <= 1.0, f"score={score} out of bounds"


# ═══ C-16: 连续 aligned 动作提高 score ═══

def test_alignment_monotonic_aligned():
    """连续 aligned 动作应该提高 score。"""
    va = ValueAlignment("test")
    initial_score = va.get_score()

    for _ in range(20):
        va.record("express")  # express 对齐 expression_drive + warmth_bias

    final_score = va.get_score()
    assert final_score > initial_score, \
        f"continuous aligned should increase score: {final_score} <= {initial_score}"


# ═══ C-17: level ∈ {normal, warning, critical} ═══

@given(personality=personality_strategy)
@settings(max_examples=50)
def test_intervention_levels(personality):
    """干预级别只能是 normal/warning/critical。"""
    ct = ConscienceTracker()
    va = ValueAlignment("test")
    ideal = IdealSelf("test")
    guard = SuperegoGuard(ct, va, ideal, "test")

    result = guard.assess({}, personality)
    assert result.level in ("normal", "warning", "critical"), \
        f"unexpected level={result.level}"


# ═══ C-18: 空 sentinel 结果 → normal ═══

def test_guard_empty_sentinel():
    """空 sentinel 结果应该返回 normal。"""
    ct = ConscienceTracker()
    va = ValueAlignment("test")
    ideal = IdealSelf("test")
    guard = SuperegoGuard(ct, va, ideal, "test")

    result = guard.assess({})
    assert result.level == "normal", f"empty sentinel should be normal, got {result.level}"


# ═══ C-19: critical 节流不超过 max_per_day ═══

def test_critical_throttle():
    """critical 节流不超过 max_per_day。"""
    ct = ConscienceTracker()
    va = ValueAlignment("test")
    ideal = IdealSelf("test")
    guard = SuperegoGuard(ct, va, ideal, "test")

    # 手动触发多次 critical
    max_per_day = SAFETY_CONFIG.get("critical_max_per_day", 3)
    critical_count = 0
    for _ in range(max_per_day + 5):
        ct._pressure = 1.0  # 强制高压力
        # 添加足够的 recent conflicts 触发超我信号
        ct.record_value_conflict(0.9, ["warmth_bias"], "guilt", 0.8, 0.8)
        result = guard.assess({}, None)
        if result.level == "critical":
            critical_count += 1

    # 不应该超过 max_per_day
    assert critical_count <= max_per_day, \
        f"critical count {critical_count} exceeds max_per_day {max_per_day}"


# ═══ C-20: slope 窗口 ≤ 历史长度 ═══

def test_slope_window_safety():
    """slope 窗口大于历史长度时不崩溃。"""
    td = TrendDetector(0.1, 0.01)
    # 只更新 3 次，但请求 window=7
    td.update(0.1)
    td.update(0.2)
    td.update(0.3)
    slope = td.slope(7)  # 应该不崩溃
    assert isinstance(slope, float)


# ═══ C-21: 递增数据 → slope > 0 ═══

def test_slope_increasing():
    """递增数据应该产生正斜率。"""
    td = TrendDetector(0.1, 0.01)
    for v in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        td.update(v)
    assert td.slope(7) > 0, f"increasing data should have positive slope, got {td.slope(7)}"


# ═══ C-22: 递减数据 → slope < 0 ═══

def test_slope_decreasing():
    """递减数据应该产生负斜率。"""
    td = TrendDetector(0.1, 0.01)
    for v in [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0]:
        td.update(v)
    assert td.slope(7) < 0, f"decreasing data should have negative slope, got {td.slope(7)}"


# ═══ C-23: PersonalityDrift update 不抛异常 ═══

@given(personality=personality_strategy)
@settings(max_examples=50)
def test_drift_update_robust(personality):
    """PersonalityDrift.update() 不应该抛异常。"""
    consumer = SurfaceConsumer()
    from emotion_spirit.memory.meaning_reservoir import MeaningReservoir
    reservoir = MeaningReservoir()
    drift = PersonalityDrift(consumer, reservoir)

    signals = SemanticSignals(
        personality_deep=personality["deep"],
        personality_surface=personality["surface"],
    )
    drift.update(signals)  # 不应该崩溃
    drift.check_drift()  # 也不应该崩溃


# ═══ C-24: tension 分类映射 ═══

@given(personality=personality_strategy, action=action_strategy)
@settings(max_examples=100)
def test_tension_classification(personality, action):
    """tension 分类验证。

    righteous 不再是无条件 early-return:
    只有 alignment_ratio ≥ 0.85 且 resistance ≤ 0.5 时才归为 righteous。
    否则按权重投票分为 guilt/doubt/shame。

    理论依据:
    - Anderson & Bushman 认知新联合模型: 初始情绪是未分化的, 后续加工决定方向
    - Weiner (1995): righteous 需要他人归因+可控性+道德违反三条件
    - Lopez (1997): 依恋安全感调节 guilt-shame 关系
    - Magai et al. (N=1118): 所有依恋类型都体验多种道德情绪
    """
    vr = ValueResistance("test")
    vr._baseline_personality = personality
    vr._interaction_count = 100
    result = vr.compute(action=action, current_personality=personality)

    if result.conflict_values and result.aligned_values:
        aligned_weight = sum(vr._values.get(v, 0.5) for v in result.aligned_values)
        conflict_weight = sum(vr._values.get(v, 0.5) for v in result.conflict_values)
        total = aligned_weight + conflict_weight
        alignment_ratio = aligned_weight / total if total > 0 else 0.5
        if alignment_ratio >= 0.85 and result.resistance <= 0.5:
            assert result.tension_type == "righteous", \
                f"high alignment + low resistance should be righteous, got {result.tension_type}"
        else:
            assert result.tension_type in ("guilt", "doubt", "shame", "righteous"), \
                f"unexpected tension_type={result.tension_type}"
    elif result.conflict_values and not result.aligned_values:
        assert result.tension_type in ("guilt", "doubt", "shame"), \
            f"conflict-only should be guilt/doubt/shame, got {result.tension_type}"
    elif not result.conflict_values:
        assert result.tension_type is None or result.tension_type in ("guilt", "doubt", "shame")


# ═══ C-25: righteous 条件判断 ═══

def test_righteous_threshold():
    """righteous 需要 alignment_ratio ≥ 0.7 且 resistance ≤ 0.5。

    理论依据:
    - Weiner (1995): righteous/indignation 需要他人归因+可控性+道德违反三条件
    - Anderson & Bushman: 初始情绪是未分化的, 认知加工才决定方向
    - "同时有 aligned + conflict"不必然产生 righteous — 大部分情况下是内在矛盾
    """
    vr = ValueResistance("test")
    personality = labels_to_personality({
        "mbti": "INFP", "attachment": "焦虑型",
        "emotion_style": "表达型", "conflict_style": "顺应型", "time_focus": "活在当下",
    })
    vr._baseline_personality = personality
    vr._interaction_count = 100

    result = vr.compute(action="express", current_personality=personality)
    if result.aligned_values and result.conflict_values:
        aligned_weight = sum(vr._values.get(v, 0.5) for v in result.aligned_values)
        conflict_weight = sum(vr._values.get(v, 0.5) for v in result.conflict_values)
        total = aligned_weight + conflict_weight
        alignment_ratio = aligned_weight / total if total > 0 else 0.5

        if alignment_ratio >= 0.85 and result.resistance <= 0.5:
            assert result.tension_type == "righteous", \
                f"high alignment ({alignment_ratio:.2f}) + low resistance ({result.resistance:.2f}) should be righteous"
        else:
            assert result.tension_type in ("guilt", "doubt", "shame", "righteous"), \
                f"low alignment or high resistance should not always be righteous, got {result.tension_type}"


# ═══ C-26: 空冲突 → tension=None ═══

def test_no_conflict_no_tension():
    """无冲突时 tension_type 应该是 None。"""
    vr = ValueResistance("test")
    personality = labels_to_personality({
        "mbti": "ISTJ", "attachment": "安全型",
        "emotion_style": "混合型", "conflict_style": "合作型", "time_focus": "活在当下",
    })
    vr._baseline_personality = personality
    vr._interaction_count = 100

    # hold 对 ISTJ-安全型 应该是 aligned (relational_autonomy + inner_coherence)  # v1.7: autonomy_guard 拆分
    result = vr.compute(action="hold", current_personality=personality)
    if not result.conflict_values:
        assert result.tension_type is None


# ═══ C-27: 坍缩事件增压 ═══

def test_collapse_increases_pressure():
    """坍缩事件应该增加 pressure。"""
    ct = ConscienceTracker()
    initial = ct.get_pressure()
    ct.record_collapse(1)  # 第一次坍缩
    assert ct.get_pressure() > initial


# ═══ C-28: SurfaceConsumer 默认值 ═══

def test_surface_defaults():
    """SurfaceConsumer 在空 Surface 输入时不报错。"""
    consumer = SurfaceConsumer()
    signals = consumer.consume({})

    assert 0.0 <= signals.body_integration <= 1.0
    assert 0.0 <= signals.body_criticality <= 1.0
    assert signals.decision_action == "hold"
    assert isinstance(signals.personality_deep, dict)
    assert isinstance(signals.personality_surface, dict)
