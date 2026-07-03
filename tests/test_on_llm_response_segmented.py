"""Tests for main.py on_llm_response segmented reply skeleton (v1.2.5 PR1 §1, 投递机制)

验证:
1. streaming_response=true 时 emotion_spirit 跳过分段, event.send 不被调用
2. segmented_reply.enable=false 时跳过整段逻辑

注: 此项目未安装 pytest-asyncio, 使用 asyncio.run() 驱动 async 方法。
"""
import asyncio
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add project root to sys.path (conftest.py does this too; belt-and-suspenders)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ═══ Supplement conftest.py mocks with missing astrbot submodules ═══
# conftest.py already mocks: astrbot, astrbot.api, astrbot.api.event, astrbot.api.star
# This test file supplements with additional submodules that emotion_spirit may import.

def _ensure_module(name: str) -> types.ModuleType:
    """Ensure a mock module exists in sys.modules without overwriting existing."""
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)
    return sys.modules[name]


# Ensure astrbot.core.* chain (may be missing from conftest)
_ensure_module("astrbot.core")
_ensure_module("astrbot.core.utils")
if "astrbot.core.utils.astrbot_path" not in sys.modules:
    ap_path_mock = types.ModuleType("astrbot.core.utils.astrbot_path")
    ap_path_mock.get_astrbot_data_path = lambda: sys.modules.get("tempfile", __import__("tempfile")).gettempdir()
    sys.modules["astrbot.core.utils.astrbot_path"] = ap_path_mock

# Additional submodules that emotion_spirit may import
_ensure_module("astrbot.api.allocation")
_ensure_module("astrbot.api.provider")
_ensure_module("astrbot.api.message_components")

# Ensure astrbot.api.logger has all expected methods
api_mod = sys.modules.get("astrbot.api")
if api_mod is not None:
    logger_mod = getattr(api_mod, "logger", None)
    if logger_mod is not None:
        if not hasattr(logger_mod, "debug"):
            logger_mod.debug = lambda *a, **kw: None
        if not hasattr(logger_mod, "error"):
            logger_mod.error = lambda *a, **kw: None


def _make_plugin():
    """Create a minimal EmotionSpiritPlugin with all stub attributes needed by on_llm_response."""
    from main import EmotionSpiritPlugin

    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    # Stub all attributes accessed by on_llm_response before the segmented reply block
    plugin._pool = MagicMock()
    plugin._pool.add_for_user = MagicMock()
    plugin._intimacy = MagicMock()
    plugin._intimacy.update = MagicMock()
    plugin._reflex_learner = MagicMock()
    plugin._reflex_learner.learn = MagicMock()
    plugin._last_bot_reply_time = {}
    return plugin


def test_on_llm_response_streaming_mode_skips():
    """streaming_response=true → emotion_spirit 跳过, event.send 不被调, llm_resp 不被清空"""

    async def _run():
        plugin = _make_plugin()
        plugin._config = {
            "segmented_reply": {"enable": True},
            "provider_settings": {"streaming_response": True},
        }
        plugin._segmented_coordinator = MagicMock()

        event = MagicMock()
        event.send = AsyncMock()
        event.get_sender_id = MagicMock(return_value="alice_123")

        response = MagicMock()
        response.completion_text = "完整回复"

        await plugin.on_llm_response(event, response)

        assert event.send.call_count == 0
        assert response.completion_text == "完整回复"  # llm_resp 不应被清空

    asyncio.run(_run())


def test_on_llm_response_disabled_no_send():
    """segmented_reply.enable=false → 跳过整段逻辑, event.send 不被调用"""

    async def _run():
        plugin = _make_plugin()
        plugin._config = {
            "segmented_reply": {"enable": False},
            "provider_settings": {"streaming_response": False},
        }
        plugin._segmented_coordinator = MagicMock()

        event = MagicMock()
        event.send = AsyncMock()
        event.get_sender_id = MagicMock(return_value="bob_456")

        response = MagicMock()
        response.completion_text = "完整回复"

        await plugin.on_llm_response(event, response)

        assert event.send.call_count == 0
        assert response.completion_text == "完整回复"

    asyncio.run(_run())