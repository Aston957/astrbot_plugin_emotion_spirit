"""Tests for SpiritStore 4-NS typed accessor (Phase C, P3-5).

验证:
1. 4 个 NS (pad_history / pad_trajectory / memory_pools / social_graph) 独立
2. per-NS dirty 跟踪
3. 旧通用 get/set API 仍可用 (向后兼容)
4. save() 持久化所有 dirty NS
"""

import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock astrbot.api.logger
import types
astrbot_mock = types.ModuleType("astrbot")
astrbot_api_mock = types.ModuleType("astrbot.api")
astrbot_api_mock.logger = types.ModuleType("logger")
astrbot_api_mock.logger.warning = lambda *a, **kw: None
astrbot_api_mock.logger.info = lambda *a, **kw: None
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_api_mock
astrbot_mock.api = astrbot_api_mock

from emotion_spirit.store import SpiritStore


def _make_store():
    """返回临时 SpiritStore（不自动 load）。"""
    tmpdir = tempfile.mkdtemp()
    return SpiritStore(tmpdir)


# ═══ Test 1: 4 NS property 都存在 ═══


def test_ns_dispatch_via_property():
    """store.pad_history / .pad_trajectory / .memory_pools / .social_graph 4 个 NS property。"""
    store = _make_store()
    assert hasattr(store, "pad_history")
    assert hasattr(store, "pad_trajectory")
    assert hasattr(store, "memory_pools")
    assert hasattr(store, "social_graph")
    # 4 NS 互不相同
    ns_set = {store.pad_history, store.pad_trajectory, store.memory_pools, store.social_graph}
    assert len(ns_set) == 4


# ═══ Test 2: pad_history NS 独立 ═══


def test_pad_history_ns_isolated_from_other_ns():
    """pad_history NS 修改不影响 pad_trajectory / memory_pools / social_graph。"""
    store = _make_store()
    store.pad_history.update("sess1", [0.5, 0.3, 0.7, 100.0])
    assert store.pad_history.get("sess1") == [0.5, 0.3, 0.7, 100.0]
    # 其他 NS 不应受影响
    assert store.pad_trajectory.get("sess1") == []
    assert store.social_graph.get_edge("alice", "bob") is None


# ═══ Test 3: pad_trajectory NS append ═══


def test_pad_trajectory_ns_appends():
    """pad_trajectory NS append 累加 points。"""
    store = _make_store()
    store.pad_trajectory.append("s1", [0.5, 0.3, 0.7, 100.0])
    store.pad_trajectory.append("s1", [0.4, 0.2, 0.6, 101.0])
    assert store.pad_trajectory.get("s1") == [
        [0.5, 0.3, 0.7, 100.0],
        [0.4, 0.2, 0.6, 101.0],
    ]


# ═══ Test 4: memory_pools NS per-user ═══


def test_memory_pools_ns_per_user():
    """memory_pools NS 是 per-user dict, 不同 user 互不影响。"""
    store = _make_store()
    pool_a = store.memory_pools.get("alice")
    pool_b = store.memory_pools.get("bob")
    assert pool_a is not None
    assert pool_b is not None
    # 不同 user 应该是不同 dict 实例
    assert pool_a is not pool_b


# ═══ Test 5: social_graph NS 边 ═══


def test_social_graph_ns_directed_edges():
    """social_graph NS 支持有向边。"""
    store = _make_store()
    store.social_graph.add_edge("alice", "bob", relation_type="friend", trust=0.7)
    edge = store.social_graph.get_edge("alice", "bob")
    assert edge is not None
    assert edge["relation_type"] == "friend"
    assert edge["trust"] == 0.7
    # 反向不应有边 (有向图)
    assert store.social_graph.get_edge("bob", "alice") is None


# ═══ Test 6: per-NS dirty 跟踪 ═══


def test_per_ns_dirty_tracking():
    """每个 NS 独立跟踪 dirty 标志。"""
    store = _make_store()
    assert not store.pad_history.is_dirty()
    assert not store.pad_trajectory.is_dirty()
    assert not store.memory_pools.is_dirty()
    assert not store.social_graph.is_dirty()

    store.pad_history.update("s1", [0.5, 0.3, 0.7, 100.0])
    assert store.pad_history.is_dirty()
    assert not store.pad_trajectory.is_dirty()  # 其他 NS 不脏
    assert not store.memory_pools.is_dirty()
    assert not store.social_graph.is_dirty()


