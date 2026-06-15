"""BotDecisionMaker proactive adapter 测试。"""

import sys, os, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from unittest.mock import MagicMock
from emotion_spirit.output.bot_decision import BotDecisionMaker


class TestBotDecisionProactive:
    def test_get_proactive_context_no_deps(self):
        bd = BotDecisionMaker()
        assert bd.get_proactive_context("user1") == ""

    def test_get_proactive_context_with_memory(self):
        bd = BotDecisionMaker()
        mock_memory = MagicMock()
        mock_memory.mean_temperature.return_value = 0.8
        mock_memory.count_hot.return_value = 3
        mock_memory.get_layer.return_value = []
        mock_memory.cascade_active.return_value = False
        bd.configure_proactive_deps(memory_pool=mock_memory)
        ctx = bd.get_proactive_context("user1")
        assert "内心很不平静" in ctx

    def test_get_proactive_context_calm(self):
        bd = BotDecisionMaker()
        mock_memory = MagicMock()
        mock_memory.mean_temperature.return_value = 0.2
        mock_memory.count_hot.return_value = 0
        mock_memory.get_layer.return_value = []
        mock_memory.cascade_active.return_value = False
        bd.configure_proactive_deps(memory_pool=mock_memory)
        ctx = bd.get_proactive_context("user1")
        assert "相对平静" in ctx

    def test_get_life_event_context_no_deps(self):
        bd = BotDecisionMaker()
        assert bd.get_life_event_context("user1") == ""

    def test_get_life_event_context_with_entries(self):
        bd = BotDecisionMaker()
        mock_entry = MagicMock()
        mock_entry.text = "今天天气很好"
        mock_entry.created_at = 1000.0
        mock_memory = MagicMock()
        mock_memory.get_layer.return_value = [mock_entry]
        bd.configure_proactive_deps(memory_pool=mock_memory)
        ctx = bd.get_life_event_context("user1")
        assert "天气很好" in ctx

    def test_should_suppress_proactive_no_deps(self):
        bd = BotDecisionMaker()
        assert bd.should_suppress_proactive("user1") == (False, "")

    def test_should_suppress_proactive_hurt(self):
        bd = BotDecisionMaker()
        mock_signals = MagicMock()
        mock_signals.pad_valence = -0.5
        mock_signals.pad_arousal = 0.8
        mock_signals.cascade_active = False
        mock_signals.collapse_count = 0
        mock_signals.in_recovery = False
        mock_consumer = MagicMock()
        mock_consumer.consume_for_session.return_value = mock_signals
        bd.configure_proactive_deps(surface_consumer=mock_consumer)
        suppress, reason = bd.should_suppress_proactive("user1")
        assert suppress and reason == "hurt"

    def test_should_suppress_proactive_collapsed(self):
        bd = BotDecisionMaker()
        mock_signals = MagicMock()
        mock_signals.pad_valence = 0.0
        mock_signals.pad_arousal = 0.3
        mock_signals.cascade_active = False
        mock_signals.collapse_count = 2
        mock_signals.in_recovery = False
        mock_consumer = MagicMock()
        mock_consumer.consume_for_session.return_value = mock_signals
        bd.configure_proactive_deps(surface_consumer=mock_consumer)
        suppress, reason = bd.should_suppress_proactive("user1")
        assert suppress and reason == "collapsed"

    def test_should_suppress_proactive_normal(self):
        bd = BotDecisionMaker()
        mock_signals = MagicMock()
        mock_signals.pad_valence = 0.1
        mock_signals.pad_arousal = 0.3
        mock_signals.cascade_active = False
        mock_signals.collapse_count = 0
        mock_signals.in_recovery = False
        mock_consumer = MagicMock()
        mock_consumer.consume_for_session.return_value = mock_signals
        bd.configure_proactive_deps(surface_consumer=mock_consumer)
        assert bd.should_suppress_proactive("user1") == (False, "")

    def test_configure_proactive_deps(self):
        bd = BotDecisionMaker()
        mem, con = object(), object()
        bd.configure_proactive_deps(memory_pool=mem, surface_consumer=con)
        assert bd._memory_pool is mem
        assert bd._surface_consumer is con

    def test_get_life_simulation_context_no_sim(self):
        """无 LifeSimulator 时返回空字符串。"""
        bd = BotDecisionMaker()
        assert bd.get_life_simulation_context("user1") == ""

    def test_get_life_simulation_context_no_event(self):
        """LifeSimulator 无 pending event 时返回空字符串。"""
        bd = BotDecisionMaker()
        mock_sim = MagicMock()
        mock_sim.pending_life_event = None
        bd.configure_proactive_deps(life_simulator=mock_sim)
        assert bd.get_life_simulation_context("user1") == ""

    def test_get_life_simulation_context_with_event(self):
        """LifeSimulator 有 pending event 时返回上下文。"""
        from emotion_spirit.regulation.life_simulator import LifeEvent
        import time

        bd = BotDecisionMaker()
        mock_sim = MagicMock()
        mock_sim.pending_life_event = LifeEvent(
            text="安静地翻着一本书",
            mood="平静",
            urgency=0.2,
            timestamp=time.time(),
            wants_to_share=True,
            event_type="reading",
        )
        bd.configure_proactive_deps(life_simulator=mock_sim)

        ctx = bd.get_life_simulation_context("user1")
        assert "安静地翻着一本书" in ctx
        assert "平静" in ctx
        assert "想分享给你" in ctx

    def test_get_life_simulation_context_no_share(self):
        """wants_to_share=False 时不显示分享提示。"""
        from emotion_spirit.regulation.life_simulator import LifeEvent
        import time

        bd = BotDecisionMaker()
        mock_sim = MagicMock()
        mock_sim.pending_life_event = LifeEvent(
            text="在发呆",
            mood="neutral",
            urgency=0.1,
            timestamp=time.time(),
            wants_to_share=False,
        )
        bd.configure_proactive_deps(life_simulator=mock_sim)

        ctx = bd.get_life_simulation_context("user1")
        assert "在发呆" in ctx
        assert "想分享" not in ctx
