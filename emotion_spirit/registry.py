"""emotion_spirit 模块注册表 + DI 工厂 (Phase B6.x, P3-7 L2)。

模块自注册, build() 按依赖图自动初始化, 加新模块不动 main.py。

B6.x 增强:
- ModuleSpec 加 `param_wire` / `config_keys` / `provides_classes` 3 字段
- `register()` 装饰器签名接受新参数
- `build()` 用 `inspect.signature` + `param_wire` 自动 wire,
  `config_keys` 从 config["params"] 注入,
  multi-instance 拆 sub (e.g. superego 4 sub 返回 dict)
"""
from __future__ import annotations
import inspect
from dataclasses import dataclass, field
from typing import Type, Callable, Any


@dataclass
class ModuleSpec:
    """模块规格: name + provides + depends_on + class + 装配配置。"""

    name: str
    provides: list[str]
    depends_on: list[str]
    module_class: Type
    # 新 B6.x 字段
    param_wire: dict[str, str] = field(default_factory=dict)
    """dep_name → __init__ 形参名 显式 mapping。
    默认: dep_name == 形参名, 不用 wire; 不一致时显式指定。"""

    config_keys: set[str] = field(default_factory=set)
    """哪些 kwarg 必须从 config["params"] 注入 (不在 depends_on)。"""

    provides_classes: dict[str, Type] | None = None
    """multi-instance: e.g. superego 4 sub-classes。
    设置后 build() 走 multi-instance 分支, 返回 dict[cls_name, instance]。"""


class ModuleRegistry:
    """全局模块注册表 (单例)。"""

    _registry: dict[str, ModuleSpec] = {}

    @classmethod
    def register(
        cls,
        *,
        name: str,
        provides: list[str],
        depends_on: list[str],
        param_wire: dict[str, str] | None = None,
        config_keys: set[str] | None = None,
        provides_classes: dict[str, Type] | None = None,
    ) -> Callable:
        """装饰器: 把模块类注册到全局 registry。

        用法:
            @ModuleRegistry.register(name="memory_pool", provides=["MemoryPool"], depends_on=[])
            class MemoryPool:
                def __init__(self):
                    ...

            @ModuleRegistry.register(
                name="buffer_signals",
                provides=["BufferSignals"],
                depends_on=["memory_pool"],
                param_wire={"memory_pool": "pool"},  # dep name → 形参名
                config_keys={"user_id"},  # 从 config["params"] 注入
            )
            class BufferSignals:
                def __init__(self, pool: MemoryPool, user_id: str = "<global>") -> None: ...
        """
        def decorator(module_class: Type) -> Type:
            cls._registry[name] = ModuleSpec(
                name=name,
                provides=provides,
                depends_on=depends_on,
                module_class=module_class,
                param_wire=dict(param_wire or {}),
                config_keys=set(config_keys or ()),
                provides_classes=provides_classes,
            )
            return module_class
        return decorator

    @classmethod
    def get_all(cls) -> dict[str, ModuleSpec]:
        return dict(cls._registry)

    @classmethod
    def reset(cls) -> None:
        """测试用: 清空 registry。"""
        cls._registry.clear()


def register(
    *,
    name: str,
    provides: list[str],
    depends_on: list[str],
    param_wire: dict[str, str] | None = None,
    config_keys: set[str] | None = None,
    provides_classes: dict[str, Type] | None = None,
) -> Callable:
    """ModuleRegistry.register 的便捷别名。"""
    return ModuleRegistry.register(
        name=name,
        provides=provides,
        depends_on=depends_on,
        param_wire=param_wire,
        config_keys=config_keys,
        provides_classes=provides_classes,
    )


def _dep_ready(dep: str, instances: dict[str, object]) -> bool:
    """dep 可能是 'xxx' 或 'xxx.yyy' (multi-instance sub)."""
    if "." in dep:
        base, sub = dep.split(".", 1)
        return base in instances and sub in instances[base]
    return dep in instances


def _check_dep_in_registry_or_instances(
    dep: str,
    instances: dict[str, object],
    dry_run: bool,
) -> bool:
    """dry_run 时, dep ready 检查走 registry + instances 真值。
    非 dry_run 时, 走 instances (build 顺序)."""
    if dry_run:
        # dry_run: 检查 dep 是否在 registry 中声明
        if "." in dep:
            base, sub = dep.split(".", 1)
            base_spec = ModuleRegistry.get_all().get(base)
            if base_spec is None:
                return False
            # 检查 sub 是否在 provides_classes 或 provides (class name 形式)
            if base_spec.provides_classes and sub in base_spec.provides_classes:
                return True
            return sub in base_spec.provides
        return dep in ModuleRegistry.get_all()
    return _dep_ready(dep, instances)


