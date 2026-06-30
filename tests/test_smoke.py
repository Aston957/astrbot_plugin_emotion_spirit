"""Smoke tests — 拦截 release blocker 级别的结构/初始化 bug。

这些测试不需要 AstrBot 运行时, 只验证代码自身的结构完整性:
- 类定义了它调用的所有方法
- 关键导入路径可以解析
- persona_report_parser 推断逻辑基本正确

v1.2.5: 因 Bug 10 (_init_modules_phase2 缺失) 新增。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


# ═══ 辅助: 找到项目根目录 ═══

def _plugin_root() -> Path:
    """Return the astrbot_plugin_emotion_spirit package root."""
    return Path(__file__).resolve().parent.parent


def _main_py_source() -> str:
    """Read main.py source."""
    return (_plugin_root() / "main.py").read_text(encoding="utf-8")


# ═══ Test 1: 结构完整性 — 所有 self._init_* 调用都有对应定义 ═══

class TestStructuralIntegrity:
    """验证 _setup_persona_state 调用的每个方法都存在定义。

    Bug 10 根因: _init_modules_phase2 被调用但从未定义。
    这个 test 直接在 AST 层面检测, 不需要任何运行时依赖。
    """

    def test_all_init_methods_have_definitions(self):
        """_setup_persona_state 调用的每个 self._init_* 方法必须有 def 定义。"""
        source = _main_py_source()
        tree = ast.parse(source)

        # 找到 _setup_persona_state 方法体中的 self.xxx() 调用
        called_methods: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_setup_persona_state":
                for stmt in ast.walk(node):
                    if (
                        isinstance(stmt, ast.Call)
                        and isinstance(stmt.func, ast.Attribute)
                        and isinstance(stmt.func.value, ast.Name)
                        and stmt.func.value.id == "self"
                    ):
                        called_methods.add(stmt.func.attr)

        # 找到类中定义的所有方法
        defined_methods: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "EmotionSpiritPlugin":
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        defined_methods.add(item.name)

        missing = called_methods - defined_methods
        assert not missing, (
            f"EmotionSpiritPlugin 调用了未定义的方法: {missing}. "
            f"已定义的方法: {sorted(defined_methods)}, "
            f"被调用的方法: {sorted(called_methods)}"
        )

    def test_no_dangling_phase2_references(self):
        """main.py 中不应残留 _init_modules_phase2 的任何引用。"""
        source = _main_py_source()
        assert "_init_modules_phase2" not in source, (
            "main.py 中仍引用 _init_modules_phase2, "
            "该方法已被移除 (Bug 10 fix)"
        )


# ═══ Test 2: persona_report_parser 推断逻辑 ═══

class TestPersonaReportParser:
    """验证人格推断的关键场景。

    Bug 9 根因: "开朗+不分析" 被误判为 INTJ 而非 ENFP。
    v1.2.2 已修复否定词预处理, 此 test 确保 regression 不再发生。
    """

    def test_enfp_not_misjudged_as_intj(self):
        """'开朗+不分析' 组合不应被判为 INTJ。"""
        from emotion_spirit.regulation.persona_report_parser import parse_persona_report

        enfp_prompt = (
            "广濑是一个性格开朗、善良、没有太多心机的普通高中男生。"
            "依靠直觉和感受，而不是长时间思考。"
            "对世界保持新鲜感。"
        )
        result = parse_persona_report(enfp_prompt)
        mbti = result.labels.get("mbti", "")
        # ENFP 或 ESFP 都可接受 — 重点是 E + F + P, 不是 INTJ
        assert mbti not in {"INTJ", "INFJ", "ISTJ"}, (
            f"开朗外向型人格不应被判为内向型, got mbti={mbti}"
        )
        assert mbti[0] == "E", f"开朗应判为 E (外向), got mbti={mbti}"
        assert "F" in mbti, f"'依靠感受' 应判为 F (情感), got mbti={mbti}"

    def test_introvert_not_misjudged_as_extrovert(self):
        """内向型描述不应被判为外向。"""
        from emotion_spirit.regulation.persona_report_parser import parse_persona_report

        intj_prompt = (
            "他喜欢独处，一个人待着就很满足。"
            "总是用逻辑分析问题，追求客观和理性。"
            "有明确的计划和安排，不喜变动。"
        )
        result = parse_persona_report(intj_prompt)
        mbti = result.labels.get("mbti", "")
        assert mbti[0] == "I", f"独处型应判为 I (内向), got mbti={mbti}"

    def test_time_focus_not_judged_as_future_without_evidence(self):
        """没有明确"未来/计划"关键词时, time_focus 不应判为"活在未来"。"""
        from emotion_spirit.regulation.persona_report_parser import parse_persona_report

        prompt = "她喜欢活在当下，享受每一天。"
        result = parse_persona_report(prompt)
        tf = result.labels.get("time_focus", "")
        assert tf != "活在未来", (
            f"描述'活在当下'不应判为'活在未来', got time_focus={tf}"
        )


# ═══ Test 3: 关键模块可导入 ═══

class TestModuleImports:
    """验证核心模块路径可以解析。

    这不是真正的 import (需要 AstrBot 运行时), 而是检查 .py 文件存在
    且可以被 Python AST 解析, 没有 SyntaxError。
    """

    @pytest.mark.parametrize("rel_path", [
        "emotion_spirit/regulation/persona_report_parser.py",
        "emotion_spirit/core/plugin_factory.py",
        "emotion_spirit/output/command_router.py",
        "emotion_spirit/output/public_api.py",
        "emotion_spirit/output/commands.py",
        "emotion_spirit/output/surface_handler.py",
    ])
    def test_core_module_parseable(self, rel_path):
        """核心模块文件存在且可被 Python 解析。"""
        path = _plugin_root() / rel_path
        assert path.exists(), f"核心模块文件不存在: {rel_path}"
        source = path.read_text(encoding="utf-8")
        # AST parse 会捕获 syntax error
        ast.parse(source, filename=str(path))
