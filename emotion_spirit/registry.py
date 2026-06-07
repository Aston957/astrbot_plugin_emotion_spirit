"""emotion_spirit 模块注册表 + DI 工厂 (Phase B, P3-7 L2)。

模块自注册, build() 按依赖图自动初始化, 加新模块不动 main.py。
"""
from __future__ import annotations
from typing import Type, Callable


class ModuleSpec:
    """模块规格: name + provides + depends_on + class。"""

    def __init__(self, name: str, provides: list[str], depends_on: list[str], module_class: Type):
        self.name = name
        self.provides = provides
        self.depends_on = depends_on
        self.module_class = module_class


class ModuleRegistry:
    """全局模块注册表 (单例)。"""

    _registry: dict[str, ModuleSpec] = {}

    @classmethod
    def register(cls, *, name: str, provides: list[str], depends_on: list[str]) -> Callable:
        """装饰器: 把模块类注册到全局 registry。

        用法:
            @ModuleRegistry.register(name="memory_pool", provides=["MemoryPool"], depends_on=[])
            class MemoryPool:
                def __init__(self):
                    ...
        """
        def decorator(module_class: Type) -> Type:
            cls._registry[name] = ModuleSpec(name, provides, depends_on, module_class)
            return module_class
        return decorator

    @classmethod
    def get_all(cls) -> dict[str, ModuleSpec]:
        return dict(cls._registry)

    @classmethod
    def reset(cls) -> None:
        """测试用: 清空 registry。"""
        cls._registry.clear()


def register(*, name: str, provides: list[str], depends_on: list[str]) -> Callable:
    """ModuleRegistry.register 的便捷别名。"""
    return ModuleRegistry.register(name=name, provides=provides, depends_on=depends_on)


def build(config: dict, *, dry_run: bool = False) -> dict[str, object]:
    """按依赖图自动初始化所有 enabled 模块。

    Args:
        config: 形如 {"modules": {"name": {"enabled": bool, "params": {...}}}}
        dry_run: True = 只检查依赖图, 不真正 init (CI 用)

    Returns:
        dict[module_name, instance] (dry_run=True 时为空 dict)

    Raises:
        RuntimeError: 循环依赖或缺失依赖
    """
    modules_cfg = config.get("modules", {})
    pending = [
        (name, spec) for name, spec in ModuleRegistry.get_all().items()
        if modules_cfg.get(name, {}).get("enabled", True)
    ]

    instances: dict[str, object] = {}

    while pending:
        progress = False
        for name, spec in list(pending):
            if all(dep in instances for dep in spec.depends_on):
                if not dry_run:
                    kwargs = {dep_name: instances[dep_name] for dep_name in spec.depends_on}
                    kwargs.update(modules_cfg.get(name, {}).get("params", {}))
                    instances[name] = spec.module_class(**kwargs)
                # dry_run: 只检查依赖图, 不实例化, 不入 dict
                pending.remove((name, spec))
                progress = True
        if not progress:
            unresolved = [n for n, _ in pending]
            raise RuntimeError(f"循环依赖或缺失依赖: {unresolved}")

    return instances
