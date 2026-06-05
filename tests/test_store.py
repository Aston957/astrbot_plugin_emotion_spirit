"""Tests for store.py"""

import tempfile
import sys
import os

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


if __name__ == "__main__":
    test_save_and_load()
    test_get_default()
    test_dirty_flag()
    test_double_save()
    test_empty_load()
    print("All store tests passed!")
