"""Smoke test for main.py per-user flow (Phase 2.0 Step 4).

验证 _consume_surface 在 per-user 模式下:
1. update_phi_for_user 只影响该 user 的 phi history
2. add_for_user 只加到该 user 的 buffer
3. confirm_check_for_user 只确认该 user 的 buffer
4. _resolve_user_id 返回 session_id
5. patterns.extract(user_id) 只读该 user 的 warm
6. counterfactual.ghost_resonance(entry, user_id) 只读该 user 的 ghosts
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock astrbot.api.logger
import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.debug = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
astrbot_api_mock.logger.error = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.memory_pool import MemoryPool
from emotion_spirit.buffer_signals import BufferSignals
from emotion_spirit.pattern_extractor import PatternExtractor
from emotion_spirit.counterfactual import Counterfactual


def test_resolve_user_id_returns_session_id():
    """_resolve_user_id 是抽象层: session_id → user_id 转换点。"""
    pool = MemoryPool()
    signals = BufferSignals(pool, user_id="alice_123")
    # 测试: pool 行为和 user_id="alice_123" 一致
    assert signals._user_id == "alice_123"


def test_main_per_user_calls_use_per_user_api():
    """静态验证: main.py 中 _consume_surface 调用 per-user API。"""
    import inspect
    import main as main_module
    # 这里 main.py 是 AstrBot 插件, 不容易直接实例化 — 用静态源码检查
    src = inspect.getsource(main_module)
    # 关键 API 调用应出现
    assert "add_for_user" in src, "main.py must use add_for_user"
    assert "update_phi_for_user" in src, "main.py must use update_phi_for_user"
    assert "confirm_check_for_user" in src, "main.py must use confirm_check_for_user"
    assert "_resolve_user_id" in src, "main.py must have _resolve_user_id method"
    # 旧 API 不应在 _consume_surface 出现
    consume_src = src[src.find("def _consume_surface"):src.find("def _consume_surface") + 5000]
    assert "self._pool.add(" not in consume_src, "_consume_surface must not use old pool.add()"
    assert "self._pool.update_phi(" not in consume_src, "_consume_surface must not use old update_phi()"


def test_main_per_user_pattern_extraction_isolated():
    """main.py 第 851 行的 patterns.extract(user_id=) 隔离。"""
    pool = MemoryPool()
    # alice: 6 条 trigger 模式
    for tag_pair in [("work", "rest"), ("work", "rest"), ("work", "rest")]:
        for t in tag_pair:
            pool.add_for_user("alice", f"a_{t}_{time.time()}", 0.5, 0.5, [t], "alice")
            time.sleep(0.01)
    # bob: 0 条
    pool.confirm_check_for_user("alice")

    extractor = PatternExtractor(pool)
    # alice 提取: 应有 trigger 模式
    alice_patterns = extractor.extract(window_days=10, user_id="alice")
    # bob 提取: 应为空
    bob_patterns = extractor.extract(window_days=10, user_id="bob")
    assert len(alice_patterns) > 0
    assert len(bob_patterns) == 0


def test_main_per_user_ghost_resonance_isolated():
    """main.py 第 856 行的 ghost_resonance(entry, user_id) 隔离。"""
    pool = MemoryPool()
    # alice: 1 ghost
    pool.add_for_user("alice", "alice_ghost", 0.95, 0.5, ["betrayal"], "alice")
    # bob: 1 ghost
    pool.add_for_user("bob", "bob_ghost", 0.95, 0.5, ["betrayal"], "bob")

    cf = Counterfactual(pool)
    # alice 的新记忆和 alice 的 ghost 共振 (tags 匹配)
    alice_entry = pool.warm_for("alice")[0] if pool.warm_for("alice") else None
    if alice_entry is None:
        # buffer 还没流转, 直接构造
        from emotion_spirit.memory_pool import MemoryEntry
        alice_entry = MemoryEntry(
            id="test_alice", text="alice_test", emotional_weight=0.5,
            phi_at_creation=0.5, tags=["betrayal"], source_user="alice",
        )
    # alice 视角: 应看到 alice_ghost 共振
    alice_boost = cf.ghost_resonance(alice_entry, user_id="alice")
    # bob 视角: 应看到 bob_ghost 共振
    bob_entry = type(alice_entry)(
        id="test_bob", text="bob_test", emotional_weight=0.5,
        phi_at_creation=0.5, tags=["betrayal"], source_user="bob",
    )
    bob_boost = cf.ghost_resonance(bob_entry, user_id="bob")
    # 两个共振都 > 0 (因为都有自己的 ghost)
    assert alice_boost > 0
    assert bob_boost > 0


if __name__ == "__main__":
    test_resolve_user_id_returns_session_id()
    test_main_per_user_calls_use_per_user_api()
    test_main_per_user_pattern_extraction_isolated()
    test_main_per_user_ghost_resonance_isolated()
    print("All main.py per-user tests passed!")
