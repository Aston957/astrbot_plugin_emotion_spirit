# tests/test_dir_structure.py
"""Phase 4 C4 — 4 层目录结构验证 (3 tests)"""
import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
EMOTION_SPIRIT_DIR = REPO_ROOT / "emotion_spirit"


# 37 modules + layer.py 在 v2 路径列表
V2_PATHS = [
    # L0 core
    "emotion_spirit.core.registry", "emotion_spirit.core.config",
    "emotion_spirit.core.knowledge", "emotion_spirit.core.persona_labels_db",
    "emotion_spirit.core.label_mapper", "emotion_spirit.core.plugin_factory",
    # L1 memory
    "emotion_spirit.memory.persona_profiles", "emotion_spirit.memory.memory_pool",
    "emotion_spirit.memory.intimacy", "emotion_spirit.memory.relationship_personality",
    "emotion_spirit.memory.social_graph", "emotion_spirit.memory.topic_privacy",
    "emotion_spirit.memory.meaning_reservoir",
    # L2 regulation
    "emotion_spirit.regulation.superego", "emotion_spirit.regulation.superego_guard",
    "emotion_spirit.regulation.body_state", "emotion_spirit.regulation.force_dynamics",
    "emotion_spirit.regulation.personality_drift", "emotion_spirit.regulation.shadow_detector",
    "emotion_spirit.regulation.pattern_extractor", "emotion_spirit.regulation.life_simulator",
    "emotion_spirit.regulation.persona_analyzer", "emotion_spirit.regulation.persona_report_parser",
    "emotion_spirit.regulation.counterfactual",
    # L3 output
    "emotion_spirit.output.bot_decision", "emotion_spirit.output.emotion_classifier",
    "emotion_spirit.output.prompt_injector", "emotion_spirit.output.surface_consumer",
    "emotion_spirit.output.surface_handler", "emotion_spirit.output.diary_writer",
    "emotion_spirit.output.command_router", "emotion_spirit.output.commands",
    "emotion_spirit.output.narrative_identity", "emotion_spirit.output.predictive_sentinel",
    "emotion_spirit.output.public_api", "emotion_spirit.output.buffer_signals",
    "emotion_spirit.output.trend_utils",
    # 根层 (留根)
    "emotion_spirit.layer",
]


def test_imports_all_modules_v2_path():
    """所有 37 modules + layer.py 从 v2 路径可导入。"""
    for path in V2_PATHS:
        try:
            importlib.import_module(path)
        except ImportError as e:
            pytest.fail(f"无法导入 {path}: {e}")


def test_no_v1_import_paths_remain():
    """codebase 0 处 v1 import path (emotion_spirit.X 而非 emotion_spirit.{L0|L1|L2|L3}.X 或 emotion_spirit.layer 或 emotion_spirit._version 或 emotion_spirit._v1_compat)。

    用 AST 解析: 对每个 from-import 跟 import 节点, 检查 module 跟 name 字段
    是否还是 v1 形式 (例如 emotion_spirit.superego 而不是 emotion_spirit.regulation.superego)。
    """
    import ast
    # v1 形式: emotion_spirit.<module_name> (没有 layer 子包)
    # v2 合法: emotion_spirit.{core|memory|regulation|output}.<module_name>
    #         emotion_spirit.layer / emotion_spirit._version / emotion_spirit._v1_compat
    #         emotion_spirit.store (root helper)
    v2_layer_prefixes = ("emotion_spirit.core.", "emotion_spirit.memory.",
                         "emotion_spirit.regulation.", "emotion_spirit.output.")
    v2_root_modules = {"emotion_spirit", "emotion_spirit.layer",
                       "emotion_spirit._version", "emotion_spirit._v1_compat",
                       "emotion_spirit.store",
                       # sub-package roots 本身也是 v2 合法路径 (from X.layer import Y)
                       "emotion_spirit.core", "emotion_spirit.memory",
                       "emotion_spirit.regulation", "emotion_spirit.output"}

    def is_v2_path(s: str) -> bool:
        if s in v2_root_modules:
            return True
        return any(s.startswith(p) for p in v2_layer_prefixes)

    found = []
    for py_file in REPO_ROOT.rglob("*.py"):
        if "/__pycache__/" in str(py_file) or "/.git/" in str(py_file):
            continue
        if "tmp_" in py_file.name or "migrate_v1" in py_file.name:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name.startswith("emotion_spirit") and not is_v2_path(name):
                        found.append(f"{py_file.name}: import {name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("emotion_spirit"):
                    if not is_v2_path(node.module):
                        # e.g. "from emotion_spirit.superego import X" → node.module='emotion_spirit.superego'
                        # 也处理 level > 0 (from .X / from ..X)
                        if node.level == 0:
                            found.append(f"{py_file.name}: from {node.module} import ...")
    assert found == [], f"发现 v1 import path: {found[:5]}"


def test_layer_dependency_no_reverse():
    """L1 不 import L2/L3, L2 不 import L3。4 层依赖方向 L0<-L1<-L2<-L3 严格单向。"""
    reverse_violations = []
    forbidden_combinations = [
        ("memory", ["regulation", "output"]),
        ("regulation", ["output"]),
    ]
    for layer_dir, forbidden_layers in forbidden_combinations:
        layer_path = EMOTION_SPIRIT_DIR / layer_dir
        for py_file in layer_path.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            text = py_file.read_text(encoding="utf-8")
            for forbidden in forbidden_layers:
                # 检查 import emotion_spirit.forbidden 或 from emotion_spirit.forbidden
                if f"emotion_spirit.{forbidden}" in text:
                    reverse_violations.append(f"{py_file.name} imports from {forbidden}")
    assert reverse_violations == [], f"反向依赖: {reverse_violations}"