def _get_dep_value(dep: str, instances: dict[str, object]) -> object:
    """从 instances 拿 dep 值, 支持 'xxx.yyy' sub 语法。"""
    if "." in dep:
        base, sub = dep.split(".", 1)
        return instances[base][sub]
    return instances[dep]


def build(config: dict, *, dry_run: bool = False) -> dict[str, object]:
    """按依赖图自动初始化所有 enabled 模块。

    Args:
        config: {
            "modules": {"name": {"enabled": bool, "params": {...}}},  # params 透传给 module
            "params": {"data_dir": ..., "persona_id": ..., "labels": ..., "llm": ..., "gossip_tendency": ...}
        }
        dry_run: True = 只检查依赖图 (CI 用)

    Returns:
        dict[module_name, instance_or_sub_dict]
        - 普通模块: instance
        - multi-instance (e.g. superego): dict[cls_name, instance]

    Raises:
        RuntimeError: 循环依赖 / 缺失依赖 / 形参不匹配
    """
    modules_cfg = config.get("modules", {})
    params = config.get("params", {})
    pending = [
        (name, spec) for name, spec in ModuleRegistry.get_all().items()
        if modules_cfg.get(name, {}).get("enabled", True)
    ]

    instances: dict[str, object] = {}

    while pending:
        progress = False
        for name, spec in list(pending):
            if not all(_check_dep_in_registry_or_instances(dep, instances, dry_run) for dep in spec.depends_on):
                continue
            if not dry_run:
                instances[name] = _build_one(spec, instances, params)
            pending.remove((name, spec))
            progress = True
        if not progress:
            unresolved = [n for n, _ in pending]
            raise RuntimeError(f"循环依赖或缺失依赖: {unresolved}")

    return instances


def _build_one(
    spec: ModuleSpec,
    instances: dict[str, object],
    params: dict[str, Any],
) -> object:
    """构建 1 个 module instance, 处理 multi-instance 拆 sub.

    装配逻辑:
    1. 用 inspect.signature 拿 __init__ 形参列表
    2. 遍历 spec.depends_on:
       - 拿 dep value (支持 "xxx.yyy" sub 语法)
       - 拿 param_name: spec.param_wire 显式 mapping, 默认 dep_spec.split(".")[-1]
       - 注入 kwargs
    3. 遍历 spec.config_keys, 从 params 注入
    4. multi-instance: 4 sub 一起创 (返回 dict[cls_name, instance])
    """
    sig = inspect.signature(spec.module_class.__init__)
    param_names = set(sig.parameters) - {"self", "args", "kwargs"}
    kwargs: dict[str, object] = {}

    # 1. wire deps → __init__ 形参 (param_wire 显式 mapping, 默认 dep 末段)
    for dep_spec in spec.depends_on:
        dep_value = _get_dep_value(dep_spec, instances)
        param_name = spec.param_wire.get(dep_spec, dep_spec.split(".")[-1])
        if param_name in param_names:
            kwargs[param_name] = dep_value
        else:
            raise RuntimeError(
                f"{spec.name}.__init__ 缺形参 {param_name!r} (dep={dep_spec!r})"
            )

    # 2. config_keys 注入 (param_wire 同样适用: config_key → __init__ 形参名)
    # B6.x.x I2: 形参不匹配时 hard error (RuntimeError), 不再静默塞 kwargs
    # 避免下游 TypeError 在最远点 fail, 难以定位 spec name + config_key。
    for key in spec.config_keys:
        if key in params:
            param_name = spec.param_wire.get(key, key)
            if spec.provides_classes:
                # multi-instance: 至少 1 个 sub 的 __init__ 形参含 param_name 才放行
                sub_param_sets = [
                    set(inspect.signature(cls.__init__).parameters) - {"self", "args", "kwargs"}
                    for cls in spec.provides_classes.values()
                ]
                if not any(param_name in sps for sps in sub_param_sets):
                    raise RuntimeError(
                        f"{spec.name}.config_key {key!r} (形参 {param_name!r}) "
                        f"不在任一 sub-class __init__ 形参"
                    )
            else:
                # 单 instance: __init__ 形参必须含 param_name
                if param_name not in param_names:
                    raise RuntimeError(
                        f"{spec.name}.config_key {key!r} (形参 {param_name!r}) "
                        f"不在 {spec.module_class.__name__}.__init__ 形参"
                    )
            kwargs[param_name] = params[key]

    # 3. multi-instance: 4 sub 一起创 (filter kwargs per sub-class __init__ signature)
    if spec.provides_classes:
        out: dict[str, object] = {}
        for cls_name, cls_obj in spec.provides_classes.items():
            sub_sig = inspect.signature(cls_obj.__init__)
            sub_params = set(sub_sig.parameters) - {"self", "args", "kwargs"}
            sub_kwargs = {k: v for k, v in kwargs.items() if k in sub_params}
            out[cls_name] = cls_obj(**sub_kwargs)
        return out
    return spec.module_class(**kwargs)
