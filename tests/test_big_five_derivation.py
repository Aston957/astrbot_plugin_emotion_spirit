"""§1.8: Big Five 必须从 13 维派生 (v1.3.0 Y-0b / Y-转绿).

Y-0b 验证 to_big_five 派生生效 + personality_feedback drift 表无 Big Five.
Y-转绿 验证 personality_with_big_five helper + 各 Big Five consumer 收到派生值.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
BIG_FIVE = re.compile(r'"(extraversion|neuroticism|agreeableness|conscientiousness|openness)"')


# ISTJ 13 维 baseline (Y-0b 已用, 用作"应派生显著 ≠ 0.5"的对照输入)
ISTJ_DEEP = {
    "expression_drive": 0.25,
    "perception_acuity": 0.70,
    "boundary_permeability": 0.40,
    "inner_coherence": 0.95,
    "relational_gravity": 0.20,
}
ISTJ_SURFACE = {
    "warmth_bias": 0.30,
    "directness": 0.85,
    "curiosity": 0.60,
    "patience": 0.70,
    "intimacy_pull": 0.25,
    "relational_autonomy": 0.60,
    "exploration_openness": 0.55,
    "gossip_tendency": 0.40,
}
ISTJ_NESTED = {"deep": ISTJ_DEEP, "surface": ISTJ_SURFACE}


def test_to_big_five_varies_across_personas():
    """to_big_five 在不同 13 维输入上产出不同 Big Five (派生生效, 非全 0.5)."""
    from emotion_spirit.utils.persona_profiles import to_big_five
    # 高 E 低 N persona vs 低 E 高 N persona
    p1 = {"warmth_bias": 0.8, "expression_drive": 0.8, "gossip_tendency": 0.7,
          "intimacy_pull": 0.7, "relational_gravity": 0.6,
          "boundary_permeability": 0.3, "inner_coherence": 0.8, "patience": 0.7,
          "directness": 0.5, "curiosity": 0.5, "perception_acuity": 0.5,
          "exploration_openness": 0.5}
    p2 = {"warmth_bias": 0.2, "expression_drive": 0.2, "gossip_tendency": 0.3,
          "intimacy_pull": 0.3, "relational_gravity": 0.4,
          "boundary_permeability": 0.8, "inner_coherence": 0.3, "patience": 0.3,
          "directness": 0.5, "curiosity": 0.5, "perception_acuity": 0.5,
          "exploration_openness": 0.5}
    b1 = to_big_five(p1)
    b2 = to_big_five(p2)
    assert b1["extraversion"] > b2["extraversion"], "高 E persona 应派生更高 extraversion"
    assert b1["neuroticism"] < b2["neuroticism"], "低 N persona 应派生更低 neuroticism"
    for v in list(b1.values()) + list(b2.values()):
        assert 0.0 <= v <= 1.0, f"Big Five 值越界 [0,1]: {v}"
    # 非全 0.5 (派生真在算)
    assert any(abs(v - 0.5) > 0.01 for v in b1.values()), "b1 不应全 0.5"


def test_personality_feedback_drift_table_no_big_five():
    """§1.8: personality_feedback drift 表必须 13 维 (无 Big Five key)."""
    pf = (REPO_ROOT / "emotion_spirit" / "regulation" / "personality_feedback.py").read_text(encoding="utf-8")
    violations = BIG_FIVE.findall(pf)
    assert not violations, f"personality_feedback 仍有 Big Five key (drift 表没迁): {violations}"


# ════════════════════════════════════════════════════════════════════════
# Y-转绿 (v1.3.0 Y-1~Y-4): Big Five 死耦合清理 guard tests
# ════════════════════════════════════════════════════════════════════════


def test_personality_with_big_five_helper_unified_entry():
    """§1.8 Y-转绿: personality_with_big_five helper 拍平 13 维 + 注入派生 Big Five.

    统一入口: Big Five consumer 调 personality_with_big_five(nested_or_deep_subdict)
    后应能取到 flat 13 维 Sylanne + 派生 OCEAN.
    """
    from emotion_spirit.utils.persona_profiles import personality_with_big_five

    derived = personality_with_big_five(ISTJ_NESTED)

    # 13 维 Sylanne 拍平: deep 5 + surface 8 = 13
    assert "expression_drive" in derived, "deep 维度未拍平"
    assert derived["expression_drive"] == 0.25
    assert "warmth_bias" in derived, "surface 维度未拍平"
    assert derived["warmth_bias"] == 0.30

    # Big Five 派生注入 (ISTJ 应: 低 E, 高 C, 中低 O, 中 A, 中低 N)
    assert "extraversion" in derived, "Big Five 未注入"
    assert "conscientiousness" in derived
    assert "openness" in derived
    assert "agreeableness" in derived
    assert "neuroticism" in derived
    # ISTJ 应显著偏离 0.5: 高 C (≥0.7), 低 E (≤0.5)
    assert derived["conscientiousness"] >= 0.65, (
        f"ISTJ conscientiousness 派生应 ≥ 0.65, 实际 {derived['conscientiousness']:.3f}"
    )
    assert derived["extraversion"] <= 0.50, (
        f"ISTJ extraversion 派生应 ≤ 0.50, 实际 {derived['extraversion']:.3f}"
    )


def test_suppression_receives_derived_big_five():
    """§1.8 Y-转绿: Suppression.compute 收到派生 Big Five (非 0.5 默认值).

    main.py:429 / surface_handler.py:148 路径 — 传 personality_with_big_five(nested)
    后 baseline 应与"全传 deep 子 dict"显著不同 (ISTJ ≠ 0.5 baseline).
    """
    from emotion_spirit.memory.suppression import SuppressionState
    from emotion_spirit.utils.persona_profiles import personality_with_big_five

    state = SuppressionState()
    derived = personality_with_big_five(ISTJ_NESTED)
    # 派生 personality 应含 OCEAN (5 维), Suppression 用 neuroticism/agreeableness/...
    # 计算 baseline: 0.35*N + 0.25*A + 0.15*(1−O) + 0.20*(1−E) + 0.05*C
    # ISTJ: N≈0.42 (中低), A≈0.30 (高 directness 拉低), O≈0.62, E≈0.30 (低), C≈0.84 (高)
    # 派生 baseline ≈ 0.35*0.42 + 0.25*0.30 + 0.15*0.38 + 0.20*0.70 + 0.05*0.84 ≈ 0.483
    # (vs 全 0.5 时 baseline = 0.5)
    level_derived = state.compute(
        personality=derived,
        context={"authority_present": 0, "social_audience": 0},
        conscience_pressure=0.0,
        relationship_intimacy=0.5,
    )
    # 派生值不应等于"全 0.5 baseline"的结果
    level_default = state.compute(
        personality={},
        context={"authority_present": 0, "social_audience": 0},
        conscience_pressure=0.0,
        relationship_intimacy=0.5,
    )
    assert abs(level_derived - level_default) > 0.01, (
        f"派生 Big Five 没生效: derived={level_derived:.3f} vs default={level_default:.3f}"
    )


def test_collapse_archetype_receives_derived_big_five():
    """§1.8 Y-转绿: CollapseArchetype.select 收到派生 Big Five (非全 0.5).

    memory_pool.py:418 路径 — ISTJ 派生 Big Five 应让 select ≠ DRIFT 默认.
    ISTJ (高 C, 低 E, 中低 N): BAS 算下来低, BIS 中等 → 应选 DRIFT/COLD/COLLAPSE,
    不应是 (caller 传 deep 子 dict 时的全 0.5 → 永远 DRIFT 默认).
    """
    from emotion_spirit.utils.persona_profiles import personality_with_big_five
    from emotion_spirit.regulation.collapse_archetype import (
        CollapseArchetypeSelector, CollapseArchetype,
    )

    selector = CollapseArchetypeSelector()
    derived = personality_with_big_five(ISTJ_NESTED)
    # ISTJ BAS < 0.5 (低 E, 高 C), BIS 中等 → select 应返回某 archetype
    archetype_istj = selector.select(derived)
    # 不应是默认 DRIFT (因 ISTJ BAS+BIS 有区分度)
    # 用另一个极端 persona 验证差异
    EXTREME_HIGH_E_NESTED = {
        "deep": {"expression_drive": 0.95, "boundary_permeability": 0.80,
                 "inner_coherence": 0.20, "relational_gravity": 0.85},
        "surface": {"warmth_bias": 0.95, "patience": 0.10, "curiosity": 0.50,
                    "directness": 0.50, "intimacy_pull": 0.85,
                    "relational_autonomy": 0.20, "exploration_openness": 0.50,
                    "gossip_tendency": 0.85, "perception_acuity": 0.50},
    }
    derived_high_e = personality_with_big_five(EXTREME_HIGH_E_NESTED)
    archetype_high_e = selector.select(derived_high_e)
    assert archetype_istj != archetype_high_e, (
        f"派生 Big Five 没区分: ISTJ={archetype_istj} vs 高E={archetype_high_e} 应不同"
    )


def test_unified_entry_decay_factor_uses_big_five():
    """§1.8 Y-转绿: UnifiedEntry.compute_decay_factor 收到派生 Big Five.

    memory_pool.py:474 路径 — 派生 Big Five 影响 valence_neuro/valence_open/factor_personality.
    ISTJ 派生 personality 应让 factor 与默认 (全 0.5) 显著不同.
    """
    from emotion_spirit.memory.unified_entry import UnifiedEntry
    from emotion_spirit.utils.persona_profiles import personality_with_big_five

    entry = UnifiedEntry(
        id="test_istj", text="test content",
        tags=[], entities={}, source_user="u1", privacy="private",
        created_at=0.0,
        temperature=0.5, emotional_weight=0.5, mass=1.0,
        tier="buffer", is_ghost=False, recall_count=0, last_recalled=0.0,
        peak_temperature=0.5,
    )
    derived = personality_with_big_five(ISTJ_NESTED)
    factor_derived = entry.compute_decay_factor(personality=derived, partner_intimacy=0.5)
    # ISTJ N ≈ 0.42, O ≈ 0.62 → 派生 factor 不等于全 0.5 的 factor
    factor_default = entry.compute_decay_factor(personality={}, partner_intimacy=0.5)
    # 验证 personality 参数真在用 (不是被忽略)
    assert factor_derived > 0.0, "factor 必须为正"
    # ISTJ vs 全 0.5: C=0.84 (高) → extra_conscientious 贡献大, 派生 factor 应 < default factor
    # (高 C → factor < 1.0 → 慢衰减)
    assert factor_derived < factor_default, (
        f"ISTJ 高 C 应派生更慢衰减 (factor<default): "
        f"derived={factor_derived:.3f} vs default={factor_default:.3f}"
    )


def test_life_agent_receives_derived_big_five():
    """§1.8 Y-转绿: LifeAgent 构造后 self._personality 含派生 Big Five (非硬编码 0.5)."""
    from emotion_spirit.agents.life_agent import LifeAgent
    from emotion_spirit.utils.persona_profiles import personality_with_big_five

    derived = personality_with_big_five(ISTJ_NESTED)
    agent = LifeAgent(personality=derived)
    # 派生 Big Five 注入 self._personality
    assert agent._personality.get("extraversion") != 0.5, (
        f"LifeAgent._personality 没收到派生 Big Five: extraversion={agent._personality.get('extraversion')}"
    )
    # ISTJ 应: 低 E, 高 C
    assert agent._personality["extraversion"] <= 0.5
    assert agent._personality["conscientiousness"] >= 0.65
    # 13 维 Sylanne 拍平也应在
    assert agent._personality.get("curiosity") == 0.60, (
        f"13 维 Sylanne 拍平缺失: curiosity={agent._personality.get('curiosity')}"
    )
    assert agent._personality.get("inner_coherence") == 0.95


def test_life_agent_set_personality_updates():
    """§1.8 Y-转绿: LifeAgent.set_personality(labels 变化时由 main.py:484 调) 注入派生 Big Five."""
    from emotion_spirit.agents.life_agent import LifeAgent
    from emotion_spirit.utils.persona_profiles import personality_with_big_five

    # 初始 OCEAN 0.5 (硬编码 fallback)
    agent = LifeAgent()
    assert agent._personality.get("extraversion") == 0.5
    # labels 变化后调 set_personality(派生 flat)
    derived = personality_with_big_five(ISTJ_NESTED)
    agent.set_personality(derived)
    assert agent._personality["extraversion"] != 0.5
    assert agent._personality["conscientiousness"] >= 0.65


def test_compute_feedback_current_uses_real_value():
    """§1.8 Y-转绿: compute_feedback 收到 flat 含 13 维时, current 是真实值.

    life_simulator.py:678 路径 (实际由 C 任务自动修活, 但仍加 guard).
    派生 flat 应含 13 维 (curiosity 等), current 不应退化为 0.5.

    测试技巧: 用 curiosity=0.96 (接近 clamp 上限 0.95) 触发 clamp 行为:
    - 派生 flat 含 curiosity=0.96 → adjusted=+0.0012 → clamp(0.96+0.0012)=0.95 → delta = 0.95-0.96 = -0.01
    - OCEAN-only (无 curiosity) → current=0.5 → adjusted=+0.0012 → clamp=0.5012 → delta = 0.0012
    两者差异显著 (>0.01), 可区分 helper 是否真注入 13 维.
    """
    from emotion_spirit.regulation.personality_feedback import PersonalityFeedback
    from emotion_spirit.utils.persona_profiles import personality_with_big_five

    # 派生 flat 含 curiosity=0.96 (接近 clamp 上限)
    HIGH_CURIOSITY_NESTED = {
        "deep": {"expression_drive": 0.5, "perception_acuity": 0.5,
                 "boundary_permeability": 0.5, "inner_coherence": 0.5,
                 "relational_gravity": 0.5},
        "surface": {"warmth_bias": 0.5, "directness": 0.5, "curiosity": 0.96,
                    "patience": 0.5, "intimacy_pull": 0.5,
                    "relational_autonomy": 0.5, "exploration_openness": 0.5,
                    "gossip_tendency": 0.5},
    }
    derived = personality_with_big_five(HIGH_CURIOSITY_NESTED)
    pf = PersonalityFeedback(feedback_rate=1.0)
    # creative 给 curiosity +0.0012 → clamp(0.96+0.0012)=0.95 → delta = 0.95-0.96 = -0.01
    delta = pf.compute_feedback(derived, "creative")
    # OCEAN-only (无 curiosity) → current=0.5 → delta = 0.5012-0.5 = +0.0012
    ocean_only = {"extraversion": 0.5, "neuroticism": 0.5, "agreeableness": 0.5,
                  "conscientiousness": 0.5, "openness": 0.5}
    delta_ocean = pf.compute_feedback(ocean_only, "creative")
    # 派生 flat 含 13 维 → curiosity=0.96 (触发 clamp, delta=-0.01)
    # OCEAN-only → curiosity=0.5 (不触发 clamp, delta=+0.0012)
    assert "curiosity" in delta
    assert delta["curiosity"] < 0, (
        f"派生 flat curiosity=0.96 应触发 clamp 产生负 delta, 实际 {delta['curiosity']}"
    )
    assert abs(delta["curiosity"] - delta_ocean["curiosity"]) > 0.005, (
        f"compute_feedback 没拿 13 维真实值: derived_delta={delta['curiosity']} "
        f"vs ocean_only_delta={delta_ocean['curiosity']} 应显著不同"
    )