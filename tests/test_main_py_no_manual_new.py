"""AST scan: list all manual new in main.py (v1.2.5 PR3 T3+T4 audit)

v1.2.5 PR3 §6 清债:
- 12 个 main.py 手 new → 评估 @register 状态 → 处理
- 评估分类: A (已注册可改) / B (需注册) / C (self 注入 v1.3)
- AST 扫描 + 状态报告 (本次 commit) + 后续 Task 4/5 处理

不抛 assert failure (除 PR3 Task 2 _reset_superego_modules AST 检查), 生成评估报告.
"""
import ast
import pytest
from pathlib import Path


def test_scan_main_py_manual_new_patterns():
    """列出 main.py 所有 self._xxx = ClassName(...) 模式

    输出格式: (line_number, attribute_name, class_name)
    用于 v1.2.5 PR3 T3+T4 评估 (哪些已 @register, 哪些没)
    """
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Attribute):
            continue
        # target.value 必须是 self
        if not (isinstance(target.value, ast.Name) and target.value.id == "self"):
            continue
        # value 必须是 Call
        if not isinstance(node.value, ast.Call):
            continue
        # call.func 必须是 Name (大写类)
        if isinstance(node.value.func, ast.Name):
            class_name = node.value.func.id
            if class_name[0].isupper():
                findings.append((node.lineno, target.attr, class_name))

    # 输出评估报告 (INFO log, 不失败)
    print("\n=== main.py manual new patterns ===")
    for line, attr, cls in findings:
        print(f"  line {line}: self.{attr} = {cls}(...)")
    print(f"\nTotal: {len(findings)} manual new")

    # 必须找到至少 1 个 (即 PR3 评估目标)
    assert len(findings) > 0


def test_no_manual_new_for_superego_in_reset():
    """AST 检查: _reset_superego_modules 不能有 ConscienceTracker() 等手 new (PR3 T2)"""
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    forbidden_classes = {"ConscienceTracker", "ValueAlignment", "IdealSelf", "ValueResistance", "SuperegoGuard"}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_reset_superego_modules":
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    if child.func.id in forbidden_classes:
                        # 检查是否被直接赋给 self._xxx
                        def find_containing_assign(needle, root):
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
                                        f"self.{target.attr} = {child.func.id}() 直赋"
                                    )
