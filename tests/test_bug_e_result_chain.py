"""Bug-E (v1.2.11): orchestrator delivery_mode + append to result_chain 守护.

v1.2.11 test1 修法 (result_chain=MessageChain([])) 方向错 — event.send 绕过 on_decorating_result,
meme_manager 读 event.get_result() 不是 response.result_chain.

v1.2.11 test2 (方向 1): 不 event.send, 改 append segments 到 response.result_chain,
让 AstrBot 默认 send 经 on_decorating_result → meme_manager 注入 image. 保留 event_send 接口
(delivery_mode config), v1.3+ 待 AstrBot send_delayed API 接回 delay.

源码守护 (不调 handle, 避免 astrbot.core.message import 依赖).
用户反馈: 2026-07-04-emotion-spirit-v1210test-feedback.md §2.
"""
from __future__ import annotations

from pathlib import Path

_ORCH = Path(__file__).parent.parent / "emotion_spirit/output/segmented_reply_orchestrator.py"


# ═══ v1.2.11 test1 基础守护 (仍有效) ═══


def test_no_result_chain_none_assignment():
    """orchestrator 不应清 result_chain=None (堵死 meme_manager → 表情包消失)."""
    source = _ORCH.read_text(encoding="utf-8")
    assert "response.result_chain = None" not in source, (
        "orchestrator 不应清 result_chain=None — Bug-E: 堵死 meme_manager.on_decorating_result "
        "早退 → 表情包消失. 改用 MessageChain([]) (空但非 None)."
    )


def test_result_chain_set_to_empty_message_chain():
    """orchestrator 应设 result_chain=MessageChain([]) (空但非 None, 让 meme_manager 不早退).

    v1.2.11 test2: 此 message chain 出现在 2 处 — silence 路径 (line 119) + event_send 分支.
    append 分支不清, 改 append segments.
    """
    source = _ORCH.read_text(encoding="utf-8")
    assert source.count("response.result_chain = MessageChain([])") >= 2, (
        "orchestrator 应设 result_chain=MessageChain([]) ≥ 2 处 (silence + event_send 分支) — "
        "Bug-E 修法: 空但非 None, MessageChain 无 __bool__ → truthy → meme_manager 不早退."
    )


# ═══ v1.2.11 test2 新增: delivery_mode 守护 ═══


def test_orchestrator_has_delivery_mode_branch():
    """orchestrator 应读 delivery_mode config (默认 append)."""
    source = _ORCH.read_text(encoding="utf-8")
    assert 'seg_config.get("delivery_mode"' in source or "seg_config.get('delivery_mode'" in source, (
        "orchestrator 应支持 delivery_mode config (Bug-E 方向 1)"
    )


def test_orchestrator_has_append_branch():
    """orchestrator 应有 append 模式 (segments → result_chain.chain.append)."""
    source = _ORCH.read_text(encoding="utf-8")
    assert "response.result_chain.chain.append(Plain(" in source, (
        "append 模式应 append segments 到 result_chain.chain (Bug-E 方向 1) "
        "— 让 AstrBot 默认 send 经 on_decorating_result → meme_manager 注入 image."
    )


def test_orchestrator_keeps_event_send_interface():
    """保留 event_send 接口 (delivery_mode='event_send' 走旧 event.send 路径).

    v1.3+ 待 AstrBot send_delayed API 后可加 delayed_append (append + delay 两全).
    """
    source = _ORCH.read_text(encoding="utf-8")
    assert 'delivery_mode == "event_send"' in source or "delivery_mode == 'event_send'" in source, (
        "应保留 event_send 分支 (接口, v1.3+ 待 send_delayed API 接回 delay)"
    )
    assert "await event.send(MessageChain([Plain(plan[0][\"text\"])]))" in source, (
        "event_send 分支应保留 event.send 分段逻辑"
    )


def test_append_mode_does_not_clear_result_chain():
    """append 分支应用 `is None` 守卫初始化 result_chain (不清空已有 LLM 默认链).

    语义: append 模式只在 result_chain 为 None 时初始化 MessageChain([]) 再 append segments;
    若已有内容 (LLM 默认链), 必须直接 .chain.append 保留, 不能重置.
    否则会清掉 LLM 默认链 → Bug-E 方向 1 失败 → 表情包仍可能丢失.
    """
    source = _ORCH.read_text(encoding="utf-8")
    else_start = source.find("else:")
    else_end = source.find("--- 7.", else_start)  # 下一个 section 标记
    assert else_start != -1 and else_end != -1, "应找到 append 分支 (else:) 与 --- 7. 分界"
    append_branch = source[else_start:else_end]
    assert "if response.result_chain is None:" in append_branch, (
        "append 分支应有 `is None` 守卫 — 否则裸 `response.result_chain = MessageChain([])` "
        "会清空 LLM 默认链, Bug-E 方向 1 失败. 守卫确保只在 None 时初始化."
    )


# ═══ Bug-D v1.2.11 test2: orchestrator 成功路径日志守护 ═══


def test_orchestrator_success_path_log():
    """orchestrator 成功路径应加 logger.info (user/mode/segments/chars/total_delay)."""
    source = _ORCH.read_text(encoding="utf-8")
    assert "emotion_spirit: segmented_reply user=" in source, (
        "orchestrator 成功路径应 logger.info — Bug-D v1.2.11 补全: 用户看不到分了几段/共几字/总延迟"
    )
