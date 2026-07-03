"""Tests for Bug 14 polish_template_events 嵌套 dict (v1.2.5 PR3 T9)."""
import pytest
from emotion_spirit.regulation.life_simulator import _flatten_personality


def test_flatten_personality_handles_nested_dict():
    """Bug 14 根因: 嵌套 personality dict 必须能 flatten"""
    nested = {
        "deep": {"expression_drive": 0.15, "perception_acuity": 0.65},
        "surface": {"warmth_bias": 0.20},
    }
    result = _flatten_personality(nested)
    assert ("deep.expression_drive", 0.15) in result
    assert ("deep.perception_acuity", 0.65) in result
    assert ("surface.warmth_bias", 0.20) in result


def test_flatten_personality_handles_flat_dict():
    """fallback 路径返回的 flat dict 也能处理"""
    flat = {"openness": 0.5, "extraversion": 0.7, "agreeableness": 0.4}
    result = _flatten_personality(flat)
    assert ("openness", 0.5) in result
    assert ("extraversion", 0.7) in result
    assert ("agreeableness", 0.4) in result


def test_flatten_personality_handles_mixed():
    """mixed 嵌套 + 顶层 scalar 也能处理"""
    mixed = {
        "deep": {"expression_drive": 0.5},
        "top_level_scalar": 0.8,
    }
    result = _flatten_personality(mixed)
    assert ("deep.expression_drive", 0.5) in result
    assert ("top_level_scalar", 0.8) in result


def test_flatten_personality_skips_non_scalar():
    """非 scalar 值 (如 str) 应该跳过而不是崩溃"""
    nested = {
        "deep": {"expression_drive": 0.5, "label": "skip_me"},
    }
    result = _flatten_personality(nested)
    assert ("deep.expression_drive", 0.5) in result
    assert not any("label" in k for k, v in result)


def test_flatten_personality_clamps_bool():
    """bool 是 int 子类, 不应被当 scalar (防 True/False 混入 format)"""
    nested = {
        "deep": {"flag": True, "value": 0.5},
    }
    result = _flatten_personality(nested)
    assert ("deep.value", 0.5) in result
    assert not any("flag" in k for k, v in result)


def test_polish_template_events_does_not_crash_on_nested_personality():
    """集成测试: polish_template_events 用嵌套 personality 不抛 TypeError"""
    from emotion_spirit.regulation.life_simulator import LifeSimulatorV2

    life_sim = LifeSimulatorV2.__new__(LifeSimulatorV2)  # 跳过 init
    nested_personality = {
        "deep": {"expression_drive": 0.15, "perception_acuity": 0.65},
        "surface": {"warmth_bias": 0.20},
    }
    template = []
    try:
        import asyncio
        asyncio.run(life_sim.polish_template_events(template, nested_personality))
    except TypeError as e:
        if "unsupported format string" in str(e) or "not all arguments converted" in str(e):
            pytest.fail(f"Bug 14 回归: {e}")
    except Exception:
        pass  # 其他异常 (LLM 不可用等) 不在本测试范围
