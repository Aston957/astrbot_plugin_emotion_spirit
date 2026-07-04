"""Bug-F (v1.3.0 rc.3): memory_type 字段 + 召回过滤 守护.

v1.2.11 token filter "不入 pool" 治标. v1.3.0 rc.3 改 memory_type:
bot ephemeral state 标类型仍入 pool (记录), 召回时过滤 (不注入 system_prompt).
"""
from __future__ import annotations

import inspect

import pytest

from emotion_spirit.memory.memory_pool import MemoryPool
from emotion_spirit.memory.unified_entry import UnifiedEntry
from main import _EPHEMERAL_BOT_TOKENS


@pytest.fixture
def pool() -> MemoryPool:
    return MemoryPool()


def test_unified_entry_has_memory_type_field():
    """UnifiedEntry dataclass 应含 memory_type 字段 (默认 bot_reply)."""
    assert "memory_type" in UnifiedEntry.__dataclass_fields__, (
        "UnifiedEntry 应含 memory_type 字段 (Bug-F)"
    )
    entry = UnifiedEntry(
        id="test", text="test", tags=[], entities={},
        source_user="bot", privacy="private", created_at=0.0,
        temperature=0.5, emotional_weight=0.5, mass=0.5,
        tier="buffer", is_ghost=False, recall_count=0,
        last_recalled=0.0, peak_temperature=0.5,
    )
    assert entry.memory_type == "bot_reply", "默认 memory_type 应为 bot_reply"
    # 可设
    entry.memory_type = "bot_ephemeral_state"
    assert entry.memory_type == "bot_ephemeral_state"


def test_add_for_user_has_memory_type_param():
    """add_for_user 接受 memory_type 参数."""
    sig = inspect.signature(MemoryPool.add_for_user)
    assert "memory_type" in sig.parameters, "add_for_user 应接受 memory_type (Bug-F)"
    # 默认值
    assert sig.parameters["memory_type"].default == "bot_reply"


def test_add_has_memory_type_param():
    """add() 接受 memory_type 参数."""
    sig = inspect.signature(MemoryPool.add)
    assert "memory_type" in sig.parameters, "add() 应接受 memory_type (Bug-F)"
    assert sig.parameters["memory_type"].default == "bot_reply"


def test_ephemeral_bot_state_tagged_not_skipped():
    """bot ephemeral state 仍入 pool (标 memory_type, 不再 '不入 pool')."""
    pool = MemoryPool()
    pool.add_for_user(
        user_id="u1", text="我刚到门口", raw_weight=0.5, phi=0.4,
        tags=["bot_reply", "warm"], source_user="bot",
        memory_type="bot_ephemeral_state",
    )
    # 应入 pool (不跳过)
    assert len(pool.warm) + len(pool.buffer) > 0, "ephemeral 应入 pool (标类型, 不再跳过)"


def test_search_by_vector_excludes_ephemeral():
    """召回时 exclude_memory_types 过滤 bot_ephemeral_state."""
    pool = MemoryPool()
    # 灌两条: ephemeral + long-term
    pool.add_for_user("u1", "我刚到门口", 0.5, 0.4, ["bot_reply"], "bot",
                      memory_type="bot_ephemeral_state")
    pool.add_for_user("u1", "我喜欢火锅", 0.5, 0.4, ["bot_reply"], "bot",
                      memory_type="bot_long_term_fact")
    # 召回 (query_vec 用任意, 因 MemoryPool 向量是 3-tuple)
    results_all = pool.search_by_vector((0.5, 0.5, 0.5), top_k=10, user_id="u1")
    results_filtered = pool.search_by_vector(
        (0.5, 0.5, 0.5), top_k=10, user_id="u1",
        exclude_memory_types={"bot_ephemeral_state"},
    )
    # 过滤后应少 (ephemeral 被排除)
    assert len(results_filtered) < len(results_all), (
        f"exclude_memory_types 应过滤 ephemeral: {len(results_filtered)} < {len(results_all)}"
    )
    assert len(results_filtered) >= 1, "long-term fact 应保留"


def test_ephemeral_tokens_still_used_for_tagging():
    """_EPHEMERAL_BOT_TOKENS 保留 (用于标 memory_type, 不再 '不入 pool')."""
    assert len(_EPHEMERAL_BOT_TOKENS) >= 10, "token 列表保留 (判定 ephemeral 用)"


def test_memory_type_to_dict_roundtrip():
    """memory_type 字段序列化/反序列化正确."""
    pool = MemoryPool()
    pool.add_for_user("u1", "我刚到门口", 0.5, 0.4, ["bot_reply"], "bot",
                      memory_type="bot_ephemeral_state")
    pool.add_for_user("u1", "我喜欢火锅", 0.5, 0.4, ["bot_reply"], "bot",
                      memory_type="bot_long_term_fact")

    data = pool.to_dict()
    # 反序列化
    pool2 = MemoryPool.from_dict(data)
    entries = pool2.all_entries()
    # 至少有一条 ephemeral
    ephemeral = [e for e in entries if e.memory_type == "bot_ephemeral_state"]
    long_term = [e for e in entries if e.memory_type == "bot_long_term_fact"]
    assert len(ephemeral) >= 1, "roundtrip 后 ephemeral memory_type 应保留"
    assert len(long_term) >= 1, "roundtrip 后 long_term memory_type 应保留"


def test_memory_type_to_dict_serialized():
    """to_dict 输出含 memory_type."""
    from emotion_spirit.memory.unified_entry import UnifiedEntry

    e = UnifiedEntry(
        id="test", text="test", tags=[], entities={},
        source_user="bot", privacy="private", created_at=0.0,
        temperature=0.5, emotional_weight=0.5, mass=0.5,
        tier="buffer", is_ghost=False, recall_count=0,
        last_recalled=0.0, peak_temperature=0.5,
        memory_type="bot_ephemeral_state",
    )
    d = e.to_dict()
    assert "memory_type" in d, "to_dict 应含 memory_type"
    assert d["memory_type"] == "bot_ephemeral_state"


def test_memory_type_from_dict_default():
    """旧数据 (无 memory_type) 默认 'bot_reply'."""
    from emotion_spirit.memory.unified_entry import UnifiedEntry

    d = {
        "id": "test", "text": "test", "tags": [], "entities": {},
        "source_user": "bot", "privacy": "private", "created_at": 0.0,
        "temperature": 0.5, "emotional_weight": 0.5, "mass": 0.5,
        "tier": "buffer", "is_ghost": False, "recall_count": 0,
        "last_recalled": 0.0, "peak_temperature": 0.5,
        "vector": [0.0, 0.0, 0.0],
        "cascade_generation": 0, "ghost_sensitivity_shift": 0.0,
        "participants": ["u1"], "mentioned": [],
        "impression": None, "compression": 0.0,
        # 故意无 memory_type
    }
    entry = UnifiedEntry.from_dict(d)
    assert entry.memory_type == "bot_reply", "旧数据无 memory_type → 默认 bot_reply"