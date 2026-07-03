"""AST 静态检查: personality shape 契约 (Bug 14 防回归)."""
import ast
from pathlib import Path


def test_no_format_string_on_personality_values():
    """AST 检查: 禁止 `f"{k}={v:.1f}" for k, v in personality.items()` 模式

    已知历史违规: life_simulator.py:289, :580 (Bug 14, PR3 T9 修)
    修法: 先用 _flatten_personality() 拍平.
    """
    src = Path("emotion_spirit/regulation/life_simulator.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
            continue
        elt = node.elt
        # elt 必须是 JoinedStr (f-string)
        if not isinstance(elt, ast.JoinedStr):
            continue
        # 检查是否有 format_spec (:.1f 之类)
        has_format_spec = False
        for v in ast.walk(elt):
            if isinstance(v, ast.FormattedValue) and v.format_spec is not None:
                has_format_spec = True
                break
        if not has_format_spec:
            continue
        # iter 是 personality.items() (comprehension 的 generators 列表)
        found = False
        for gen in node.generators:
            if not isinstance(gen.iter, ast.Call):
                continue
            if not (isinstance(gen.iter.func, ast.Attribute)
                    and gen.iter.func.attr == "items"):
                continue
            if not (isinstance(gen.iter.func.value, ast.Name)
                    and gen.iter.func.value.id == "personality"):
                continue
            found = True
            break
        if not found:
            continue
        pytest.fail(
            f"line {elt.lineno}: `personality.items()` 直接 format 是 Bug 14 模式, "
            f"必须先用 _flatten_personality() 拍平"
        )


def test_get_current_personality_dict_type_hint_realistic():
    """main.py 中 _get_current_personality_dict 返回注解应真实反映嵌套 shape."""
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_get_current_personality_dict":
            if node.returns is None:
                continue
            ret = ast.unparse(node.returns)
            # 接受 dict[str, dict[str, float]] 或 dict[str, Any] (真实契约)
            assert ("dict[str, dict[str, float]]" in ret
                    or "dict[str, dict]" in ret
                    or "dict[str, Any]" in ret), (
                f"line {node.lineno} type hint 应真实反映嵌套 shape, 当前: {ret}"
            )
