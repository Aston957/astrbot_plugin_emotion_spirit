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
