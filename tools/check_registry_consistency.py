"""Static scan: 验证 @register 装饰器声明的 depends_on + param_wire 跟 __init__ 形参一致 (B6.x P0)。

扫所有 emotion_spirit/*.py, 验证:
1. @register 的 depends_on 列表里 dep name 跟 __init__ 形参名能映射 (通过 param_wire 或同名)
2. config_keys 列表里 config key 跟 __init__ 形参名能映射 (通过 param_wire 或同名)
3. multi-instance: provides_classes 都在 __init__ 形参名集合中

不一致时 exit 1, 输出 diff。
"""
import re
import sys
import inspect
import importlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
EMOTION_SPIRIT_DIR = ROOT / "emotion_spirit"
sys.path.insert(0, str(ROOT))


def _find_register_decorators(source: str) -> list[tuple[int, str, dict[str, Any]]]:
    """解析 @register(...) 装饰器, 返回 (line_no, class_name, kwargs) 列表。
    """
    # 简化版: 用 ast 解析
    import ast
    results: list[tuple[int, str, dict[str, Any]]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return results

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not node.decorator_list:
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func_name = None
            if isinstance(dec.func, ast.Name):
                func_name = dec.func.id
            elif isinstance(dec.func, ast.Attribute):
                func_name = dec.func.attr
            if func_name != "register":
                continue
            kwargs = {}
            for kw in dec.keywords:
                key = kw.arg
                if key is None:
                    continue
                value = ast.literal_eval(kw.value)
                kwargs[key] = value
            results.append((node.lineno, node.name, kwargs))
    return results


def _get_init_param_names(class_obj: type) -> set[str]:
    """拿 __init__ 形参名集合 (excluding self)."""
    try:
        sig = inspect.signature(class_obj.__init__)
    except (TypeError, ValueError):
        return set()
    return set(sig.parameters) - {"self", "args", "kwargs"}


def _check_module_consistency(
    module_name: str,
    spec_name: str,
    spec_kwargs: dict[str, Any],
    cls_obj: type,
) -> list[str]:
    """验证 1 个 @register 模块的 spec 跟 __init__ 一致。"""
    errors: list[str] = []
    init_params = _get_init_param_names(cls_obj)
    depends_on: list[str] = spec_kwargs.get("depends_on", [])
    param_wire: dict[str, str] = spec_kwargs.get("param_wire", {})
    config_keys: set[str] = set(spec_kwargs.get("config_keys", []))
    provides_classes: dict[str, Any] | None = spec_kwargs.get("provides_classes")

    # 1. deps: 验证 param_wire 后能命中 __init__ 形参
    for dep in depends_on:
        if "." in dep:
            # multi-instance sub: e.g. "superego.alignment" → 默认 param_name = "alignment"
            base, sub = dep.split(".", 1)
            param_name = param_wire.get(dep, sub)
        else:
            param_name = param_wire.get(dep, dep)
        if param_name not in init_params:
            errors.append(
                f"{module_name}.{spec_name}: dep {dep!r} → param {param_name!r} "
                f"not in __init__ params {sorted(init_params)}"
            )

    # 2. config_keys: 验证 param_wire 后能命中 __init__ 形参
    for key in config_keys:
        param_name = param_wire.get(key, key)
        if param_name not in init_params:
            # 在 multi-instance 下, param 可能属于 sub-class, 不是 module_class
            # 这种情况不算 error
            if not provides_classes:
                errors.append(
                    f"{module_name}.{spec_name}: config_key {key!r} → param {param_name!r} "
                    f"not in __init__ params {sorted(init_params)}"
                )

    # 3. multi-instance: 验证 provides_classes 在 __init__ 形参名集合中
    if provides_classes:
        for cls_name, sub_cls in provides_classes.items():
            sub_params = _get_init_param_names(sub_cls)
            for dep in depends_on:
                if "." in dep:
                    base, sub = dep.split(".", 1)
                    # sub 是当前 module 的 sub, param 应该在 sub 的形参中
                    if base == spec_name:
                        param_name = param_wire.get(dep, sub)
                        if param_name not in sub_params:
                            errors.append(
                                f"{module_name}.{spec_name}.{cls_name}: dep {dep!r} "
                                f"→ param {param_name!r} not in __init__ params {sorted(sub_params)}"
                            )
            # NOTE: config_keys 共享给所有 sub, build() 会按 sub_params 过滤, 故不报 error

    return errors


def main() -> int:
    import emotion_spirit  # noqa: F401  # 触发 28 模块 @register

    from emotion_spirit.registry import ModuleRegistry, ModuleSpec

    errors: list[str] = []

    for name, spec in ModuleRegistry.get_all().items():
        module_name = spec.module_class.__module__
        try:
            errors.extend(_check_module_consistency(
                module_name, name,
                {
                    "depends_on": spec.depends_on,
                    "param_wire": spec.param_wire,
                    "config_keys": spec.config_keys,
                    "provides_classes": spec.provides_classes,
                },
                spec.module_class,
            ))
        except Exception as e:
            errors.append(f"{module_name}.{name}: scan failed: {e}")

    if errors:
        print(f"[FAIL] Registry consistency check found {len(errors)} issues:")
        for err in errors[:20]:
            print(f"  - {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        return 1

    print(f"[PASS] Registry consistency check OK ({len(ModuleRegistry.get_all())} modules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
