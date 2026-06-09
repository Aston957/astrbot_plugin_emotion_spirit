"""Tests for PersonaAnalyzer 3-class split (Phase C, P3-6).

拆 3 类后, 验证:
1. RuleBasedAnalyzer 独立可用 (无 LLM 也能解析)
2. LLMAnalyzer 强制要求 llm_callable
3. LLMAnalyzer.analyze 调用 LLM
4. PersonaAnalyzerWithFallback LLM 优先, 失败走 RuleBased
5. 向后兼容: PersonaAnalyzer(llm) 仍可用
6. 持久化: save_report / load_report round-trip
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run(coro):
    """Helper: 跑 async coroutine (跟其他测试一致用 asyncio.run)."""
    return asyncio.run(coro)


def test_rule_based_analyzer_returns_labels_without_llm():
    """RuleBasedAnalyzer 能在没 LLM 时返回 labels (基于 system_prompt 模式匹配)。"""
    from emotion_spirit.regulation.persona_analyzer import RuleBasedAnalyzer
    analyzer = RuleBasedAnalyzer()
    result = _run(analyzer.analyze("alice", "INFP 焦虑型 表达型 顺应型 活在当下"))
    assert result.persona_id == "alice"
    assert result.has_labels
    assert result.labels["mbti"] == "INFP"
    assert result.source == "rule_based"


def test_llm_analyzer_requires_llm_callable():
    """LLMAnalyzer 必须传 llm_callable, 不传抛错。"""
    from emotion_spirit.regulation.persona_analyzer import LLMAnalyzer
    try:
        LLMAnalyzer()
        assert False, "LLMAnalyzer() should raise TypeError"
    except TypeError:
        pass  # expected: missing required argument 'llm'


def test_llm_analyzer_invokes_llm():
    """LLMAnalyzer.analyze 调用 llm 拿 labels。"""
    from emotion_spirit.regulation.persona_analyzer import LLMAnalyzer

    class MockLLM:
        async def __call__(self, system, prompt):
            return "mbti: INFP\nattachment: 焦虑型\nemotion_style: 表达型\nconflict_style: 顺应型\ntime_focus: 活在当下"

    analyzer = LLMAnalyzer(MockLLM())
    result = _run(analyzer.analyze("alice", "some prompt"))
    assert result.has_labels
    assert result.labels["mbti"] == "INFP"
    assert result.source == "llm"


def test_fallback_analyzer_uses_rule_based_when_llm_fails():
    """PersonaAnalyzerWithFallback LLM 失败时 fallback 到 RuleBased。"""
    from emotion_spirit.regulation.persona_analyzer import (
        PersonaAnalyzerWithFallback, RuleBasedAnalyzer,
    )

    class FailingLLM:
        async def __call__(self, system, prompt):
            raise RuntimeError("LLM 不可用")

    fallback = RuleBasedAnalyzer()
    analyzer = PersonaAnalyzerWithFallback(llm=FailingLLM(), fallback=fallback)
    result = _run(analyzer.analyze("alice", "INFP 焦虑型 表达型 顺应型 活在当下"))
    assert result.has_labels
    assert result.labels["mbti"] == "INFP"
    assert result.source == "rule_based"  # 走 fallback


def test_fallback_analyzer_uses_llm_when_works():
    """LLM 成功时优先用 LLM, source = 'llm'。"""
    from emotion_spirit.regulation.persona_analyzer import (
        PersonaAnalyzerWithFallback, RuleBasedAnalyzer,
    )

    class WorkingLLM:
        async def __call__(self, system, prompt):
            return "mbti: INFP\nattachment: 焦虑型\nemotion_style: 表达型\nconflict_style: 顺应型\ntime_focus: 活在当下"

    fallback = RuleBasedAnalyzer()
    analyzer = PersonaAnalyzerWithFallback(llm=WorkingLLM(), fallback=fallback)
    result = _run(analyzer.analyze("alice", "some prompt"))
    assert result.has_labels
    assert result.source == "llm"


def test_fallback_analyzer_works_without_llm():
    """PersonaAnalyzerWithFallback(llm=None) 走 RuleBased。"""
    from emotion_spirit.regulation.persona_analyzer import PersonaAnalyzerWithFallback

    analyzer = PersonaAnalyzerWithFallback(llm=None)
    result = _run(analyzer.analyze("alice", "INFP 焦虑型 表达型 顺应型 活在当下"))
    assert result.has_labels
    assert result.source == "rule_based"
    assert result.labels["mbti"] == "INFP"


def test_backward_compat_persona_analyzer_alias():
    """PersonaAnalyzer = PersonaAnalyzerWithFallback (向后兼容别名)。"""
    from emotion_spirit.regulation.persona_analyzer import (
        PersonaAnalyzer, PersonaAnalyzerWithFallback,
    )
    assert PersonaAnalyzer is PersonaAnalyzerWithFallback

    # 旧用法: PersonaAnalyzer(llm) 仍能工作
    class WorkingLLM:
        async def __call__(self, system, prompt):
            return "mbti: ISTJ\nattachment: 安全型"

    analyzer = PersonaAnalyzer(llm=WorkingLLM())
    result = _run(analyzer.analyze("bob", "some text"))
    assert result.has_labels
    assert result.source == "llm"

    # 旧用法: PersonaAnalyzer(llm=None) 仍能工作
    analyzer_no_llm = PersonaAnalyzer(llm=None)
    result_no_llm = _run(analyzer_no_llm.analyze("bob", "INFP 焦虑型 表达型 顺应型 活在当下"))
    assert result_no_llm.has_labels
    assert result_no_llm.source == "rule_based"


def test_persona_analysis_result_has_labels_property():
    """PersonaAnalysisResult.has_labels: True 当 labels 非空。"""
    from emotion_spirit.regulation.persona_analyzer import PersonaAnalysisResult

    # 有 labels
    r1 = PersonaAnalysisResult(
        persona_id="x", labels={"mbti": "INFP"}, drives={},
        source="rule_based", confidence=0.5,
    )
    assert r1.has_labels is True

    # 空 labels
    r2 = PersonaAnalysisResult(
        persona_id="x", labels={}, drives={},
        source="rule_based", confidence=0.5,
    )
    assert r2.has_labels is False

    # 全 None/空值
    r3 = PersonaAnalysisResult(
        persona_id="x", labels={"mbti": ""}, drives={},
        source="rule_based", confidence=0.5,
    )
    assert r3.has_labels is False


def test_persona_analysis_result_to_from_dict_roundtrip(tmp_path):
    """save_report / load_report round-trip 保留 5 字段。"""
    from emotion_spirit.regulation.persona_analyzer import (
        PersonaAnalysisResult, save_report, load_report,
    )

    original = PersonaAnalysisResult(
        persona_id="alice",
        labels={"mbti": "INFP", "attachment": "焦虑型"},
        drives={"curiosity": 0.7, "expression": 0.5},
        source="llm",
        confidence=0.85,
    )
    save_report(original, tmp_path)

    loaded = load_report(tmp_path)
    assert loaded is not None
    assert loaded.persona_id == "alice"
    assert loaded.labels == {"mbti": "INFP", "attachment": "焦虑型"}
    assert loaded.drives == {"curiosity": 0.7, "expression": 0.5}
    assert loaded.source == "llm"
    assert loaded.confidence == 0.85


def test_load_report_returns_none_when_missing(tmp_path):
    """load_report 在文件不存在时返回 None。"""
    from emotion_spirit.regulation.persona_analyzer import load_report

    result = load_report(tmp_path)
    assert result is None


def test_register_decorator_preserved():
    """PersonaAnalyzerWithFallback 仍注册到 ModuleRegistry (向后兼容)。

    Note: test_module_registry 会 reset registry, 所以这里 importlib.reload
    重新触发 @register 装饰器, 确保 persona_analyzer 在 registry 里。
    """
    import importlib
    from emotion_spirit.core.registry import ModuleRegistry
    from emotion_spirit import persona_analyzer

    # 重新加载触发 @register 装饰器 (即使前面 test reset 了 registry)
    importlib.reload(persona_analyzer)

    spec = ModuleRegistry.get_all().get("persona_analyzer")
    assert spec is not None, "persona_analyzer 应该在 ModuleRegistry 里"
    assert spec.module_class is persona_analyzer.PersonaAnalyzerWithFallback
    # 同时验证 PersonaAnalyzer 是 PersonaAnalyzerWithFallback 的别名
    assert persona_analyzer.PersonaAnalyzer is persona_analyzer.PersonaAnalyzerWithFallback
