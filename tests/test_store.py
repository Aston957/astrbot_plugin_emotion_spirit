"""Tests for store.py"""

import json
import os
import sys
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock astrbot.api.logger before importing
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


def test_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store.set("memory_pool", {"hot": [], "warm": []})
        store.save()

        store2 = SpiritStore(tmpdir)
        store2.load()
        assert store2.get("memory_pool") == {"hot": [], "warm": []}


def test_get_default():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        assert store.get("nonexistent") is None
        assert store.get("nonexistent", {"default": True}) == {"default": True}


def test_dirty_flag():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        assert not store.is_dirty
        store.set("key", "value")
        assert store.is_dirty
        store.save()
        assert not store.is_dirty


def test_double_save():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store.set("key", "value")
        store.save()
        # Second save should be no-op (dirty=False)
        store.save()
        assert not store.is_dirty


def test_empty_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store.load()  # Should not error
        assert store.get("anything") is None


# ═══ v1.2: schema v2 (pad_history / pad_trajectory) ═══


def test_v2_pad_history_namespace_exists():
    """pad_history 是顶层 dict（v1.2 schema 升级）。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store.load()
        assert "pad_history" in store._data
        assert store._data["pad_history"] == {}


def test_v2_pad_trajectory_namespace_exists():
    """pad_trajectory 是顶层 dict。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store.load()
        assert "pad_trajectory" in store._data
        assert store._data["pad_trajectory"] == {}


def test_update_pad_history_writes_correctly():
    """update_pad_history 写入 (v, a, d, t) list。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store.update_pad_history("s1", (0.5, 0.6, 0.7, 1234.0))
        assert store._data["pad_history"]["s1"] == [0.5, 0.6, 0.7, 1234.0]


def test_update_pad_trajectory_writes_list_of_lists():
    """update_pad_trajectory 写入 list of [v, a, d, t]。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        frames = [(0.5, 0.6, 0.7, 1234.0), (0.4, 0.5, 0.6, 1235.0)]
        store.update_pad_trajectory("s1", frames)
        assert store._data["pad_trajectory"]["s1"] == [
            [0.5, 0.6, 0.7, 1234.0],
            [0.4, 0.5, 0.6, 1235.0],
        ]


def test_update_pad_history_sets_dirty_flag():
    """update_pad_history 后 is_dirty = True。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        assert not store.is_dirty
        store.update_pad_history("s1", (0.5, 0.6, 0.7, 1234.0))
        assert store.is_dirty


def test_update_pad_trajectory_sets_dirty_flag():
    """update_pad_trajectory 后 is_dirty = True。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        assert not store.is_dirty
        store.update_pad_trajectory("s1", [(0.5, 0.6, 0.7, 1234.0)])
        assert store.is_dirty


def test_save_persists_pad_data_to_disk():
    """save() 后磁盘文件包含 pad 数据。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store.update_pad_history("s1", (0.5, 0.6, 0.7, 1234.0))
        store.update_pad_trajectory("s1", [[0.5, 0.6, 0.7, 1234.0]])
        store.save()

        data_path = os.path.join(tmpdir, "spirit_data.json")
        assert os.path.exists(data_path)
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["pad_history"]["s1"] == [0.5, 0.6, 0.7, 1234.0]
        assert data["pad_trajectory"]["s1"] == [[0.5, 0.6, 0.7, 1234.0]]


def test_load_back_compat_migrates_to_v2():
    """老 spirit_data.json (无 pad_history) → load 后自动加 v2 命名空间。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_path = os.path.join(tmpdir, "spirit_data.json")
        legacy = {"persona": {"foo": "bar"}, "memory_pool": {"entries": []}}
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(legacy, f)

        store = SpiritStore(tmpdir)
        store.load()
        assert "pad_history" in store._data
        assert "pad_trajectory" in store._data
        assert store._data["pad_history"] == {}
        assert store._data["pad_trajectory"] == {}
        # 老数据保留
        assert store._data["persona"] == {"foo": "bar"}


def test_round_trip_preserves_pad_data():
    """save → load 完整保留 pad_history / pad_trajectory。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store.update_pad_history("s1", (0.5, 0.6, 0.7, 1234.0))
        store.update_pad_trajectory("s1", [[0.5, 0.6, 0.7, 1234.0]])
        store.save()

        # 新 store 加载
        store2 = SpiritStore(tmpdir)
        store2.load()
        assert store2.get_pad_history("s1") == [0.5, 0.6, 0.7, 1234.0]
        assert store2.get_pad_trajectory("s1") == [[0.5, 0.6, 0.7, 1234.0]]


def test_periodic_save_dirty_only():
    """periodic_save 只在 dirty 时写盘。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store._dirty = False
        last_save = store._last_save_time
        # 不 dirty → 不写
        store.periodic_save()
        assert store._last_save_time == last_save
        # dirty → 写
        store._dirty = True
        store.periodic_save()
        assert store._last_save_time > last_save


def test_get_pad_history_default_empty_list():
    """get_pad_history 不存在的 session → None（caller 检查）。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = SpiritStore(tmpdir)
        store.load()
        assert store.get_pad_history("nonexistent") is None


if __name__ == "__main__":
    test_save_and_load()
    test_get_default()
    test_dirty_flag()
    test_double_save()
    test_empty_load()
    test_v2_pad_history_namespace_exists()
    test_v2_pad_trajectory_namespace_exists()
    test_update_pad_history_writes_correctly()
    test_update_pad_trajectory_writes_list_of_lists()
    test_update_pad_history_sets_dirty_flag()
    test_update_pad_trajectory_sets_dirty_flag()
    test_save_persists_pad_data_to_disk()
    test_load_back_compat_migrates_to_v2()
    test_round_trip_preserves_pad_data()
    test_periodic_save_dirty_only()
    test_get_pad_history_default_empty_list()
    print("All store tests passed!")
