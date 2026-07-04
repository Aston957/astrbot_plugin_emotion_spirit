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


# === v1.2.5 PR3 Task 4+5: 已处理类不得回退为手 new ===

def test_no_manual_new_for_t4_classes():
    """T4 修后, main.py 不应有 9 个已处理类手 new"""
    t4_classes = {
        "PatternExtractor", "BufferSignals", "ShadowDetector",
        "LifeSimulator", "PersonalityDrift", "PredictiveSentinel",
        "NarrativeIdentity", "Counterfactual", "PromptInjector",
    }

    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Attribute):
            continue
        if not (isinstance(target.value, ast.Name) and target.value.id == "self"):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        if isinstance(node.value.func, ast.Name) and node.value.func.id in t4_classes:
            violations.append(f"line {node.lineno}: self.{target.attr} = {node.value.func.id}(...)")

    assert not violations, f"T4 回退为手 new: {violations}"


def test_public_api_is_facade_hand_new():
    """main.py PublicAPI 走手 new (facade 吃整个 modules dict, @register 不适配).

    Bug-C (v1.2.10): v1.2.5 PR3 T3 尝试 @register 但漏加装饰器 → KeyError.
    即使加 @register 也会 TypeError (factory 只注入单个 dep, 无路径传 instances dict).
    回退手 new, 同 CommandImpl/SurfaceHandler/LifeAgent.
    见 registry._build_one (registry.py:205-271) — depends_on 单 dep 注入模型不适用.
    """
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Attribute):
            continue
        target = node.targets[0]
        if not (isinstance(target.value, ast.Name) and target.value.id == "self"):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        if isinstance(node.value.func, ast.Name) and node.value.func.id == "PublicAPI":
            found = True
            # PublicAPI 手 new 是故意的 (facade 模式), 不失败.
            # 参数: PublicAPI(self._modules) — 传整个 modules dict
            continue  # OK, allowed

    # 必须存在 (确保我们没有误删 hand-new)
    assert found, "main.py 缺少 PublicAPI(self._modules) 手 new (Bug-C 必须存在)"


def test_initialize_no_superego_manual_new():
    """initialize() 不应有 ValueAlignment/IdealSelf/ValueResistance/SuperegoGuard 手 new (T2 扩展)"""
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    forbidden = {"ValueAlignment", "IdealSelf", "ValueResistance", "SuperegoGuard"}

    for node in ast.walk(tree):
        if not (isinstance(node, ast.AsyncFunctionDef) and node.name == "initialize"):
            continue
        for child in ast.walk(node):
            if not (isinstance(child, ast.Call) and isinstance(child.func, ast.Name)):
                continue
            if child.func.id in forbidden:
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
                                f"line {parent.lineno} initialize() 内 "
                                f"self.{target.attr} = {child.func.id}() 手 new (T2 扩展未修)"
                            )


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
