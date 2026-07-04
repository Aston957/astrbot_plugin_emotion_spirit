"""Bug-F (v1.2.11): bot ephemeral state 不入 warm pool 守护.

bot "我刚到/我准备出门" 等短期 state 写进 warm pool → 新对话召回 → 上下文错乱
(bot 误以为还在上一场景). v1.2.11 token filter 临时挡 (v1.3 做 memory_type 彻底分类).

构造模式复用 test_persona_load_priority: __new__ 跳过 __init__, mock _pool/_intimacy
/_reflex_learner, 调 _apply_bot_reply_effects 验证 add_for_user 是否调.

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


def test_ephemeral_bot_state_not_written_to_pool():
    """bot "我刚到门口" → add_for_user 不调 (ephemeral state 不入 warm pool)."""
    plugin, pool = _make_plugin_with_mock_pool()
    plugin._apply_bot_reply_effects("user1", "学长！我刚到门口，在等我姐。", "warm", 0.5)
    pool.add_for_user.assert_not_called()


def test_long_term_bot_fact_written_to_pool():
    """bot "我喜欢吃火锅" → add_for_user 调 (long-term fact 该记)."""
    plugin, pool = _make_plugin_with_mock_pool()
    plugin._apply_bot_reply_effects("user1", "我喜欢吃火锅，冬天尤其想吃。", "warm", 0.5)
    pool.add_for_user.assert_called_once()


def test_ephemeral_state_still_updates_intimacy_and_reflex():
    """ephemeral filter 只跳 add_for_user, intimacy/reflex 不受影响 (用户反馈 §8.3 方案 A 要求)."""
    plugin, pool = _make_plugin_with_mock_pool()
    plugin._apply_bot_reply_effects("user1", "我准备出门了", "warm", 0.5)
    pool.add_for_user.assert_not_called()
    plugin._intimacy.update.assert_called_once()
    plugin._reflex_learner.learn.assert_called_once()


def test_ephemeral_tokens_nonempty():
    """_EPHEMERAL_BOT_TOKENS 非空 (防意外清空)."""
    assert len(_EPHEMERAL_BOT_TOKENS) >= 10