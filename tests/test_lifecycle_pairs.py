"""§1.5: 生命周期 — 有状态 @register 模块必须有 to_dict/from_dict 配对."""

from __future__ import annotations

from emotion_spirit.core.registry import ModuleRegistry


def _has_method(cls_or_name, method_name: str) -> bool:
    """检查模块类是否有某方法."""
    spec = ModuleRegistry.get_all().get(cls_or_name)
    if spec and spec.module_class:
        return hasattr(spec.module_class, method_name)
    return False


def test_to_dict_has_corresponding_from_dict():
    """有 to_dict 的模块应有 from_dict (或兼容接口)."""
    # v1.2.7: 检查已知有状态模块
    stateful_modules = [
        "force_dynamics", "intimacy", "memory_pool",
        "superego_guard", "suppression",
    ]
    for name in stateful_modules:
        spec = ModuleRegistry.get_all().get(name)
        if spec and spec.module_class:
            cls = spec.module_class
            has_to_dict = hasattr(cls, "to_dict")
            has_from_dict = hasattr(cls, "from_dict")
            assert has_to_dict == has_from_dict, (
                f"{name}: to_dict={has_to_dict} != from_dict={has_from_dict}"
            )


def test_shadow_detector_has_lifecycle():
    """有状态模块应当有 to_dict/from_dict 或显式标记为无状态."""
    from emotion_spirit.regulation.shadow_detector import ShadowDetector
    # ShadowDetector 是有状态的 (_detections 列表)
    assert hasattr(ShadowDetector, "to_dict"), "ShadowDetector 应有 to_dict"
    assert hasattr(ShadowDetector, "from_dict"), "ShadowDetector 应有 from_dict"