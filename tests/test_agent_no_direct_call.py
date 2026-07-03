"""§1.6 规则 2: agent 不互相直接调 — 走 SelfCore 统一编排."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
AGENTS_DIR = REPO_ROOT / "emotion_spirit" / "agents"

_BLACKLIST_IMPORTS = [
    "from .memory_agent import",
    "from .personality_agent import",
    "from .relationship_agent import",
    "from .life_agent import",
    "from .self_core import",
    "from .event_bus import",
]


def test_agent_no_direct_import_of_other_agents():
    """agent 文件不 import 其他 agent (走 SelfCore)."""
    violations = []

    for py_file in AGENTS_DIR.rglob("*.py"):
        if py_file.name == "__init__.py" or "/__pycache__/" in str(py_file):
            continue
        source = py_file.read_text(encoding="utf-8")
        for bl in _BLACKLIST_IMPORTS:
            if bl in source:
                violations.append(f"{py_file.name}: {bl}")
            # Also check AST for import statements
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "agents" in node.module:
                    if "__init__" not in node.module:
                        violations.append(f"{py_file.name}: from {node.module} import ...")

    assert not violations, f"agent 直接调用其他 agent: {violations}"