# ═══ Test 7: save 只持久化脏 NS (并清 dirty) ═══


def test_save_only_persists_dirty_ns():
    """save() 后所有 NS 的 dirty 标志被清空。"""
    store = _make_store()
    store.pad_history.update("s1", [0.5, 0.3, 0.7, 100.0])
    assert store.is_dirty

    # 模拟 save
    store.save()
    assert not store.pad_history.is_dirty()
    assert not store.pad_trajectory.is_dirty()
    assert not store.memory_pools.is_dirty()
    assert not store.social_graph.is_dirty()
    assert not store.is_dirty


# ═══ Test 8: 旧 get/set 仍工作 (向后兼容) ═══


def test_legacy_get_set_still_works():
    """旧通用 get/set API 仍能工作 (向后兼容)。"""
    store = _make_store()
    store.set("custom_key", {"foo": "bar"})
    assert store.get("custom_key") == {"foo": "bar"}
    # 旧 key 不在 4 NS 内
    assert store.get("custom_key") != store.pad_history.get("custom_key")


# ═══ Test 9: NS 修改 + save + reload 后数据保留 ═══


def test_ns_data_persists_after_reload():
    """NS 修改 + save + reload 后数据保留。"""
    tmpdir = tempfile.mkdtemp()
    store1 = SpiritStore(tmpdir)
    store1.pad_history.update("sess1", [0.5, 0.3, 0.7, 100.0])
    store1.pad_trajectory.append("sess1", [0.5, 0.3, 0.7, 100.0])
    store1.social_graph.add_edge("alice", "bob", relation_type="friend", trust=0.7)
    store1.save()

    store2 = SpiritStore(tmpdir)
    assert store2.pad_history.get("sess1") == [0.5, 0.3, 0.7, 100.0]
    assert store2.pad_trajectory.get("sess1") == [[0.5, 0.3, 0.7, 100.0]]
    assert store2.social_graph.get_edge("alice", "bob") is not None


# ═══ Test 10: 旧通用 key 跟 NS 独立 (data 顶层 vs _ns_data) ═══


def test_legacy_key_independent_from_ns():
    """旧 set('memory_pool', ...) 跟新 memory_pools NS 是独立空间。"""
    store = _make_store()
    store.set("memory_pool", {"old": "data"})
    # 旧 key 走通用 get
    assert store.get("memory_pool") == {"old": "data"}
    # 新 NS 是独立的空 dict
    assert store.memory_pools.get("alice") == {}


# ═══ Test 11: save 持久化旧 key + NS 混合 ═══


def test_save_persists_both_legacy_and_ns():
    """save() 持久化旧通用 key + 4 NS 全部 (向后兼容)。"""
    tmpdir = tempfile.mkdtemp()
    store1 = SpiritStore(tmpdir)
    store1.set("custom_key", {"legacy": True})
    store1.pad_history.update("s1", [0.5, 0.3, 0.7, 100.0])
    store1.save()

    # 读盘验证
    data_path = Path(tmpdir) / "spirit_data.json"
    with open(data_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # 旧 key 在 data 顶层
    assert raw.get("data", {}).get("custom_key") == {"legacy": True}
    # NS 在顶层
    assert raw.get("pad_history", {}).get("s1") == [0.5, 0.3, 0.7, 100.0]


# ═══ Test 12: empty store save() 是 no-op ═══


def test_empty_save_is_noop():
    """空 store save() 不应写盘。"""
    tmpdir = tempfile.mkdtemp()
    store = SpiritStore(tmpdir)
    data_path = Path(tmpdir) / "spirit_data.json"
    # 没有 dirty, save 应是 no-op
    assert not store.is_dirty
    store.save()
    # 文件不应被创建
    assert not data_path.exists()


if __name__ == "__main__":
    test_ns_dispatch_via_property()
    test_pad_history_ns_isolated_from_other_ns()
    test_pad_trajectory_ns_appends()
    test_memory_pools_ns_per_user()
    test_social_graph_ns_directed_edges()
    test_per_ns_dirty_tracking()
    test_save_only_persists_dirty_ns()
    test_legacy_get_set_still_works()
    test_ns_data_persists_after_reload()
    test_legacy_key_independent_from_ns()
    test_save_persists_both_legacy_and_ns()
    test_empty_save_is_noop()
    print("All 4-NS SpiritStore tests passed!")
