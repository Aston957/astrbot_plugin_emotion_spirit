"""Bug-E (v1.2.11): orchestrator 不再清 result_chain=None 守护.

emotion_spirit 清 result_chain=None 堵死 meme_manager.on_decorating_result
(if not result: return 早退) → 表情包消失. 改设 MessageChain([]) (空但非 None,
MessageChain 无 __bool__ → truthy → 不早退; chain 空 → 不 double-send).

源码守护 (不调 handle, 避免 astrbot.core.message import 依赖):
验证 orchestrator.py 不含 result_chain = None, 含 MessageChain([]).
用户反馈: 2026-07-04-emotion-spirit-v1210-feedback.md §8.2.
"""
from __future__ import annotations

from pathlib import Path

_ORCH = Path(__file__).parent.parent / "emotion_spirit/output/segmented_reply_orchestrator.py"


def test_no_result_chain_none_assignment():
    """orchestrator 不应清 result_chain=None (堵死 meme_manager → 表情包消失)."""
    source = _ORCH.read_text(encoding="utf-8")
    assert "response.result_chain = None" not in source, (
        "orchestrator 不应清 result_chain=None — Bug-E: 堵死 meme_manager.on_decorating_result "
        "早退 → 表情包消失. 改用 MessageChain([]) (空但非 None)."
    )


def test_result_chain_set_to_empty_message_chain():
    """orchestrator 应设 result_chain=MessageChain([]) (空但非 None, 让 meme_manager 不早退)."""
    source = _ORCH.read_text(encoding="utf-8")
    assert "response.result_chain = MessageChain([])" in source, (
        "orchestrator 应设 result_chain=MessageChain([]) — Bug-E 修法: 空但非 None, "
        "MessageChain 无 __bool__ → truthy → meme_manager on_decorating_result 不早退."
    )