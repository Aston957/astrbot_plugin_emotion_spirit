"""Tests for PromptInjector boundary block (Phase A, gossip_tendency 真消费点)。

v1.7.2: 验证 gossip_tendency 在 prompt 输出里有真实的 [边界] 块映射。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_injector():
    """Mock 7 个依赖, 返回可正常跑 build_context 的 injector。

    所有 mock 都配置成"最小不阻塞"路径: 空列表 / 0.0 压力 / stranger 关系。
    这样 build_context 内部的所有条件分支都不会触发, 只测我们关心的 [边界] 块。
    """
    from emotion_spirit.prompt_injector import PromptInjector
    from unittest.mock import MagicMock

    pool = MagicMock()
    pool.warm_for.return_value = []  # 空列表 → 跳过 [印象] 块

    intimacy = MagicMock()
    intimacy.get_lifecycle.return_value = "stranger"
    intimacy.get_intimacy.return_value = 0.1

    conscience = MagicMock()
    conscience.get_pressure_breakdown.return_value = {
        "pressure": 0.0,
        "dominant_tension": None,
    }
    conscience.get_recent_alignments.return_value = []

    diary = MagicMock()
    diary.get_recent_diary.return_value = []

    shadow = MagicMock()
    shadow.detect.return_value = []

    return PromptInjector(
        pool=pool,
        intimacy=intimacy,
        alignment=MagicMock(),
        conscience=conscience,
        ideal=MagicMock(),
        shadow=shadow,
        diary=diary,
    )


def test_boundary_block_renders_for_low_gossip():
    """v1.7.2: gossip_tendency < 0.2 → 'bot 不会主动提其他人'。"""
    injector = _make_injector()
    text = injector.build_context(
        user_id="alice",
        persona="ISTJ-S",
        current_personality={},
        gossip_tendency=0.15,
    )
    assert "[边界] bot 不会主动提其他人" in text


def test_boundary_block_renders_for_high_gossip():
    """v1.7.2: gossip_tendency >= 0.8 → 'bot 主动分享听到的事'。"""
    injector = _make_injector()
    text = injector.build_context(
        user_id="alice",
        persona="ESTP-A",
        current_personality={},
        gossip_tendency=0.85,
    )
    assert "[边界] bot 主动分享听到的事" in text


def test_global_state_block_renders_aggregate_temperature():
    """v1.7.2 P2-1: [全局] 块读 BufferSignals.aggregate_temperature 渲染温度档。

    保留 aggregate_* 类方法不删 (反 YAGNI 修正), 通过 PromptInjector 注入真消费点。
    """
    from emotion_spirit.prompt_injector import PromptInjector
    from unittest.mock import MagicMock

    # 复用 _make_injector 的 mock 设置
    pool = MagicMock()
    pool.warm_for.return_value = []
    intimacy = MagicMock()
    intimacy.get_lifecycle.return_value = "stranger"
    intimacy.get_intimacy.return_value = 0.1
    conscience = MagicMock()
    conscience.get_pressure_breakdown.return_value = {"pressure": 0.0, "dominant_tension": None}
    conscience.get_recent_alignments.return_value = []
    diary = MagicMock()
    diary.get_recent_diary.return_value = []
    shadow = MagicMock()
    shadow.detect.return_value = []

    # Mock buffer_signals 实例: aggregate_temperature 返回中等 0.45
    buffer_signals = MagicMock()
    buffer_signals.aggregate_temperature.return_value = 0.45

    injector = PromptInjector(
        pool=pool, intimacy=intimacy, alignment=MagicMock(),
        conscience=conscience, ideal=MagicMock(), shadow=shadow,
        diary=diary, buffer_signals=buffer_signals,
    )

    text = injector.build_context(
        user_id="alice", persona="INFP-A",
        current_personality={}, gossip_tendency=0.3,
    )
    # [全局] 块应该出现, 含温度档位描述
    assert "[全局]" in text
    # 0.45 在 [0.3, 0.6) → "中等"
    assert "中等" in text or "0.45" in text


def test_global_state_block_omitted_when_buffer_signals_none():
    """v1.7.2: 没传 buffer_signals 时不渲染 [全局] 块 (向后兼容老 caller)。"""
    injector = _make_injector()  # _make_injector 不传 buffer_signals
    text = injector.build_context(
        user_id="alice", persona="ISTJ-S",
        current_personality={}, gossip_tendency=0.3,
    )
    assert "[全局]" not in text
