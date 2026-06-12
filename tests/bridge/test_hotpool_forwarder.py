"""HotPoolForwarder 测试 (Phase D: MemoryPool 替代 UnifiedMemory)。"""

import sys, os, types, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
astrbot_api_mock.logger.debug = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.bridge.hotpool_forwarder import HotPoolForwarder
from emotion_spirit.memory.memory_pool import MemoryPool
from emotion_spirit.memory.unified_entry import UnifiedEntry


def _make_entry(text, tags=None, source_user="user1"):
    return UnifiedEntry(
        id=f"test_{int(time.time() * 1000)}_{id(text) % 10000}",
        text=text, tags=tags or [], entities={},
        source_user=source_user, privacy="private",
        created_at=time.time(), temperature=0.5,
        emotional_weight=0.5, mass=0.3, tier="buffer",
        is_ghost=False, recall_count=0, last_recalled=0.0, peak_temperature=0.5,
    )


class _MockPool:
    """Minimal mock with _entries and _cascade_engine for HotPoolForwarder tests."""
    def __init__(self):
        self._entries_dict = {}
        self._cascade_engine = None

    @property
    def _entries(self):
        return self._entries_dict


class TestHotPoolForwarder:
    def test_forward_without_memory(self):
        f = HotPoolForwarder()
        assert f.forward("s1", "contradiction", 0.5) == 0

    def test_forward_invalid_signal_type(self):
        pool = _MockPool()
        f = HotPoolForwarder(pool)
        assert f.forward("s1", "invalid", 0.5) == 0

    def test_forward_no_entries(self):
        pool = _MockPool()
        f = HotPoolForwarder(pool)
        assert f.forward("s1", "contradiction", 0.5) == 0

    def test_forward_affects_recent_entries(self):
        pool = _MockPool()
        for i in range(5):
            entry = _make_entry(f"memory {i}", source_user="user1")
            entry.created_at = time.time() - i * 100
            pool._entries_dict[entry.id] = entry
        f = HotPoolForwarder(pool)
        assert f.forward("user1", "contradiction", 0.5) > 0

    def test_forward_by_keyword_matching(self):
        pool = _MockPool()
        entry = _make_entry("今天天气真好", tags=["天气"], source_user="user1")
        pool._entries_dict[entry.id] = entry
        class MockEngine:
            _tag_index = {"天气": [entry.id]}
            _entity_index = {}
            def find_related(self, source): return []
        pool._cascade_engine = MockEngine()
        f = HotPoolForwarder(pool)
        assert f.forward("user1", "reinforcement", 0.3, source_text="天气不错") >= 1

    def test_set_memory_pool(self):
        f = HotPoolForwarder()
        mem = object()
        f.set_memory_pool(mem)
        assert f._memory is mem

    def test_extract_keywords_chinese(self):
        kw = HotPoolForwarder._extract_keywords("今天天气真好")
        assert any("天气" in k for k in kw)

    def test_extract_keywords_english(self):
        kw = HotPoolForwarder._extract_keywords("hello world test")
        assert "hello" in kw

    def test_extract_keywords_mixed(self):
        kw = HotPoolForwarder._extract_keywords("Python 编程很好玩")
        assert "python" in kw
        assert any("编程" in k for k in kw)
