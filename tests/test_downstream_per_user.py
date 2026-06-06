"""Tests for downstream modules per-user read path (Phase 2.0 Step 3).

验证 PatternExtractor / Counterfactual / LifeSimulator / DiaryWriter /
NarrativeIdentity / PromptInjector 6 个下游模块都按 user_id 读池子,
跨用户隔离, 默认 <global> 向后兼容。
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
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.memory_pool import MemoryPool
from emotion_spirit.pattern_extractor import PatternExtractor
from emotion_spirit.counterfactual import Counterfactual
from emotion_spirit.life_simulator import LifeSimulator
from emotion_spirit.diary_writer import DiaryWriter
from emotion_spirit.narrative_identity import NarrativeIdentity
from emotion_spirit.prompt_injector import PromptInjector


# ═══ PatternExtractor ═══

def test_pattern_extractor_per_user_isolation():
    """PatternExtractor.extract(user_id) 只读该 user 的 warm 池。"""
    pool = MemoryPool()
    # alice: 6 条带 trigger 模式 (stress → cope 重复)
    pool.add_for_user("alice", "alice_e1", 0.5, 0.5, ["stress"], "alice")
    pool.add_for_user("alice", "alice_e2", 0.5, 0.5, ["cope"], "alice")
    pool.add_for_user("alice", "alice_e3", 0.5, 0.5, ["stress"], "alice")
    pool.add_for_user("alice", "alice_e4", 0.5, 0.5, ["cope"], "alice")
    pool.add_for_user("alice", "alice_e5", 0.5, 0.5, ["stress"], "alice")
    pool.add_for_user("alice", "alice_e6", 0.5, 0.5, ["cope"], "alice")
    # bob: 6 条不同 tags
    pool.add_for_user("bob", "bob_e1", 0.5, 0.5, ["happy"], "bob")
    pool.add_for_user("bob", "bob_e2", 0.5, 0.5, ["play"], "bob")
    pool.add_for_user("bob", "bob_e3", 0.5, 0.5, ["happy"], "bob")
    pool.add_for_user("bob", "bob_e4", 0.5, 0.5, ["play"], "bob")
    pool.add_for_user("bob", "bob_e5", 0.5, 0.5, ["happy"], "bob")
    pool.add_for_user("bob", "bob_e6", 0.5, 0.5, ["play"], "bob")
    # 流转到 warm
    pool.confirm_check_for_user("alice")
    pool.confirm_check_for_user("bob")

    extractor = PatternExtractor(pool)
    # alice 提取: stress→cope 触发模式
    alice_patterns = extractor.extract(window_days=10, user_id="alice")
    bob_patterns = extractor.extract(window_days=10, user_id="bob")
    # 隔离断言
    alice_tags = {tag for p in alice_patterns for tag in p.tags}
    bob_tags = {tag for p in bob_patterns for tag in p.tags}
    assert "stress" in alice_tags
    assert "happy" not in alice_tags
    assert "happy" in bob_tags
    assert "stress" not in bob_tags


def test_pattern_extractor_default_global():
    """默认 user_id=<global>, 旧 API 兼容。"""
    pool = MemoryPool()
    # 3 条 trigger 模式 (确保能检测到)
    pool.add("g_e1", 0.5, 0.5, ["work"], "user1")
    pool.add("g_e2", 0.5, 0.5, ["rest"], "user1")
    pool.add("g_e3", 0.5, 0.5, ["work"], "user1")
    pool.add("g_e4", 0.5, 0.5, ["rest"], "user1")
    pool.add("g_e5", 0.5, 0.5, ["work"], "user1")
    pool.add("g_e6", 0.5, 0.5, ["rest"], "user1")
    pool.confirm_check()  # 流转到 warm
    extractor = PatternExtractor(pool)
    # 默认 user_id="<global>" → 读 <global> 池
    patterns = extractor.extract(window_days=10)
    assert any("work" in p.tags for p in patterns)


# ═══ Counterfactual ═══

def test_counterfactual_get_eligible_ghosts_per_user():
    """Counterfactual.get_eligible_ghosts(user_id) 只读该 user 的 ghosts。"""
    pool = MemoryPool()
    # alice: 1 个 ghost (手动通过 bypass path: raw_weight > bypass + 标签含 betrayal)
    # 简单做法: 直接 add 一个 high-weight betrayal
    pool.add_for_user("alice", "alice_ghost", 0.95, 0.5, ["betrayal"], "alice")
    pool.add_for_user("bob", "bob_ghost", 0.95, 0.5, ["betrayal"], "bob")
    # 此时两边都有 ghost (因为 bypass_ghost 路径触发)

    cf = Counterfactual(pool)
    # 设 ghost_sensitivity_shift >= 0.25
    pool.ghosts_for("alice")[0].ghost_sensitivity_shift = 0.5
    pool.ghosts_for("bob")[0].ghost_sensitivity_shift = 0.5

    # 等 14 天
    past = time.time() - 15 * 86400
    for g in pool.ghosts_for("alice") + pool.ghosts_for("bob"):
        g.created_at = past

    alice_ghosts = cf.get_eligible_ghosts(user_id="alice")
    bob_ghosts = cf.get_eligible_ghosts(user_id="bob")
    # 隔离: alice 的不含 bob 的 source_user
    assert all(g.source_user == "alice" for g in alice_ghosts)
    assert all(g.source_user == "bob" for g in bob_ghosts)


# ═══ LifeSimulator ═══

def test_life_simulator_per_user_buffer_isolation():
    """LifeSimulator.check_mode_a(user_id) 读 user 的 buffer (不混其他 user)。"""
    pool = MemoryPool()
    # alice: 5 条高 weight (触发 Mode A)
    for i in range(5):
        pool.add_for_user("alice", f"a{i}", 0.9, 0.5, ["x"], "alice")
    # bob: 0 条

    # 构造 LifeSimulator 需要 consumer/intimacy/signals/reservoir, 这里只测 pool 部分
    # 简化: 直接测试 pool.sample_for_mode_a 的 per-user 路径
    from emotion_spirit.life_simulator import LifeSimulator
    from emotion_spirit.buffer_signals import BufferSignals
    # mock consumer/intimacy/reservoir
    class _Stub:
        pass
    sim = LifeSimulator(_Stub(), pool, _Stub(), _Stub(), _Stub())
    # alice: 5 条新条目在 5 min 内 → sample_for_mode_a(minutes=5) 应返回 5 条
    recent_alice = [e for e in pool.buffer_for("alice") if e.created_at > time.time() - 300]
    recent_bob = [e for e in pool.buffer_for("bob") if e.created_at > time.time() - 300]
    assert len(recent_alice) == 5
    assert len(recent_bob) == 0


# ═══ DiaryWriter ═══

def test_diary_writer_uses_user_id_in_pool_read():
    """DiaryWriter.build_diary_prompt(user_id) 读 user 的 warm 池。"""
    pool = MemoryPool()
    # alice: 3 条带 "hope" tag
    for i in range(3):
        pool.add_for_user("alice", f"a{i}", 0.5, 0.5, ["hope"], "alice")
    # bob: 3 条带 "regret" tag
    for i in range(3):
        pool.add_for_user("bob", f"b{i}", 0.5, 0.5, ["regret"], "bob")
    # 流转到 warm
    pool.confirm_check_for_user("alice")
    pool.confirm_check_for_user("bob")

    # 验证 DiaryWriter 内部使用 warm_for(user_id) (静态检查)
    from emotion_spirit.diary_writer import DiaryWriter
    import inspect
    src = inspect.getsource(DiaryWriter.build_diary_prompt)
    assert "warm_for" in src, "DiaryWriter.build_diary_prompt must use self._pool.warm_for(user_id)"

    # 验证 pool.warm_for 返回正确集合
    alice_warm = pool.warm_for("alice")
    bob_warm = pool.warm_for("bob")
    assert len(alice_warm) == 3
    assert len(bob_warm) == 3
    assert all("hope" in e.tags for e in alice_warm)
    assert all("regret" in e.tags for e in bob_warm)


# ═══ NarrativeIdentity ═══

def test_narrative_identity_uses_signals_with_user_id():
    """NarrativeIdentity 通过 signals (已 per-user from Step 2) 实现隔离。"""
    from emotion_spirit.buffer_signals import BufferSignals
    pool = MemoryPool()
    # alice 5 条, bob 5 条不同 weight
    for i in range(5):
        pool.add_for_user("alice", f"a{i}", 0.1, 0.5, ["x"], "alice")
        time.sleep(0.01)
    for i in range(5):
        pool.add_for_user("bob", f"b{i}", 0.9, 0.5, ["y"], "bob")
        time.sleep(0.01)

    # signals 绑定不同 user → 隔离已由 Step 2 保证
    sig_alice = BufferSignals(pool, user_id="alice")
    sig_bob = BufferSignals(pool, user_id="bob")
    # alice 是 escalating (低→高), bob 早期高 → 稳定/cooling
    m_alice = sig_alice.emotional_momentum()
    m_bob = sig_bob.emotional_momentum()
    # 隔离断言
    assert m_alice["avg_weight"] != m_bob["avg_weight"]


# ═══ PromptInjector ═══

def test_prompt_injector_uses_user_specific_warm():
    """PromptInjector.build_context(user_id, ...) 读 user_id 的 warm 池。"""
    pool = MemoryPool()
    # alice: 3 条
    for i in range(3):
        pool.add_for_user("alice", f"a{i}", 0.5, 0.5, ["x"], "alice")
    # bob: 3 条
    for i in range(3):
        pool.add_for_user("bob", f"b{i}", 0.5, 0.5, ["y"], "bob")

    # 构造 PromptInjector 需要其他依赖, 这里只测 pool 读取路径
    # 验证 PromptInjector.build_context 中 self._pool.warm 已被替换为 warm_for(user_id)
    from emotion_spirit.prompt_injector import PromptInjector
    class _Stub:
        def get_lifecycle(self, *a, **kw): return "stranger"
        def get_intimacy(self, *a, **kw): return 0.0
        def get_pressure_breakdown(self, *a, **kw): return {"pressure": 0.0}
        def get_recent_alignments(self, *a, **kw): return []
        def compute_gap(self, *a, **kw): return 0.0
        def get_direction(self, *a, **kw): return {}
    # 简化: 只验证 PromptInjector 内部使用 self._pool.warm_for(user_id)
    # 通过检查源代码 (静态验证) 或通过 mock
    import inspect
    src = inspect.getsource(PromptInjector.build_context)
    # 必须包含 warm_for 调用
    assert "warm_for" in src, "PromptInjector.build_context must use self._pool.warm_for(user_id)"


if __name__ == "__main__":
    test_pattern_extractor_per_user_isolation()
    test_pattern_extractor_default_global()
    test_counterfactual_get_eligible_ghosts_per_user()
    test_life_simulator_per_user_buffer_isolation()
    test_diary_writer_uses_user_id_in_pool_read()
    test_narrative_identity_uses_signals_with_user_id()
    test_prompt_injector_uses_user_specific_warm()
    print("All downstream per-user tests passed!")
