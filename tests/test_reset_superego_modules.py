"""Tests for _reset_superego_modules (v1.2.5 PR3 T2, 修双轨 bug)

T2 关键洞察 (双轨 bug):
- 初始化: main.py:271-272 用 self._modules["superego"]["conscience"] (走 factory) ✅
- 重置: main.py:698-718 手 new 5 个 sub ❌
- 后果: 重置后 self._conscience 指向新对象, 但 self._modules["superego"]["conscience"] 仍指旧对象
- 修法: 重置时直接重建 self._modules["superego"] 子字典, 不动 main.py 装配代码

注: 不 import main.py, 避免 conftest mock 不完整导致 ModuleNotFoundError.
    用 AST 静态分析 + 源码字符串检查更可靠.
"""
import ast
import pytest
from pathlib import Path


def _get_reset_superego_source() -> str:
    """提取 _reset_superego_modules 函数的源码片段."""
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_reset_superego_modules":
            # 用 ast.get_source_segment 拿源码
            return ast.get_source_segment(src, node)
    pytest.fail("_reset_superego_modules not found in main.py")


def test_reset_superego_modules_no_manual_new_in_source():
    """AST 检查: main.py:_reset_superego_modules 不能有 `self._xxx = ClassName(...)` 直赋 (防双轨)

    handbook §1.2 强拦, 防双轨 bug 回归.
    允许模式: `local_var = ClassName(...)` (再装到 _modules dict) — 修法所需.
    禁模式: `self._conscience = ConscienceTracker()` (直赋 self, 跟 _modules 不一致).
    """
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    forbidden_classes = {"ConscienceTracker", "ValueAlignment", "IdealSelf", "ValueResistance", "SuperegoGuard"}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_reset_superego_modules":
            for child in ast.walk(node):
                if not (isinstance(child, ast.Call) and isinstance(child.func, ast.Name)):
                    continue
                if child.func.id not in forbidden_classes:
                    continue
                # 检查这个 Call 是否被直接赋给 self._xxx
                # 模式: self._xxx = ClassName(...)
                # 不算违规: local_var = ClassName(...) (后面再装 dict)
                # 用 ast.iter_child_nodes 找父节点 (更可靠)
                def find_containing_assign(needle, root):
                    """找直接包含 needle 的 Assign 节点 (BFS)."""
                    from collections import deque
                    queue = deque([root])
                    while queue:
                        cur = queue.popleft()
                        if isinstance(cur, ast.Assign) and cur.value is needle:
                            return cur
                        for c in ast.iter_child_nodes(cur):
                            queue.append(c)
                    return None
                parent = find_containing_assign(child, node)
                if parent is not None:
                    for target in parent.targets:
                        if (isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"):
                            pytest.fail(
                                f"handbook §1.2 违规: line {parent.lineno} _reset_superego_modules 内 "
                                f"self.{target.attr} = {child.func.id}(...) 直赋 (会跟 _modules['superego'] 不一致). "
                                f"应: local_var = {child.func.id}(...) → 装到 self._modules['superego']['{target.attr}'] + "
                                f"self.{target.attr} = local_var (身份一致)"
                            )


def test_reset_superego_modules_imports_conscience_tracker():
    """_reset_superego_modules 必须 import ConscienceTracker (修 NameError latent bug)

    Pre-existing bug: 原代码用 ConscienceTracker() 但没 import, 调用时 NameError.
    修法: 在函数体内 import from emotion_spirit.regulation.superego.conscience import ConscienceTracker
    """
    func_src = _get_reset_superego_source()
    assert "from emotion_spirit.regulation.superego.conscience import ConscienceTracker" in func_src, (
        "_reset_superego_modules 必须显式 import ConscienceTracker (防 NameError)"
    )


def test_reset_superego_modules_assigns_to_modules_dict():
    """_reset_superego_modules 必须重建 self._modules["superego"] 子字典 (双轨消核心)

    AST 检查: 函数体内有 `self._modules["superego"] = {...}` 模式
    """
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_reset_superego_modules":
            for child in ast.walk(node):
                # 检查 self._modules["superego"] = {...} 赋值
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if (isinstance(target, ast.Subscript)
                            and isinstance(target.value, ast.Attribute)
                            and target.value.attr == "_modules"
                            and isinstance(target.value.value, ast.Name)
                            and target.value.value.id == "self"
                            and isinstance(target.slice, ast.Constant)
                            and target.slice.value == "superego"):
                            return  # 找到, 测试通过
            pytest.fail(
                "handbook §1.2 + 双轨消要求: _reset_superego_modules 必须重建 "
                "self._modules['superego'] 子字典 (单点重建, 同步 self._xxx 引用)"
            )


def test_reset_superego_modules_identity_pattern_in_source():
    """源码检查: self._xxx 必须从 self._modules["superego"][...] 同步, 保持身份一致"""
    func_src = _get_reset_superego_source()
    # 必须有 self._conscience = ... 模式
    for attr in ["_conscience", "_alignment", "_ideal", "_value_resistance", "_superego_guard"]:
        # 简单字符串检查: 行内含 "self._conscience ="
        assert f"self.{attr} =" in func_src, (
            f"_reset_superego_modules 必须重置 self.{attr} (跟新 _modules['superego'] 同步)"
        )
