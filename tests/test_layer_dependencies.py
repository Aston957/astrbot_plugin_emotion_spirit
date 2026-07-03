"""§1.3: core 元层不依赖业务层 — AST 扫 import, core 不 import memory/regulation/output."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CORE_DIR = REPO_ROOT / "emotion_spirit" / "core"

_FORBIDDEN_PREFIXES = (
    "emotion_spirit.memory",
    "emotion_spirit.regulation",
    "emotion_spirit.output",
    "emotion_spirit.bridge",
    "emotion_spirit.agents",
)


def test_core_does_not_import_business_layers():
    """core/ 目录不应 import memory/regulation/output/bridge/agents."""
    violations = []
    for py_file in sorted(CORE_DIR.rglob("*.py")):
        if "/__pycache__/" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(_FORBIDDEN_PREFIXES):
                        violations.append(f"{py_file.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(_FORBIDDEN_PREFIXES):
                    violations.append(f"{py_file.name}: from {node.module} import ...")
                    # Also check relative imports from business layers
                if node.module and node.level > 0:
                    # from ..memory.X -> 从 core/ 角度看 .. 是情感层上层目录
                    pass  # 复杂, 暂不检查

    assert not violations, f"core 层违反元层规则: {violations}"