"""EngineManager 测试。"""

import sys, os, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.bridge.engine_manager import EngineManager


class TestEngineManager:
    def test_init_defaults(self):
        em = EngineManager()
        assert em.available is False
        assert em._started is False

    def test_start_graceful(self):
        """start() 不管 sylanne 是否可用都不报错。"""
        em = EngineManager()
        result = em.start()
        # sylanne 可能可用也可能不可用, 但不应该抛异常
        assert isinstance(result, bool)

    def test_stop_when_not_started(self):
        em = EngineManager()
        em.stop()

    def test_process_returns_none_without_engine(self):
        em = EngineManager()
        assert em.process("session1", "hello") is None

    def test_state_returns_none_without_engine(self):
        em = EngineManager()
        assert em.state("session1") is None

    def test_inject_without_engine_and_forwarder(self):
        em = EngineManager()
        em.inject("session1", "test", "contradiction", 0.5)

    def test_set_forwarder(self):
        em = EngineManager()
        forwarder = object()
        em.set_forwarder(forwarder)
        assert em._forwarder is forwarder

    def test_on_surface_without_engine(self):
        em = EngineManager()
        em.on_surface(lambda *a: None)

    def test_off_surface_without_engine(self):
        em = EngineManager()
        em.off_surface(lambda *a: None)
