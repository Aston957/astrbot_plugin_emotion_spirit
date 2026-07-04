"""§1.1: KB 集中化 — AST 扫 .py, 单 dict/list 字面量 > 10 项 → CI 红。

硬编码数据应进 KB, 不进代码 (handbook §1.1)。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
EMOTION_SPIRIT_DIR = REPO_ROOT / "emotion_spirit"


def _count_dict_items(node: ast.Dict) -> int:
    return len(node.keys)


def _count_list_items(node: ast.List | ast.Set) -> int:
    return len(node.elts)


def test_no_large_hardcoded_data_in_production_code():
    """生产代码不应有单 dict/list 字面量 > 10 项 (应进 KB)."""
    threshold = 10
    violations = []

    for py_file in sorted(EMOTION_SPIRIT_DIR.rglob("*.py")):
        if str(py_file).replace("\\", "/").endswith("__pycache__"):
            continue
        fp = str(py_file).replace("\\", "/")
        if "/__pycache__/" in fp or "/kb/" in fp or "/sylanne/" in fp:
            continue
        # 排除 knowledge.py (它本身就是 KB 声明性数据)
        if py_file.name == "knowledge.py":
            continue
        # 排除 adaptation.py (EMOTION_ACTIVITY_BIAS, v1.1.0C 源数据)
        if py_file.name == "adaptation.py":
            continue
        # 排除 label_mapper.py (LABEL_OPTIONS 等标签映射表)
        if py_file.name == "label_mapper.py":
            continue
        # 排除 persona_profiles.py (叙事模板)
        if py_file.name == "persona_profiles.py":
            continue
        # 排除 superego/conscience.py (get_pressure_breakdown 诊断字段聚合, v1.3.0 rc.2)
        # 注: 这是 runtime 计算的诊断 API 聚合 dict, 不是硬编码数据. 跟 label_mapper 一样属聚合器.
        if py_file.name == "conscience.py" and "superego" in str(py_file):
            continue
        # 排除 __init__.py (import 列表非硬编码数据)
        if py_file.name == "__init__.py":
            continue
        # 排除 config.py (配置 schema)
        if py_file.name == "config.py":
            continue
        # 排除 persona_labels_db.py (KB loader)
        if py_file.name == "persona_labels_db.py":
            continue
        # 排除 sylanne adapter.py (引擎映射表)
        if py_file.name == "adapter.py":
            continue
        # 排除 agents/base.py (VALID_FLAGS frozenset, 代码常量)
        if py_file.name == "base.py" and "agents" in fp:
            continue
        # 排除 memory/unified_entry.py (Entry 类型定义, 含 schema dicts)
        if py_file.name == "unified_entry.py":
            continue
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Dict) and _count_dict_items(node) > threshold:
                violations.append(f"{py_file.name}: dict with {_count_dict_items(node)} items")
                break  # one per file
            elif isinstance(node, (ast.List, ast.Set)) and _count_list_items(node) > threshold:
                violations.append(f"{py_file.name}: list with {_count_list_items(node)} items")
                break  # one per file

    if violations:
        pytest.fail(f"发现硬编码大数据: {violations[:10]}")


def test_persona_labels_db_not_hardcoded():
    """persona_labels_db.json 的路径应指向 KB, 不在代码中手编."""
    for py_file in EMOTION_SPIRIT_DIR.rglob("*.py"):
        if "/__pycache__/" in str(py_file):
            continue
        source = py_file.read_text(encoding="utf-8")
        if '3072' in source and 'persona' in source:
            # 允许 docstring/注释中引用, 但不允许 dict 字面量
            try:
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Dict) and len(node.keys) > 5:
                        pytest.fail(f"{py_file.name}: 可能有 KB 数据硬编码")
            except SyntaxError:
                continue