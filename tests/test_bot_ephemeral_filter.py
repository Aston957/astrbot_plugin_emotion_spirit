"""Bug-F (v1.2.11 → v1.3.0 rc.3): bot ephemeral state memory_type 标记 守护.

v1.2.11: token filter "不入 pool" (临时 patch).
v1.3.0 rc.3: 改标 memory_type=bot_ephemeral_state 仍入 pool, 召回时过滤.

构造模式复用 test_persona_load_priority: __new__ 跳过 __init__, mock _pool/_intimacy
/_reflex_learner, 调 _apply_bot_reply_effects 验证 add_for_user 是否带 memory_type.

用户反馈: 2026-07-04-emotion-spirit-v1210-feedback.md §8.3.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from main import EmotionSpiritPlugin, _EPHEMERAL_BOT_TOKENS


def _make_plugin_with_mock_pool() -> tuple[EmotionSpiritPlugin, MagicMock]:
    """__new__ 跳过 __init__, 注入 mock 依赖."""
    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    plugin._pool = MagicMock()
    plugin._intimacy = MagicMock()
    plugin._reflex_learner = MagicMock()
    plugin._last_bot_reply_time = {}
    return plugin, plugin._pool


def test_ephemeral_bot_state_tagged_ephemeral():
    """bot "我刚到门口" → add_for_user 调 + memory_type=bot_ephemeral_state (仍入 pool, 标类型)."""
    plugin, pool = _make_plugin_with_mock_pool()
    plugin._apply_bot_reply_effects("user1", "学长！我刚到门口，在等我姐。", "warm", 0.5)
    pool.add_for_user.assert_called_once()
    # 验证 memory_type 参数
    _call_kwargs = pool.add_for_user.call_args.kwargs
    assert _call_kwargs.get("memory_type") == "bot_ephemeral_state", (
        f"ephemeral bot state 应标 memory_type=bot_ephemeral_state, got {_call_kwargs.get('memory_type')}"
    )


def test_long_term_bot_fact_written_to_pool():
    """bot "我喜欢吃火锅" → add_for_user 调 + memory_type=bot_reply (long-term fact 默认)."""
    plugin, pool = _make_plugin_with_mock_pool()
    plugin._apply_bot_reply_effects("user1", "我喜欢吃火锅，冬天尤其想吃。", "warm", 0.5)
    pool.add_for_user.assert_called_once()
    _call_kwargs = pool.add_for_user.call_args.kwargs
    assert _call_kwargs.get("memory_type") in ("bot_reply", None), (
        f"long-term fact 应标 memory_type=bot_reply, got {_call_kwargs.get('memory_type')}"
    )


def test_ephemeral_state_still_updates_intimacy_and_reflex():
    """ephemeral filter 只改标记, intimacy/reflex 仍更新 (用户反馈 §8.3 方案 A 要求)."""
    plugin, pool = _make_plugin_with_mock_pool()
    plugin._apply_bot_reply_effects("user1", "我准备出门了", "warm", 0.5)
    pool.add_for_user.assert_called_once()  # 现在入 pool (标类型)
    plugin._intimacy.update.assert_called_once()
    plugin._reflex_learner.learn.assert_called_once()


def test_ephemeral_tokens_nonempty():
    """_EPHEMERAL_BOT_TOKENS 非空 (防意外清空)."""
    assert len(_EPHEMERAL_BOT_TOKENS) >= 10