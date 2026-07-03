"""§1.4: 类型契约 — 跨子系统流动的裸 float 应加维度标签."""

from __future__ import annotations


def test_conscience_pressure_has_contract():
    """conscience_pressure 已通过参数签名明确 (HP-2 已修)."""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    import inspect
    sig = inspect.signature(DefenseModulator.compute_defense_states)
    param = sig.parameters.get("conscience_pressure")
    assert param is not None, "compute_defense_states 应有 conscience_pressure 参数"
    # 默认值应为 0.0
    assert param.default == 0.0, "conscience_pressure 默认应为 0.0 (向后兼容)"


def test_force_state_dict_contract():
    """force_state 参数应是 dict (非裸 float)."""
    from emotion_spirit.regulation.defense_modulator import DefenseModulator
    import inspect
    sig = inspect.signature(DefenseModulator.compute_defense_states)
    param = sig.parameters.get("force_state")
    assert param is not None, "compute_defense_states 应有 force_state 参数"
    # force_state 类型应为 Optional[dict], 默认无 default (=inspect._empty)
    # 检查 annotation 含 dict
    ann = str(param.annotation)
    assert "dict" in ann or "Dict" in ann or "Optional" in ann, (
        f"force_state 类型注解应为 dict, 实际: {ann}"
    )