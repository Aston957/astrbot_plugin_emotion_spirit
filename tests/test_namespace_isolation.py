"""Namespace isolation test for embedded sylanne.

Verifies that emotion_spirit.sylanne (v3.0.1+) does NOT conflict with
external sylanne-1.4.7 (if user has both installed).

Background: emotion_spirit v3.0 embedded SylannEngine as
emotion_spirit.sylanne_core. Per ADR-0003, R3 renamed it to
emotion_spirit.sylanne (shorter, no _core suffix) to physically
isolate from external sylanne_alpha namespace.

This test ensures:
1. emotion_spirit.sylanne is the canonical path
2. emotion_spirit.sylanne_core is NO LONGER accessible (legacy removed)
3. If external sylanne_alpha is installed, it does not conflict
"""

from __future__ import annotations

import importlib
import sys


def test_canonical_path_sylanne_exists():
    """emotion_spirit.sylanne must be importable (canonical path post-R3)."""
    mod = importlib.import_module("emotion_spirit.sylanne")
    assert mod is not None
    # Key public API must be re-exported
    assert hasattr(mod, "SylanneEngine")
    assert hasattr(mod, "SylanneConfig")


def test_legacy_path_sylanne_core_removed():
    """emotion_spirit.sylanne_core must NOT be importable (R3 renamed it)."""
    # Clear any cached module
    sys.modules.pop("emotion_spirit.sylanne_core", None)
    try:
        importlib.import_module("emotion_spirit.sylanne_core")
        raise AssertionError(
            "emotion_spirit.sylanne_core should be removed after R3, "
            "but was importable. Check git history for failed rename."
        )
    except ModuleNotFoundError:
        pass  # Expected: legacy path is gone


def test_no_conflict_with_external_sylanne_alpha():
    """If external sylanne-1.4.7 is installed, our embedded sylanne doesn't conflict.

    emotion_spirit.sylanne and (hypothetical) sylanne_alpha should be
    different modules with different __name__.
    """
    # Import our embedded sylanne first
    import emotion_spirit.sylanne
    assert emotion_spirit.sylanne.__name__ == "emotion_spirit.sylanne"

    # If external sylanne_alpha is installed (rare), verify it's a different module
    if "sylanne_alpha" in sys.modules:
        external = sys.modules["sylanne_alpha"]
        assert external is not emotion_spirit.sylanne
        assert external.__name__ != emotion_spirit.sylanne.__name__


def test_subpackages_accessible():
    """emotion_spirit.sylanne.compute must be importable."""
    mod = importlib.import_module("emotion_spirit.sylanne.compute")
    assert mod is not None
    # Key compute classes
    assert hasattr(mod, "AlphaKernel")
    assert hasattr(mod, "AlphaBodyState")


def test_no_sys_modules_leak():
    """emotion_spirit.sylanne_core should not be in sys.modules after this test."""
    assert "emotion_spirit.sylanne_core" not in sys.modules
    assert "emotion_spirit.sylanne" in sys.modules
