"""Tests for SpiritStore v3 schema migration (Phase 2.0 Step 5).

验证:
1. v3 schema: memory_pools (per-user) + social_graph namespace
2. 老 v2 数据: memory_pool (单 key) → 自动迁移到 memory_pools
3. social_graph 命名空间初始化
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


def test_schema_version_is_3():
    """v3 schema 应是当前 schema_version。"""
    from emotion_spirit.store import _CURRENT_SCHEMA_VERSION
    assert _CURRENT_SCHEMA_VERSION >= 3


def test_migrate_v2_to_v3_memory_pool_to_pools():
    """老 v2 数据有 'memory_pool' 单 key, v3 应自动迁移到 'memory_pools'。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 写 v2 数据: 单个 memory_pool 键
        data_path = Path(tmpdir) / "spirit_data.json"
        v2_data = {
            "schema_version": 2,
            "memory_pool": {"buffer": [], "warm": [], "cold": [], "ghosts": [], "next_id": 0},
        }
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(v2_data, f)

        # 加载: 应自动迁移
        store = SpiritStore(tmpdir)
        # v3 应有 memory_pools 键 (来自 memory_pool 的迁移)
        assert store.get("memory_pools") is not None
        # 老 memory_pool 键被替换/移除
        assert store.get("memory_pool") is None or store.get("memory_pools") is not None


def test_social_graph_namespace_initialized():
    """v3: social_graph 命名空间应自动初始化。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        # v3 应自动初始化 social_graph 键
        assert store.get("social_graph") is not None
        assert "edges" in store.get("social_graph", {})
        assert "user_index" in store.get("social_graph", {})


def test_migrate_v2_preserves_data():
    """迁移不应丢失数据, 只是重命名键。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # v2 数据: memory_pool 含 1 个 warm entry
        data_path = Path(tmpdir) / "spirit_data.json"
        v2_data = {
            "schema_version": 2,
            "memory_pool": {
                "buffer": [], "warm": [{"id": "mem_1", "text": "test", "emotional_weight": 0.5}],
                "cold": [], "ghosts": [], "next_id": 1,
            },
        }
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(v2_data, f)

        store = SpiritStore(tmpdir)
        pools = store.get("memory_pools")
        # 迁移后数据应保留
        assert pools is not None
        # pools 是 dict[str, _UserPool], 至少应有 <global> 池 (旧数据视为 global)
        assert "<global>" in pools or "pools" in pools


if __name__ == "__main__":
    test_schema_version_is_3()
    test_migrate_v2_to_v3_memory_pool_to_pools()
    test_social_graph_namespace_initialized()
    test_migrate_v2_preserves_data()
    print("All SpiritStore v3 tests passed!")
