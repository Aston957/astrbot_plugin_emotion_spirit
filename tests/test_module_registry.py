"""Tests for ModuleRegistry + DI (Phase B, P3-7 L2)."""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import emotion_spirit  # noqa: F401  # 触发 28 模块 @register
from emotion_spirit.registry import ModuleRegistry


@pytest.fixture(autouse=True)
def isolate_registry():
    """每个 test 前保存 28 真实 modules, 清空 registry; test 后恢复 28 真实 modules。

    这样 test_module_registry.py 测试可以自由 @register 新 class, 不受 28 真实模块影响;
    test_registry_mismatch_fix.py 后续测试仍能看到完整的 28 真实模块。
    """
    saved = dict(ModuleRegistry.get_all())
    ModuleRegistry.reset()
    yield
    # 恢复 28 真实 modules, 清掉 test 加入的临时 classes
    ModuleRegistry._registry.clear()
    for name, spec in saved.items():
        ModuleRegistry._registry[name] = spec


def test_module_registry_register_decorator():
    """@register 装饰器把类注册到全局 registry。"""
    from emotion_spirit.registry import ModuleRegistry, register

    @register(name="test_mod", provides=["TestMod"], depends_on=[])
    class TestMod:
        def __init__(self):
            self.value = 42

    assert "test_mod" in ModuleRegistry.get_all()
    spec = ModuleRegistry.get_all()["test_mod"]
    assert spec.provides == ["TestMod"]
    assert spec.depends_on == []


def test_build_resolves_simple_dependency():
    """build() 按依赖图 init 模块。"""
    from emotion_spirit.registry import ModuleRegistry, register, build

    @register(name="a", provides=["A"], depends_on=[])
    class A:
        def __init__(self):
            self.x = 1

    @register(name="b", provides=["B"], depends_on=["a"])
    class B:
        def __init__(self, a):
            self.a = a
            self.y = 2

    config = {"modules": {"a": {"enabled": True}, "b": {"enabled": True}}}
    instances = build(config)

    assert "a" in instances
    assert "b" in instances
    assert instances["b"].a is instances["a"]


def test_build_disabled_module_skipped():
    """config.enabled=False 跳过该模块。"""
    from emotion_spirit.registry import ModuleRegistry, register, build

    @register(name="a", provides=["A"], depends_on=[])
    class A:
        def __init__(self):
            pass

    @register(name="b", provides=["B"], depends_on=["a"])
    class B:
        def __init__(self, a):
            pass

    config = {"modules": {"a": {"enabled": True}, "b": {"enabled": False}}}
    instances = build(config)

    assert "a" in instances
    assert "b" not in instances


def test_build_circular_dependency_raises():
    """循环依赖应抛 RuntimeError。"""
    from emotion_spirit.registry import ModuleRegistry, register, build

    @register(name="a", provides=["A"], depends_on=["B"])
    class A:
        def __init__(self, b): pass

    @register(name="b", provides=["B"], depends_on=["A"])
    class B:
        def __init__(self, a): pass

    config = {"modules": {"a": {"enabled": True}, "b": {"enabled": True}}}
    import pytest
    with pytest.raises(RuntimeError, match="循环依赖"):
        build(config)


def test_build_dry_run_does_not_initialize():
    """dry_run=True 只检查依赖图, 不真正 init。"""
    from emotion_spirit.registry import ModuleRegistry, register, build

    @register(name="a", provides=["A"], depends_on=[])
    class A:
        def __init__(self):
            raise RuntimeError("不应 init")

    config = {"modules": {"a": {"enabled": True}}}
    instances = build(config, dry_run=True)
    assert instances == {}  # dry_run 不返回实例


def test_build_with_param_wire():
    """param_wire 显式 mapping: dep name → __init__ 形参名。"""
    from emotion_spirit.registry import ModuleRegistry, register, build

    @register(name="a", provides=["A"], depends_on=[])
    class A:
        def __init__(self):
            self.x = 1

    # dep name "a" 形参名是 "other", 用 param_wire 显式 wire
    @register(name="b", provides=["B"], depends_on=["a"], param_wire={"a": "other"})
    class B:
        def __init__(self, other):
            self.other = other

    config = {"modules": {"a": {"enabled": True}, "b": {"enabled": True}}}
    instances = build(config)
    assert instances["b"].other is instances["a"]


def test_build_with_config_keys():
    """config_keys 从 config["params"] 注入, 不在 depends_on 列表。"""
    from emotion_spirit.registry import ModuleRegistry, register, build

    @register(name="a", provides=["A"], depends_on=[], config_keys={"data_dir", "name"})
    class A:
        def __init__(self, data_dir: str, name: str = "default") -> None:
            self.data_dir = data_dir
            self.name = name

    config = {
        "modules": {"a": {"enabled": True}},
        "params": {"data_dir": "/tmp/foo", "name": "test"},
    }
    instances = build(config)
    assert instances["a"].data_dir == "/tmp/foo"
    assert instances["a"].name == "test"


def test_build_multi_instance_superego():
    """provides_classes 触发 multi-instance 分支, 返回 dict[cls_name, instance]。"""
    from emotion_spirit.registry import ModuleRegistry, register, build

    @register(
        name="superego",
        provides=["Alignment", "Conscience"],
        depends_on=[],
        provides_classes={"Alignment": type("Alignment", (), {}),
                          "Conscience": type("Conscience", (), {})},
    )
    class _Bundle:
        def __init__(self) -> None: pass

    config = {"modules": {"superego": {"enabled": True}}}
    instances = build(config)
    assert isinstance(instances["superego"], dict)
    assert "Alignment" in instances["superego"]
    assert "Conscience" in instances["superego"]


def test_build_dry_run_28_modules():
    """dry_run 走 28 模块依赖图检查, 0 错误。完整 28 模块集成测试在 test_registry_build_dryrun.py。"""
    # 此处仅验证 dry_run 基础机制 (用单 module); 完整 28 模块 dry_run 在
    # tests/test_registry_build_dryrun.py::test_dry_run_28_modules_no_error。
    from emotion_spirit.registry import ModuleRegistry, register, build

    @register(name="a", provides=["A"], depends_on=[])
    class A:
        def __init__(self) -> None: pass

    config = {"modules": {"a": {"enabled": True}}}
    instances = build(config, dry_run=True)
    assert instances == {}


def test_build_superego_sub_dep_via_dot():
    """'superego.alignment' 这种 sub 引用从 instances['superego']['alignment'] 拿。"""
    from emotion_spirit.registry import ModuleRegistry, register, build

    @register(
        name="superego",
        provides=["Alignment", "Conscience"],
        depends_on=[],
        provides_classes={
            "alignment": type("Alignment", (), {"__init__": lambda self, persona="": None}),
            "conscience": type("Conscience", (), {"__init__": lambda self: None}),
        },
        config_keys={"persona"},
    )
    class _Bundle:
        def __init__(self) -> None: pass

    @register(name="consumer", provides=["Consumer"], depends_on=["superego.alignment", "superego.conscience"])
    class Consumer:
        def __init__(self, alignment, conscience):
            self.alignment = alignment
            self.conscience = conscience

    config = {
        "modules": {"superego": {"enabled": True}, "consumer": {"enabled": True}},
        "params": {"persona": "test"},
    }
    instances = build(config)
    assert instances["consumer"].alignment is instances["superego"]["alignment"]
    assert instances["consumer"].conscience is instances["superego"]["conscience"]
