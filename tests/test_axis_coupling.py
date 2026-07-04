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
