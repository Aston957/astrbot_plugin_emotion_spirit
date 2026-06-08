"""Tests for tools/check_registry_consistency.py (B6.x CI gate)。

正向测试: 静态扫描应该 28 模块全 pass, exit 0。
(dry_run 测试在 tests/test_registry_build_dryrun.py, 互补覆盖)
"""
from __future__ import annotations
import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_check_registry_consistency_passes():
    """跑静态扫描 CI gate, 29 模块全 pass, exit 0。"""
    import emotion_spirit  # noqa: F401
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tool_path = os.path.join(project_root, "tools", "check_registry_consistency.py")

    result = subprocess.run(
        [sys.executable, tool_path],
        capture_output=True, text=True, cwd=project_root,
    )
    assert result.returncode == 0, f"scan failed: stdout={result.stdout}, stderr={result.stderr}"
    assert "PASS" in result.stdout
    assert "29 modules" in result.stdout


def test_check_registry_consistency_covers_all_29_specs():
    """静态扫描内部遍历 ModuleRegistry.get_all(), 应有 29 个 specs。

    直接在测试进程内验证 _check_module_consistency 不抛错。
    """
    import emotion_spirit  # noqa: F401
    from emotion_spirit.registry import ModuleRegistry
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
