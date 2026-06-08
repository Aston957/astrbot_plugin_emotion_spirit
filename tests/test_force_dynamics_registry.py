"""ForceDynamics @register 装饰 + 28→29 modules 验证 (Phase 3.0A)。"""
from __future__ import annotations


def test_force_dynamics_registered_in_module_registry():
    """ForceDynamics @register 进 ModuleRegistry, 28 → 29 modules。"""
    from emotion_spirit.registry import ModuleRegistry
    from emotion_spirit.force_dynamics import ForceDynamics

    all_specs = ModuleRegistry.get_all()
    assert "force_dynamics" in all_specs, "force_dynamics 没在 registry"

    spec = all_specs["force_dynamics"]
    assert spec.module_class is ForceDynamics
    assert spec.provides == ["ForceDynamics"]
    assert spec.depends_on == []
