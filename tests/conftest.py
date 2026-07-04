"""Shared pytest fixtures + 5 persona fixture labels re-export (Phase 3.0A)。

5 persona fixture labels 在 tests/fixture_labels.py (普通 Python module),
本文件 re-export + 5 个 pytest fixtures。

注: labels 放在 fixture_labels.py (而非 conftest.py) 是因为 pytest conftest.py
有特殊加载语义, 其他测试文件 (e.g. verification/test_gossip_tendency_simulation.py)
需要通过 importlib 加载。fixture_labels.py 是普通 Python module, 可被任何位置 import。
"""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path

import pytest

# Mock astrbot before any emotion_spirit import (测试环境无 AstrBot 宿主)
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
astrbot_api_mock.logger.debug = lambda *a, **kw: None
astrbot_api_mock.logger.error = lambda *a, **kw: None
# Mock astrbot.api.event (main.py + commands.py import from it)
# v1.2.5: added filter decorators to support `from astrbot.api.event import filter`
astrbot_api_event_mock = types.ModuleType("astrbot.api.event")
astrbot_api_event_mock.filter = types.SimpleNamespace(
    on_llm_request=lambda: lambda f: f,
    on_llm_response=lambda **kw: lambda f: f,
    on_decorating_result=lambda **kw: lambda f: f,
    command=lambda *args, **kwargs: lambda f: f,
)
astrbot_api_event_mock.AstrMessageEvent = type("AstrMessageEvent", (), {})
astrbot_api_mock.event = astrbot_api_event_mock
# Mock astrbot.api.star (main.py: from astrbot.api.star import Context, Star)
astrbot_api_star_mock = types.ModuleType("astrbot.api.star")
astrbot_api_star_mock.Context = type("Context", (), {})
astrbot_api_star_mock.Star = type("Star", (), {})
sys.modules.setdefault("astrbot", astrbot_mock)
sys.modules.setdefault("astrbot.api", astrbot_api_mock)
sys.modules.setdefault("astrbot.api.event", astrbot_api_event_mock)
sys.modules.setdefault("astrbot.api.star", astrbot_api_star_mock)
astrbot_mock.api = astrbot_api_mock
# Mock astrbot.core.utils.astrbot_path (main.py:23 imports get_astrbot_data_path).
# v1.2.11: 补全 conftest mock — 之前 test_init_persistence 等各自 mock, conftest 漏了,
# 导致 `from main import` 的测试 (e.g. test_signature_compat) collect 即崩.
# 用 setdefault 不覆盖已有, test_init_persistence 自己的 mock 仍优先.
astrbot_core_mock = types.ModuleType("astrbot.core")
astrbot_core_utils_mock = types.ModuleType("astrbot.core.utils")
astrbot_core_utils_path_mock = types.ModuleType("astrbot.core.utils.astrbot_path")
astrbot_core_utils_path_mock.get_astrbot_data_path = lambda: tempfile.gettempdir()
sys.modules.setdefault("astrbot.core", astrbot_core_mock)
sys.modules.setdefault("astrbot.core.utils", astrbot_core_utils_mock)
sys.modules.setdefault("astrbot.core.utils.astrbot_path", astrbot_core_utils_path_mock)
astrbot_core_mock.utils = astrbot_core_utils_mock
astrbot_core_utils_mock.astrbot_path = astrbot_core_utils_path_mock

# 让 verification/ 模块能 import
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "verification"))
# pytest 加载 conftest 时不一定把 tests/ 加进 sys.path, 显式加上
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))


# v1.2.11: defensive logger method 兜底 — Patch B B5 路径用 logger.info + Bug-F ephemeral
# filter 用 logger.debug, 但某些 collect 顺序下 main 在 mock 完成前 import, 拿到空 ModuleType.
# 直接给 main.logger 补所有方法 (conftest.py 末尾, 任何 main import 之后都会运行).
def _noop(*args, **kwargs):
    return None


try:
    import main as _main_module  # noqa: E402
    for _mname in ("debug", "info", "warning", "error", "critical", "exception"):
        if not hasattr(_main_module.logger, _mname):
            setattr(_main_module.logger, _mname, _noop)
except (ImportError, AttributeError):
    pass


# 从 fixture_labels.py re-export
from fixture_labels import (  # noqa: E402
    INFP_A_LABELS,
    ISTJ_S_LABELS,
    ENTP_AV_LABELS,
    ISFJ_D_LABELS,
    ESTP_A_LABELS,
    ALL_5_FIXTURE_LABELS,
    ALL_5_FIXTURE_NAMES,
    ALL_5_FIXTURES,
)


__all__ = [
    "INFP_A_LABELS", "ISTJ_S_LABELS", "ENTP_AV_LABELS",
    "ISFJ_D_LABELS", "ESTP_A_LABELS",
    "ALL_5_FIXTURE_LABELS", "ALL_5_FIXTURE_NAMES", "ALL_5_FIXTURES",
]


# ═══ pytest fixtures (包装 labels 副本, 防止测试意外修改全局) ═══

@pytest.fixture
def infp_a_labels() -> dict[str, str]:
    """INFP-A 5 标签 (mbti + attachment + emotion_style + conflict_style + time_focus)。"""
    return dict(INFP_A_LABELS)


@pytest.fixture
def istj_s_labels() -> dict[str, str]:
    """ISTJ-S 5 标签。"""
    return dict(ISTJ_S_LABELS)


@pytest.fixture
def entp_av_labels() -> dict[str, str]:
    """ENTP-AV 5 标签。"""
    return dict(ENTP_AV_LABELS)


@pytest.fixture
def isfj_d_labels() -> dict[str, str]:
    """ISFJ-D 5 标签。"""
    return dict(ISFJ_D_LABELS)


@pytest.fixture
def estp_a_labels() -> dict[str, str]:
    """ESTP-A 5 标签。"""
    return dict(ESTP_A_LABELS)


@pytest.fixture
def all_5_fixture_labels() -> list[dict[str, str]]:
    """5 persona 标签列表 (5 fixture 全套)。"""
    return [dict(labels) for labels in ALL_5_FIXTURE_LABELS]
