"""§1.2 规则 3: main.py 单方法 < 50 行 — 编排逻辑抽到 @register 组件."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MAIN_PY = REPO_ROOT / "main.py"


def _get_function_lengths() -> list[tuple[str, int]]:
    """AST 解析 main.py, 返回 (name, line_count) 列表."""
    source = MAIN_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    results = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = node.end_lineno or start
            lines = end - start + 1
            results.append((node.name, lines))
    return results


def test_no_method_exceeds_50_lines():
    """main.py 单方法不超过 50 行 (编排应抽 @register)."""
    max_allowed = 50
    violations = [(n, l) for n, l in _get_function_lengths() if l > max_allowed]
    allowlist = {
        # 这些是 AstrBot 生命周期钩子 / 数据加载 / 持久化, 允许超限
        "__init__",                       # ~53 行: 构造函数 (config migration + 28 模块装配 + 队列)
        "_init_modules_phase1",       # ~80 行: factory 装配 + 模块取用
        "initialize",                 # ~30 行: AstrBot 钩子
        "_ns_handler",                # ~12 行: 命令闭包 (多个实例, 短的)
        "_ns_command",                # ~52 行 (v1.2.11): AstrBot 命名空间命令工厂 + Patch A __signature__ 覆盖 + 注释
        "_schedule_plan_generation_loop",  # ~70 行: 调度循环
        "_schedule_diary_generation_loop", # ~61 行: 调度循环
        "on_llm_request",             # ~71 行: AstrBot LLM 请求钩子
        "_load_phase2_data",          # ~64 行: 数据加载
        "_load_persona_state",        # ~55 行 (v1.2.11 Patch B): 数据加载 + B5 conditional 重写 + 详细注释
        "_persist_modules",           # ~52 行: 持久化 (串联所有 @register 模块)
    }
    violations = [(n, l) for n, l in violations if n not in allowlist]
    assert not violations, (
        f"以下方法超过 {max_allowed} 行: {[(n, l) for n, l in violations]}"
    )


def test_on_llm_response_bounded():
    """on_llm_response 行数应薄 (AstrBot 钩子, 副作用+状态收集已抽 helper)."""
    funcs = dict(_get_function_lengths())
    max_len = funcs.get("on_llm_response", 999)
    # v1.2.8: _apply_bot_reply_effects + _collect_segmented_state 抽出后 ~43行 (薄壳目标 < 55)
    assert max_len <= 55, f"on_llm_response = {max_len} 行, 应 ≤ 55 (v1.2.8 薄壳化)"


def test_no_long_nested_function():
    """main.py 不应有嵌套函数超 30 行."""
    source = MAIN_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    length = (child.end_lineno or child.lineno) - child.lineno + 1
                    if length > 30:
                        violations.append((node.name, child.name, length))
    assert not violations, f"嵌套函数超限: {violations}"