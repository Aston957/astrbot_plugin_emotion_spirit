"""Integration tests for v1.1.0C modules.

Verifies that all 9 new v1.1.0C modules are registered in the global
``ModuleRegistry`` and that the public adaptation helpers are importable.

The 9 v1.1.0C modules:

* ``adaptation_engine`` (T1: ``emotion_spirit.utils.adaptation``)
* ``activity_history`` (T4: ``emotion_spirit.memory.activity_history``)
* ``project_manager`` (T5: ``emotion_spirit.regulation.project_manager``)
* ``recovery_tracker`` (T6: ``emotion_spirit.regulation.recovery_tracker``)
* ``personality_feedback`` (T7: ``emotion_spirit.regulation.personality_feedback``)
* ``user_activity_detector`` (T8: ``emotion_spirit.utils.user_activity_detector``)
* ``energy_model`` (T9: ``emotion_spirit.utils.energy_model``)
* ``environment_context`` (T9: ``emotion_spirit.regulation.environment_context``)
* ``emotion_predictor`` (T9: ``emotion_spirit.utils.emotion_predictor``)

These modules use the ``@register`` decorator, but they are NOT pulled in by
``emotion_spirit/__init__.py``'s explicit import list (they are leaf modules,
only depended on by the agents / life_simulator wiring).  The tests below
import each module to trigger its decorator side effect, then check the
registry.  ``ModuleRegistry.get_all()`` returns ``dict[str, ModuleSpec]`` so
we use ``ModuleRegistry._registry`` (the underlying storage) to iterate names.
"""
from __future__ import annotations

import pytest


# v1.1.0C module spec names (in spec-defined order; see task brief)
# v1.2.7: 4 modules moved to utils/ (no @register): adaptation, user_activity_detector,
# energy_model, emotion_predictor. Remaining 5 still @register in regulation/memory.
_V110C_MODULES = [
    "activity_history",
    "project_manager",
    "recovery_tracker",
    "personality_feedback",
    "environment_context",
]


@pytest.mark.parametrize("module_name", _V110C_MODULES)
def test_v110c_module_registered(module_name: str) -> None:
    """Each remaining @register v1.1.0C module should be in the registry."""
    # Explicit import triggers @register decorator side effect
    if module_name == "activity_history":
        import emotion_spirit.memory.activity_history  # noqa: F401
    elif module_name == "project_manager":
        import emotion_spirit.regulation.project_manager  # noqa: F401
    elif module_name == "recovery_tracker":
        import emotion_spirit.regulation.recovery_tracker  # noqa: F401
    elif module_name == "personality_feedback":
        import emotion_spirit.regulation.personality_feedback  # noqa: F401
    elif module_name == "environment_context":
        import emotion_spirit.regulation.environment_context  # noqa: F401

    from emotion_spirit.core.registry import ModuleRegistry

    assert module_name in ModuleRegistry.get_all(), (
        f"v1.1.0C module {module_name!r} not found in ModuleRegistry. "
        f"Known: {sorted(ModuleRegistry.get_all().keys())}"
    )


def test_v110c_utils_modules_importable() -> None:
    """4 v1.1.0C modules moved to utils/ should be importable (no @register)."""
    from emotion_spirit.utils import (
        compute_social_tendency,
        EmotionPredictor,
        UserActivityDetector,
        get_energy_level,
    )
    assert callable(compute_social_tendency)
    assert callable(EmotionPredictor)
    assert callable(UserActivityDetector)
    assert callable(get_energy_level)


def test_v110c_all_modules_registered() -> None:
    """All 5 remaining @register v1.1.0C modules should be in the registry.

    v1.2.7: 4 moved to utils/ (adaptation, user_activity_detector, energy_model,
    emotion_predictor) are no longer @register.
    """
    # Trigger all decorator side effects in one go
    import emotion_spirit.memory.activity_history  # noqa: F401
    import emotion_spirit.regulation.project_manager  # noqa: F401
    import emotion_spirit.regulation.recovery_tracker  # noqa: F401
    import emotion_spirit.regulation.personality_feedback  # noqa: F401
    import emotion_spirit.regulation.environment_context  # noqa: F401

    from emotion_spirit.core.registry import ModuleRegistry

    registered = set(ModuleRegistry.get_all().keys())
    missing = [m for m in _V110C_MODULES if m not in registered]
    assert not missing, f"v1.1.0C modules missing from registry: {missing}"


def test_adaptation_engine_imports() -> None:
    """Adaptation module should expose its key public functions."""
    from emotion_spirit.utils import (
        compute_social_tendency,
        select_adaptation_activity,
        derive_activity_preferences,
    )

    assert callable(compute_social_tendency)
    assert callable(select_adaptation_activity)
    assert callable(derive_activity_preferences)


def test_v110c_modules_provide_classes() -> None:
    """Each v1.1.0C ModuleSpec should have a non-empty provides list."""
    import emotion_spirit.memory.activity_history  # noqa: F401
    import emotion_spirit.regulation.project_manager  # noqa: F401
    import emotion_spirit.regulation.recovery_tracker  # noqa: F401
    import emotion_spirit.regulation.personality_feedback  # noqa: F401
    import emotion_spirit.regulation.environment_context  # noqa: F401

    from emotion_spirit.core.registry import ModuleRegistry

    registry = ModuleRegistry.get_all()
    for name in _V110C_MODULES:
        spec = registry[name]
        assert spec.provides, f"{name} has empty provides list"
        assert spec.module_class is not None, f"{name} has no module_class"
