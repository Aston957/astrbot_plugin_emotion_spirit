"""Tests for ModuleRegistry + DI (Phase B, P3-7 L2)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_function(function):
    """每个 test 前清空 registry。"""
    from emotion_spirit.registry import ModuleRegistry
    ModuleRegistry.reset()


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
