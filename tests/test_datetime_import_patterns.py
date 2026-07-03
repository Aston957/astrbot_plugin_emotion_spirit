"""AST 静态检查: datetime import 不遮蔽 (Bug 13 防回归)."""
import ast
from pathlib import Path


def test_no_datetime_class_method_confusion():
    """main.py 不能调 datetime.date / datetime.time (类方法遮蔽)

    main.py 有 `from datetime import date, datetime, timezone, timedelta`.
    这里 `datetime` 是类 datetime.datetime, 不是模块.
    写 `datetime.date.today()` 会被解析为 `类.实例方法` → AttributeError.
    Bug 13 修: 改用 `date.today()` / `date.fromtimestamp()` 等.
    """
    src = Path("main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    has_datetime_class = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            if any(a.name == "datetime" for a in node.names):
                has_datetime_class = True
                break

    if not has_datetime_class:
        pytest.skip("main.py 不存在 `from datetime import datetime`")

    forbidden = {"date", "time", "tzinfo"}
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "datetime":
                if node.attr in forbidden:
                    violations.append(f"line {node.lineno}: datetime.{node.attr}")

    assert not violations, f"datetime 类方法遮蔽违规: {violations}"
