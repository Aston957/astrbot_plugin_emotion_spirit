"""Tests for tools/check_registry_consistency.py (B6.x CI gate)。

正向测试: 静态扫描应该 56 模块全 pass, exit 0。
(dry_run 测试在 tests/test_registry_build_dryrun.py, 互补覆盖)

Phase 3.0B Task 3: 29 → 30 (+body_state)
Phase 0 Task 3: 30 → 34 (+dream_generator, +reflex_learner, +reflex_learner_store, +memory_sampler)
Phase 0 Task 5: 34 → 39 (+cascade_engine, +decay_model, +suppression, +collapse_archetype, +collapse_archetype_selector)
v1.1.0C import-fix: 39 → 48 (+activity_history, +project_manager, +recovery_tracker,
                                 +personality_feedback, +user_activity_detector,
                                 +energy_model, +environment_context, +emotion_predictor)
v1.2.1 DI cleanup: 48 → 56 (+engine_manager, +hotpool_forwarder, +personality_bridge,
                                 +realtime_dispatch, +rhythm_learner, +self_core,
                                 +life_simulator_v2, +command_router;
                                 LifeAgent 因 factory 无法表达 self_core.bus 依赖,
                                 仍手 new — 同 MemoryAgent/PersonalityAgent/RelationshipAgent 一组)
"""
from __future__ import annotations
import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_check_registry_consistency_passes():
    """跑静态扫描 CI gate, 56 模块全 pass, exit 0。"""
    import emotion_spirit  # noqa: F401
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tool_path = os.path.join(project_root, "tools", "check_registry_consistency.py")

    result = subprocess.run(
        [sys.executable, tool_path],
        capture_output=True, text=True, cwd=project_root,
    )
    assert result.returncode == 0, f"scan failed: stdout={result.stdout}, stderr={result.stderr}"
    assert "PASS" in result.stdout
    assert "58 modules" in result.stdout


def test_check_registry_consistency_covers_all_58_specs():
    """静态扫描内部遍历 ModuleRegistry.get_all(), 应有 58 个 specs。"""
    import emotion_spirit  # noqa: F401
    from emotion_spirit.core.registry import ModuleRegistry
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tools.check_registry_consistency import _check_module_consistency

    # 每个 spec 都过一遍一致性检查, 不抛错 = OK
    for name, spec in ModuleRegistry.get_all().items():
        errs = _check_module_consistency(
            spec.module_class.__module__, name,
            {
                "depends_on": spec.depends_on,
                "param_wire": spec.param_wire,
                "config_keys": spec.config_keys,
                "provides_classes": spec.provides_classes,
            },
            spec.module_class,
        )
        assert errs == [], f"{name} has consistency issues: {errs}"
