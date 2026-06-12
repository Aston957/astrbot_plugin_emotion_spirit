"""conftest.py for sylanne_core tests — sets up astrbot mock before collection."""

import sys
import types

# Mock astrbot before any emotion_spirit import
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
astrbot_api_mock.logger.debug = lambda *a, **kw: None
astrbot_api_mock.logger.error = lambda *a, **kw: None
sys.modules.setdefault("astrbot", astrbot_mock)
sys.modules.setdefault("astrbot.api", astrbot_api_mock)
astrbot_mock.api = astrbot_api_mock
