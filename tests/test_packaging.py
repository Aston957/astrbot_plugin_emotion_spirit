# tests/test_packaging.py
"""Phase 4 C2 — packaging 验证"""
import re
import tomllib
import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


def test_pyproject_toml_valid():
    """pyproject.toml 可被 tomllib 解析, 含必要字段。"""
    pyproject = REPO_ROOT / "pyproject.toml"
    assert pyproject.exists()
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data["project"]
    assert project["name"] == "astrbot-plugin-emotion-spirit"
    # version 走 dynamic (从 emotion_spirit/_version.py 提供), base 必为 2.0.0
    assert "version" in project.get("dynamic", []), \
        "pyproject 应声明 dynamic = ['version'], 由 _version.py 提供"
    assert ">=3.11" in project["requires-python"]
    assert "astrbot>=4.9.2,<5" in project["dependencies"]
    assert "dev" in project["optional-dependencies"]
    # 版本 base (2.0.0) 通过 _version.py + metadata.yaml 共同验证 (下一个 test)


def test_metadata_yaml_version_matches_pyproject():
    """metadata.yaml 版本号与 pyproject.toml 等价 (PEP 440 base 一致)。

    pyproject.toml 用 PEP 440 合法形式 (例如 "2.0.0.post1"),
    metadata.yaml 用项目内部 release label (例如 "2.0.0v1", 包含非 PEP 440
    的 "vN" 后缀)。本测试要求两者归一化到相同的 base version
    (2.0.0), 即同一 release 的不同表达。
    """
    metadata_text = (REPO_ROOT / "metadata.yaml").read_text(encoding="utf-8")
    m = re.search(r"^\s*version:\s*[\"']?([^\"'\s#]+)[\"']?", metadata_text, re.MULTILINE)
    assert m, "metadata.yaml 缺 version 字段"
    metadata_version = m.group(1)

    # 解析 _version.py (PEP 440 合法, 通过 packaging.version 验证)
    version_py = REPO_ROOT / "emotion_spirit" / "_version.py"
    assert version_py.exists(), "emotion_spirit/_version.py 必须存在 (C2 引入)"
    ns = {}
    exec(version_py.read_text(encoding="utf-8"), ns)
    py_version_str = ns["__version__"]

    from packaging.version import Version, InvalidVersion
    try:
        py_v = Version(py_version_str)
    except InvalidVersion as e:
        pytest.fail(f"_version.py 中 __version__={py_version_str!r} 不是 PEP 440: {e}")

    # 解析 metadata 版本: 去掉非 PEP 440 字符 (例如 "v1" 后缀), 取 base
    # "2.0.0v1" → "2.0.0"
    base_match = re.match(r"^(\d+(?:\.\d+)*)", metadata_version)
    assert base_match, f"metadata 版本 {metadata_version!r} 缺少数字 base"
    metadata_base = base_match.group(1)
    py_base = ".".join(str(x) for x in py_v.release)

    assert metadata_base == py_base, (
        f"版本 base 不一致: metadata={metadata_version} (base={metadata_base}), "
        f"pyproject={py_version_str} (base={py_base})"
    )


def test_no_third_party_imports():
    """codebase 0 第三方依赖 (除 astrbot + stdlib + dev 测试)。

    本地模块 (在 emotion_spirit/ 下的 .py 文件, 或 emotion_spirit 包本身,
    或 main.py 这样的 repo-root 脚本) 视为合法。
    """
    emotion_spirit_dir = REPO_ROOT / "emotion_spirit"
    # 收集 emotion_spirit/ 下所有本地模块名 (去后缀)
    local_modules = {
        p.stem
        for p in emotion_spirit_dir.rglob("*.py")
        if p.stem != "__init__"
    }
    # repo-root 下的 .py 也算本地 (例如 main.py)
    repo_root_modules = {
        p.stem
        for p in REPO_ROOT.glob("*.py")
        if p.stem != "__init__"
    }
    local_top_levels = local_modules | repo_root_modules | {
        "emotion_spirit", "core", "memory", "regulation", "output",
    }
    allowed_prefixes = (
        "__future__",
        "ast", "astrbot", "collections", "dataclasses", "datetime",
        "enum", "functools", "hypothesis", "inspect", "itertools",
        "json", "logging", "math", "os", "pathlib", "random", "re",
        "string", "sys", "time", "typing", "unittest", "uuid",
        "warnings", "importlib", "copy", "abc", "io", "hashlib",
        "_pytest", "pytest", "asyncio", "tomllib", "builtins",
        "contextlib", "traceback", "types", "weakref", "operator",
        "threading", "multiprocessing", "queue", "socket", "urllib",
        "http", "email", "textwrap", "difflib", "pprint",
    )
    third_party = []
    for py_file in emotion_spirit_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in local_top_levels:
                        continue
                    if not any(top.startswith(p) for p in allowed_prefixes):
                        third_party.append(f"{py_file.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if top in local_top_levels:
                        continue
                    if not any(top.startswith(p) for p in allowed_prefixes):
                        third_party.append(f"{py_file.name}: from {node.module} import ...")
    assert third_party == [], f"发现第三方依赖: {third_party}"
