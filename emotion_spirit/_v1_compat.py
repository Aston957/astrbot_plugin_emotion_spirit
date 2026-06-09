# emotion_spirit/_v1_compat.py
"""v1.x 兼容垫片 (Phase 4 C3)。

提供 v1.x API 的薄包装, 每次调用发 DeprecationWarning。
v1.x 用户过渡: 不需要 (v1 无用户, spec §1.3)。
v1.x 内部卫生: codebase 内部调用旧 API 时, 触发 warning 让 caller 知道要换。

将随 v2.1 删除 (届时所有 v1 调用点都应已迁移)。
"""
import warnings


def _conscience_pressure_old(severity: float) -> float:
    """v1.x: 直接 hard-clip severity 到 [0, 1] 当压力值。

    Deprecated since v2.0: 用 ConscienceTracker 替代。
    """
    warnings.warn(
        "_conscience_pressure_old() is deprecated, "
        "use ConscienceTracker.get_pressure() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return min(1.0, max(0.0, severity))


__all__ = ["_conscience_pressure_old"]
