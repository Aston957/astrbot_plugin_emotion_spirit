"""Tests for BufferSignals per-user read path (Phase 2.0 Step 2).

核心断言:
1. 构造函数接受 user_id 参数
2. 实例方法默认读 user_id 对应池（per-user 隔离）
3. 跨用户隔离: user A 写入不影响 user B 的信号
4. 聚合类方法 BufferSignals.aggregate_* 跨用户读
5. 向后兼容: 默认 user_id="<global>" (与旧 pool.add() API 配合)
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock astrbot.api.logger (与 test_buffer_signals.py 一致)
import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.memory_pool import MemoryPool
from emotion_spirit.buffer_signals import BufferSignals


# ═══ 测试 1: 构造函数接受 user_id 参数 ═══

def test_constructor_accepts_user_id():
    """BufferSignals(pool, user_id) 应被接受并存为 _user_id。"""
    pool = MemoryPool()
    signals = BufferSignals(pool, user_id="alice")
    assert signals._user_id == "alice"


def test_constructor_default_user_id_global():
    """默认 user_id 应为 <global>, 保持向后兼容。"""
    pool = MemoryPool()
    signals = BufferSignals(pool)
    assert signals._user_id == "<global>"


# ═══ 测试 2: per-user 读路径 ═══

def test_temperature_per_user_isolated():
    """user A 的 buffer 满, user B 的 buffer 空 → A 的 temperature > 0, B 的 == 0。"""
    pool = MemoryPool()
    # user alice: 20 条
    for i in range(20):
        pool.add_for_user("alice", f"text {i}", 0.5, 0.5, ["test"], "alice")
    # user bob: 0 条
    signals_alice = BufferSignals(pool, user_id="alice")
    signals_bob = BufferSignals(pool, user_id="bob")
    assert signals_alice.buffer_temperature() > 0
    assert signals_bob.buffer_temperature() == 0.0


def test_momentum_per_user_only_sees_own_entries():
    """momentum 只看自己 user 的 entries, 不混入其他 user。"""
    pool = MemoryPool()
    # alice: 1 条
    pool.add_for_user("alice", "alice_event", 0.1, 0.5, ["tag"], "alice")
    # bob: 5 条 (达到 momentum 计算的 min threshold = 3)
    for i in range(5):
        pool.add_for_user("bob", f"bob_{i}", 0.9, 0.5, ["bob"], "bob")

    signals_alice = BufferSignals(pool, user_id="alice")
    signals_bob = BufferSignals(pool, user_id="bob")

    # alice 只有 1 条, momentum 不足阈值 → stable
    alice_momentum = signals_alice.emotional_momentum()
    assert alice_momentum["direction"] == "stable"

    # bob 有 5 条相同权重 → 不该是 escalating
    bob_momentum = signals_bob.emotional_momentum()
    # 5 条相同 weight 0.9 → early_avg == late_avg → stable (无差异)
    assert bob_momentum["direction"] == "stable"


def test_echo_patterns_per_user_isolated():
    """echo_patterns 只看自己 user 的 buffer。"""
    pool = MemoryPool()
    # alice: tag "hurt" 出现 5 次
    for i in range(5):
        pool.add_for_user("alice", f"a{i}", 0.5, 0.5, ["hurt"], "alice")
    # bob: tag "happy" 出现 5 次
    for i in range(5):
        pool.add_for_user("bob", f"b{i}", 0.5, 0.5, ["happy"], "bob")

    signals_alice = BufferSignals(pool, user_id="alice")
    signals_bob = BufferSignals(pool, user_id="bob")

    alice_echoes = signals_alice.echo_patterns()
    bob_echoes = signals_bob.echo_patterns()

    alice_tags = {e["tag"] for e in alice_echoes}
    bob_tags = {e["tag"] for e in bob_echoes}

    assert "hurt" in alice_tags
    assert "happy" not in alice_tags
    assert "happy" in bob_tags
    assert "hurt" not in bob_tags


def test_mode_b_strategy_per_user_uses_own_buffer():
    """mode_b_strategy 用自己的 buffer_temperature / momentum。"""
    pool = MemoryPool()
    # alice: buffer 满 (温度高)
    for i in range(30):
        pool.add_for_user("alice", f"a{i}", 0.9, 0.5, ["x"], "alice")
    # bob: buffer 空 → temperature == 0 → "exploratory"
    signals_alice = BufferSignals(pool, user_id="alice")
    signals_bob = BufferSignals(pool, user_id="bob")

    assert signals_bob.mode_b_strategy() == "exploratory"
    # alice 高温 → "cathartic"
    assert signals_alice.mode_b_strategy() == "cathartic"


# ═══ 测试 3: 向后兼容 (default user_id="<global>") ═══

def test_default_user_id_reads_global_pool():
    """默认 user_id="<global>" 时, 读旧 pool.add() 写入的数据。"""
    pool = MemoryPool()
    # 旧 API: pool.add() 写入 <global> 池
    for i in range(20):
        pool.add(f"global_{i}", 0.5, 0.5, ["legacy"], "user1")

    signals = BufferSignals(pool)  # 默认 <global>
    assert signals.buffer_temperature() > 0


# ═══ 测试 4: 聚合类方法 (跨用户读) ═══

def test_aggregate_temperature_merges_all_users():
    """BufferSignals.aggregate_temperature(pool) 应跨用户聚合。"""
    pool = MemoryPool()
    # alice: 15 条, 低权重 (避免温度公式饱和)
    for i in range(15):
        pool.add_for_user("alice", f"a{i}", 0.02, 0.5, ["x"], "alice")
    # bob: 15 条, 低权重
    for i in range(15):
        pool.add_for_user("bob", f"b{i}", 0.02, 0.5, ["x"], "bob")
    # 聚合温度应 > 单 user 温度 (30 条 vs 15 条, 容量压力不同)
    agg_temp = BufferSignals.aggregate_temperature(pool)
    single_temp = BufferSignals(pool, user_id="alice").buffer_temperature()
    assert agg_temp > single_temp
    assert agg_temp < 1.0  # 不应饱和
    assert single_temp < agg_temp


def test_aggregate_echo_patterns_merges_all_users():
    """BufferSignals.aggregate_echo_patterns(pool) 应看到所有 user 的 echo。"""
    pool = MemoryPool()
    for i in range(5):
        pool.add_for_user("alice", f"a{i}", 0.5, 0.5, ["shared_tag"], "alice")
    for i in range(5):
        pool.add_for_user("bob", f"b{i}", 0.5, 0.5, ["bob_only"], "bob")

    agg_echoes = BufferSignals.aggregate_echo_patterns(pool)
    tags = {e["tag"] for e in agg_echoes}
    assert "shared_tag" in tags
    assert "bob_only" in tags


# ═══ 测试 5: 内部 confirmation_history 仍实例级 (per-instance, 不按 user 分) ═══

def test_confirmation_history_remains_per_instance():
    """confirmation_history 不按 user 分, 是 BufferSignals 实例的状态。"""
    pool = MemoryPool()
    signals = BufferSignals(pool, user_id="alice")
    signals.record_confirmation("e1", 100.0, True, ["tag"])
    # 重新读 → 应能看到刚 record 的历史
    assert len(signals._confirmation_history) == 1
    # 换一个 user_id 实例化, 历史是新的
    signals2 = BufferSignals(pool, user_id="bob")
    assert len(signals2._confirmation_history) == 0


if __name__ == "__main__":
    test_constructor_accepts_user_id()
    test_constructor_default_user_id_global()
    test_temperature_per_user_isolated()
    test_momentum_per_user_only_sees_own_entries()
    test_echo_patterns_per_user_isolated()
    test_mode_b_strategy_per_user_uses_own_buffer()
    test_default_user_id_reads_global_pool()
    test_aggregate_temperature_merges_all_users()
    test_aggregate_echo_patterns_merges_all_users()
    test_confirmation_history_remains_per_instance()
    print("All buffer_signals per-user tests passed!")
