"""§1.6 规则 1: agent 是连线, 不是节点 — 方法体不应有算法实现."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
AGENTS_DIR = REPO_ROOT / "emotion_spirit" / "agents"

# 允许的流程控制 + 调组件模式
_ALLOWED = {
    "perceive": ["return", "dict", "get", "try", "except", "if", "callable"],
    "gate": ["return", "if", "elif", "else", "not"],
    "act": ["return", "if", "try", "except", "await", "for", "import",
            "AgentIntent"],
}


def test_agent_methods_no_algorithm_implementation():
    """agent 方法体不该有算法实现 (只应调组件 + 流程控制)."""
    violations = []

    # 允许 SelfCore._compose 用 for 循环 (组合多 agent 输出)
    allowed_for_loop = {"_compose"}

    for py_file in AGENTS_DIR.rglob("*.py"):
        if py_file.name == "__init__.py" or "/__pycache__/" in str(py_file):
            continue
        if py_file.name == "self_core.py":
            continue  # SelfCore._compose 是编排器, 允许 for
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                name = node.name
                if name in allowed_for_loop:
                    continue
                # 检查是否有 for 循环 (算法标志)
                if any(isinstance(n, ast.For) for n in ast.walk(node)):
                    violations.append(f"{py_file.name}.{name}: for 循环")
                # 检查是否有复杂的算术表达式
                for child in ast.walk(node):
                    if isinstance(child, ast.BinOp) and isinstance(child.op, (ast.Mult, ast.Div, ast.Pow)):
                        violations.append(f"{py_file.name}.{name}: 算术运算")
                        break

    assert not violations, f"agent 可能含算法实现: {violations[:10]}"


def test_agent_methods_call_components():
    """agent 方法应调用 self._xxx 组件 (连线模式)."""
    for py_file in AGENTS_DIR.rglob("*.py"):
        if py_file.name == "__init__.py" or "/__pycache__/" in str(py_file) or py_file.name == "base.py":
            continue
        source = py_file.read_text(encoding="utf-8")
        # 每个 agent act 方法应包含 self._xxx 调用
        if "async def act" in source and "self._" not in source:
            assert False, f"{py_file.name}: act 方法没有 self._ 组件调用"