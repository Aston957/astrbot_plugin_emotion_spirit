"""§1.7 轴心驱动守护: 轴心模块必须接受 personality (静态参数).

v1.3.0 rc.2: 本轮只验证 ConscienceTracker (已改). 其他轴心模块 (DefenseModulator/
Suppression/Collapse/IntimacyTracker/DecayModel/ReflexLearner) 标 TODO 后续 rc 耦合.

白名单: ForceDynamics (已耦合 compute(personality, ...)) + ConscienceTracker (rc.2 改).
TODO: 其余轴心模块 v1.3.0 后续 rc 接 personality.
"""
from __future__ import annotations

import inspect

from emotion_spirit.regulation.superego.conscience import ConscienceTracker
from emotion_spirit.regulation.force_dynamics import ForceDynamics


def test_conscience_tracker_has_set_personality():
    """ConscienceTracker 必须有 set_personality(personality) 接口 (§1.7 规则 4)."""
    assert hasattr(ConscienceTracker, "set_personality"), (
        "ConscienceTracker 必须有 set_personality 接受 13维 personality (§1.7 轴心耦合)"
    )
    sig = inspect.signature(ConscienceTracker.set_personality)
    assert "personality" in sig.parameters, "set_personality 必须接受 personality 参数"


def test_conscience_tracker_no_hardcoded_pressure_params():
    """ConscienceTracker 不应硬编码轴心参数 — 必须从 personality 算. Bug-G 复发拦截."""
    source = inspect.getsource(ConscienceTracker)
    # 关键: 不该有 get_pressure 用 _raw_pressure / P95 (旧饱和公式)
    assert "_raw_pressure / self._window_quantile" not in source, (
        "get_pressure 不应用 _raw_pressure/P95 公式 (Bug-G 饱和根因), 改双通道 acute+chronic"
    )
    assert "set_personality" in source, "必须有 set_personality 从 personality 算参数"


def test_force_dynamics_accepts_personality():
    """ForceDynamics.compute 必须接受 personality (已耦合, 防退步)."""
    sig = inspect.signature(ForceDynamics.compute)
    assert "personality" in sig.parameters, "ForceDynamics.compute 必须接受 personality (§1.7 耦合典范)"


# TODO (v1.3.0 后续 rc): DefenseModulator / Suppression / CollapseArchetypeSelector /
# IntimacyTracker / DecayModel / ReflexLearner 接 personality. 加测试守护.


def test_kb_weights_dims_covered_by_personality():
    """rc.4: KB conscience_params.json weights 引用的维度必须 ∈ 13维 personality (防 rc.3 错配重蹈).

    rc.3 set_personality 只传 deep (5维) → KB weights 引用 9 维 (含 6 个 surface 维) →
    surface 维度取 0.5 兜底 → 参数没人格化 → 饱和. 本测试防 regress.
    """
    import json
    from pathlib import Path

    kb = json.loads(
        Path("emotion_spirit/core/kb/conscience_params.json").read_text(encoding="utf-8")
    )
    # 13 维 personality (force_dynamics.py:4-7 / _BASELINE deep 5 + surface 8)
    PERSONALITY_DIMS = {
        "warmth_bias", "patience", "boundary_permeability",  # 自然 (deep)
        "relational_gravity", "intimacy_pull", "expression_drive", "gossip_tendency",  # 社会 (surface)
        "inner_coherence", "curiosity", "perception_acuity", "directness",  # 个体 (surface)
        "relational_autonomy", "exploration_openness",  # 个体 (surface)
    }
    for param_name, spec in kb.items():
        if param_name == "_meta":
            continue
        for dim in spec.get("weights", {}):
            assert dim in PERSONALITY_DIMS, (
                f"KB {param_name}.weights 引用 {dim!r}, 但不在 13维 personality 内 — "
                "set_personality 传 deep+surface 合并 (13维), weights 维度必须在其中"
            )
