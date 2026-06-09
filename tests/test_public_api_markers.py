"""Phase 4 C3 — public API markers 验证"""
import importlib
import re
import warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
EMOTION_SPIRIT_DIR = REPO_ROOT / "emotion_spirit"


def test_all_modules_have_all_list():
    """39 个 emotion_spirit/*.py 模块都有 __all__。"""
    modules = []
    for py_file in EMOTION_SPIRIT_DIR.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        if py_file.name == "_v1_compat.py":  # 兼容垫片, 不强制
            continue
        if py_file.name == "_version.py":  # auto-generated, 不强制
            continue
        modules.append(py_file.stem)
    for module_name in sorted(modules):
        mod = importlib.import_module(f"emotion_spirit.{module_name}")
        assert hasattr(mod, "__all__"), f"emotion_spirit.{module_name} 缺 __all__"
        assert len(mod.__all__) > 0, f"emotion_spirit.{module_name}.__all__ 是空"


def test_all_list_no_underscore_prefix():
    """__all__ 不含 _ 开头项 (除 __init__ 自身 & _v1_compat 兼容垫片)。"""
    for py_file in EMOTION_SPIRIT_DIR.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        if py_file.name == "_v1_compat.py":  # 兼容垫片, 名字就是 _ 前缀
            continue
        text = py_file.read_text(encoding="utf-8")
        m = re.search(r"__all__\s*=\s*\[(.*?)\]", text, re.DOTALL)
        if not m:
            continue
        block = m.group(1)
        items = re.findall(r'["\']([^"\']+)["\']', block)
        for item in items:
            if item.startswith("_") and not item.startswith("__"):
                pytest.fail(f"{py_file.name}.__all__ 含 _ 前缀项: {item}")


def test_deprecation_warning_raised_on_v1_compat():
    """v1.x 兼容垫片触发 DeprecationWarning。"""
    from emotion_spirit import _v1_compat
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = _v1_compat._conscience_pressure_old(0.5)
        assert any(issubclass(warning.category, DeprecationWarning) for warning in w), \
            "调用 _conscience_pressure_old 未触发 DeprecationWarning"
        assert result == 0.5


def test_deprecation_warning_message_has_alternative():
    """v1.x 兼容垫片 DeprecationWarning 含替代方案。"""
    from emotion_spirit import _v1_compat
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _v1_compat._conscience_pressure_old(0.5)
        deprecation_warnings = [warning for warning in w
                                if issubclass(warning.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 1
        assert "ConscienceTracker" in str(deprecation_warnings[0].message)


def test_public_api_stable_md_exists():
    """public_api_stable.md 存在且含 stable/deprecated 表。"""
    md = REPO_ROOT / "public_api_stable.md"
    assert md.exists()
    text = md.read_text(encoding="utf-8")
    assert "## Stable" in text
    assert "## Deprecated" in text
    assert "## Internal" in text


def test_public_api_stable_md_version_consistency():
    """public_api_stable.md 标题版本号与 emotion_spirit._version 一致。"""
    # pyproject.toml 用 dynamic version, 单点真相反而写在 _version.py
    from emotion_spirit._version import __version__ as pep_version
    md = (REPO_ROOT / "public_api_stable.md").read_text(encoding="utf-8")
    m = re.search(r"v?(\d+\.\d+\.\d+)", md)
    assert m, f"public_api_stable.md 缺版本号 (匹配 vX.Y.Z 或 X.Y.Z)"
    md_base = m.group(1)
    from packaging.version import Version
    pep_base = str(Version(pep_version).base_version)
    assert md_base == pep_base, f"version base 不一致: md={md_base}, _version={pep_base}"
