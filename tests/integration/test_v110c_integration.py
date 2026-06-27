"""Integration tests for v1.1.0C modules.

Verifies that all 9 new v1.1.0C modules are registered in the global
``ModuleRegistry`` and that the public adaptation helpers are importable.

The 9 v1.1.0C modules:

* ``adaptation_engine`` (T1: ``emotion_spirit.regulation.adaptation``)
* ``activity_history`` (T4: ``emotion_spirit.memory.activity_history``)
* ``project_manager`` (T5: ``emotion_spirit.regulation.project_manager``)
* ``recovery_tracker`` (T6: ``emotion_spirit.regulation.recovery_tracker``)
* ``personality_feedback`` (T7: ``emotion_spirit.regulation.personality_feedback``)
* ``user_activity_detector`` (T8: ``emotion_spirit.regulation.user_activity_detector``)
* ``energy_model`` (T9: ``emotion_spirit.regulation.energy_model``)
* ``environment_context`` (T9: ``emotion_spirit.regulation.environment_context``)
* ``emotion_predictor`` (T9: ``emotion_spirit.regulation.emotion_predictor``)

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
_V110C_MODULES = [
    "adaptation_engine",
    "activity_history",
    "project_manager",
    "recovery_tracker",
    "personality_feedback",
    "user_activity_detector",
    "energy_model",
    "environment_context",
    "emotion_predictor",
]


@pytest.mark.parametrize("module_name", _V110C_MODULES)
def test_v110c_module_registered(module_name: str) -> None:
    """Each v1.1.0C module should be in the registry after explicit import."""
    # Explicit import triggers @register decorator side effect
    if module_name == "adaptation_engine":
        import emotion_spirit.regulation.adaptation  # noqa: F401
    elif module_name == "activity_history":
        import emotion_spirit.memory.activity_history  # noqa: F401
    elif module_name == "project_manager":
        import emotion_spirit.regulation.project_manager  # noqa: F401
    elif module_name == "recovery_tracker":
        import emotion_spirit.regulation.recovery_tracker  # noqa: F401
    elif module_name == "personality_feedback":
        import emotion_spirit.regulation.personality_feedback  # noqa: F401
    elif module_name == "user_activity_detector":
        import emotion_spirit.regulation.user_activity_detector  # noqa: F401
    elif module_name == "energy_model":
        import emotion_spirit.regulation.energy_model  # noqa: F401
    elif module_name == "environment_context":
        import emotion_spirit.regulation.environment_context  # noqa: F401
    elif module_name == "emotion_predictor":
        import emotion_spirit.regulation.emotion_predictor  # noqa: F401

    from emotion_spirit.core.registry import ModuleRegistry

    assert module_name in ModuleRegistry.get_all(), (
        f"v1.1.0C module {module_name!r} not found in ModuleRegistry. "
        f"Known: {sorted(ModuleRegistry.get_all().keys())}"
    )


def test_v110c_all_modules_registered() -> None:
    """All 9 v1.1.0C modules should be in the registry after explicit import.

    This is the "combined" assertion from the task brief; it also serves as a
    single point of failure if any one module is missing.
    """
    # Trigger all decorator side effects in one go
    import emotion_spirit.regulation.adaptation  # noqa: F401
    import emotion_spirit.memory.activity_history  # noqa: F401
    import emotion_spirit.regulation.project_manager  # noqa: F401
    import emotion_spirit.regulation.recovery_tracker  # noqa: F401
    import emotion_spirit.regulation.personality_feedback  # noqa: F401
    import emotion_spirit.regulation.user_activity_detector  # noqa: F401
    import emotion_spirit.regulation.energy_model  # noqa: F401
    import emotion_spirit.regulation.environment_context  # noqa: F401
    import emotion_spirit.regulation.emotion_predictor  # noqa: F401

    from emotion_spirit.core.registry import ModuleRegistry

    registered = set(ModuleRegistry.get_all().keys())
    missing = [m for m in _V110C_MODULES if m not in registered]
    assert not missing, f"v1.1.0C modules missing from registry: {missing}"


def test_adaptation_engine_imports() -> None:
    """Adaptation module should expose its key public functions."""
    from emotion_spirit.regulation.adaptation import (
        compute_social_tendency,
        select_adaptation_activity,
        derive_activity_preferences,
    )

    assert callable(compute_social_tendency)
    assert callable(select_adaptation_activity)
    assert callable(derive_activity_preferences)


def test_v110c_modules_provide_classes() -> None:
    """Each v1.1.0C ModuleSpec should have a non-empty provides list."""
    import emotion_spirit.regulation.adaptation  # noqa: F401
    import emotion_spirit.memory.activity_history  # noqa: F401
    import emotion_spirit.regulation.project_manager  # noqa: F401
    import emotion_spirit.regulation.recovery_tracker  # noqa: F401
    import emotion_spirit.regulation.personality_feedback  # noqa: F401
    import emotion_spirit.regulation.user_activity_detector  # noqa: F401
    import emotion_spirit.regulation.energy_model  # noqa: F401
    import emotion_spirit.regulation.environment_context  # noqa: F401
    import emotion_spirit.regulation.emotion_predictor  # noqa: F401

    from emotion_spirit.core.registry import ModuleRegistry

    registry = ModuleRegistry.get_all()
    for name in _V110C_MODULES:
        spec = registry[name]
        assert spec.provides, f"{name} has empty provides list"
        assert spec.module_class is not None, f"{name} has no module_class"
