"""Tests for persona_profiles.py — 通用维度映射版本"""

import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotion_spirit.utils import (
    get_personality_params,
    get_intimacy_weights,
    get_intimacy_modulation,
    get_value_behaviors,
    DIMENSION_DISPLAY,
    get_narrative,
)
from emotion_spirit.utils.persona_profiles import (
    _ACTION_ALIGN,
    _ACTION_MISALIGN,
    _select_variant,
)
from emotion_spirit.utils import KnowledgeBase

# Phase B Step 3: NARRATIVE_TEMPLATES 走 KnowledgeBase (单一数据源)
NARRATIVE_TEMPLATES = KnowledgeBase.NARRATIVE_TEMPLATES


def test_value_behaviors_generic():
    """通用映射返回维度名作为 key (v1.7: 12 维)。"""
    vb = get_value_behaviors()
    assert isinstance(vb, dict)
    assert len(vb) > 0
    # key 应该是 12 维维度名 (v1.7: 11→12)
    for dim_name in vb:
        assert dim_name in DIMENSION_DISPLAY, f"{dim_name} not in DIMENSION_DISPLAY"


def test_value_behaviors_has_aligned_misaligned():
    """每个维度都应有 aligned 和 misaligned 列表。"""
    vb = get_value_behaviors()
    for dim, mapping in vb.items():
        assert "aligned" in mapping, f"{dim} missing aligned"
        assert "misaligned" in mapping, f"{dim} missing misaligned"


def test_value_behaviors_express():
    """express 应该在 expression_drive 的 aligned 中。"""
    vb = get_value_behaviors()
    assert "express" in vb["expression_drive"]["aligned"]


def test_value_behaviors_withdraw():
    """withdraw 应该在 relational_gravity 的 misaligned 中。"""
    vb = get_value_behaviors()
    assert "withdraw" in vb["relational_gravity"]["misaligned"]


def test_action_align_coverage():
    """所有 _ACTION_ALIGN 中的动作都应出现在映射中。"""
    vb = get_value_behaviors()
    all_aligned = set()
    for mapping in vb.values():
        all_aligned.update(mapping["aligned"])
    for action in _ACTION_ALIGN:
        assert action in all_aligned, f"{action} not found in any aligned list"


def test_dimension_display_coverage():
    """DIMENSION_DISPLAY 应覆盖 12 维 (v1.7: 11→12)。"""
    assert len(DIMENSION_DISPLAY) == 12
    expected = {
        "expression_drive", "perception_acuity", "boundary_permeability",
        "inner_coherence", "relational_gravity", "warmth_bias",
        "directness", "curiosity", "patience", "intimacy_pull",
        "relational_autonomy", "exploration_openness",  # v1.7: autonomy_guard 拆分
    }
    assert set(DIMENSION_DISPLAY.keys()) == expected


def test_xiaotian_params():
    """v1.7.2 + Phase B B3: 回避型 在 KB 中无 expression_drive delta, 新值 = 0.25 (baseline) - 0.10 (I) = 0.15。"""
    params = get_personality_params({"mbti": "INTP", "attachment": "回避型"})
    assert params["deep"]["expression_drive"] == 0.15
    assert params["surface"]["curiosity"] == 0.75


def test_xiaofu_params():
    params = get_personality_params({"mbti": "ENFP", "attachment": "焦虑型"})
    assert params["deep"]["expression_drive"] == 0.55
    assert params["surface"]["warmth_bias"] == 0.6


def test_intimacy_weights():
    weights = get_intimacy_weights()
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01


def test_intimacy_modulation():
    mod = get_intimacy_modulation()
    assert "alpha" in mod


# ═══ Phase 3: 叙事模板测试 ═══

def test_narrative_templates_coverage():
    """v1.7.2 + Phase B B3: NARRATIVE_TEMPLATES 走 KnowledgeBase (11 dim, 无 perception_acuity)。"""
    expected_dims = {
        "relational_gravity", "intimacy_pull", "warmth_bias", "expression_drive",
        "directness", "curiosity", "patience", "boundary_permeability",
        "inner_coherence", "relational_autonomy", "exploration_openness",
    }
    assert set(KnowledgeBase.NARRATIVE_TEMPLATES.keys()) == expected_dims
    scenes = {"violation", "alignment", "advice"}
    for dim, variants in KnowledgeBase.NARRATIVE_TEMPLATES.items():
        for variant in ("high", "low"):
            assert variant in variants, f"{dim} missing {variant}"
            assert set(variants[variant].keys()) == scenes, f"{dim}/{variant} missing scenes"


def test_select_variant_high():
    """warmth_bias > 阈值 → 选择 high 变体"""
    personality = {
        "deep": {}, "surface": {"warmth_bias": 0.7, "intimacy_pull": 0.3},
    }
    # relational_gravity 用 warmth_bias (阈值 0.5)
    assert _select_variant("relational_gravity", personality) == "high"


def test_select_variant_low():
    """warmth_bias ≤ 阈值 → 选择 low 变体"""
    personality = {
        "deep": {}, "surface": {"warmth_bias": 0.3, "intimacy_pull": 0.3},
    }
    assert _select_variant("relational_gravity", personality) == "low"


def test_select_variant_no_personality():
    """无 personality → 默认 high"""
    assert _select_variant("warmth_bias", None) == "high"


def test_get_narrative_violation():
    """get_narrative 应返回人格化的 violation 叙事"""
    personality = {
        "deep": {}, "surface": {"warmth_bias": 0.7},
    }
    text = get_narrative("relational_gravity", "violation", personality)
    assert "忽略" in text or "在乎" in text


def test_get_narrative_advice():
    """get_narrative 应返回人格化的 advice 叙事"""
    personality = {
        "deep": {}, "surface": {"warmth_bias": 0.7},
    }
    text = get_narrative("relational_gravity", "advice", personality)
    assert "联系" in text or "想念" in text


def test_get_narrative_fallback():
    """未知维度 → 返回 DIMENSION_DISPLAY 名称"""
    text = get_narrative("unknown_dim", "violation", None)
    assert text == "unknown_dim"


def test_get_narrative_no_personality():
    """v1.7.2 + Phase B B3: 无 personality → 使用默认变体 (high), 走 KnowledgeBase.NARRATIVE_TEMPLATES。"""
    text = get_narrative("warmth_bias", "violation", None)
    # KB warmth_bias high violation = "你最近对人的温暖减少了" (B2 文本重写)
    assert "温暖" in text or "冷淡" in text
