"""Tests for superego_guard.py — C 计划安全层"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotion_spirit.superego_guard import SuperegoGuard, InterventionResult
from emotion_spirit.superego import ConscienceTracker, ValueAlignment, IdealSelf
from emotion_spirit.config import SAFETY_CONFIG


# ═══ 辅助 ═══

def _make_guard(persona="xiaofu"):
    conscience = ConscienceTracker()
    alignment = ValueAlignment(persona)
    ideal = IdealSelf(persona, {"mbti": "ENFP", "attachment": "焦虑型"})
    return SuperegoGuard(conscience, alignment, ideal, persona), conscience, alignment, ideal


# ═══ 基本功能 ═══

def test_assess_normal():
    guard, conscience, alignment, ideal = _make_guard()
    sentinel_result = {"level": "normal", "triggered_count": 0, "triggered_signals": []}
    result = guard.assess(sentinel_result)
    assert result.level == "normal"
    assert result.conscience_threshold == SAFETY_CONFIG["conscience_threshold_normal"]
    assert result.safety_note is None
    assert result.repair_advice is None


def test_assess_warning():
    guard, conscience, alignment, ideal = _make_guard()
    sentinel_result = {"level": "warning", "triggered_count": 3, "triggered_signals": ["strain_accelerating"]}
    result = guard.assess(sentinel_result)
    assert result.level == "warning"
    assert result.conscience_threshold == SAFETY_CONFIG["conscience_threshold_warning"]


def test_assess_critical():
    guard, conscience, alignment, ideal = _make_guard()
    sentinel_result = {"level": "critical", "triggered_count": 5, "triggered_signals": ["strain_accelerating"]}
    result = guard.assess(sentinel_result)
    assert result.level == "critical"
    assert result.show_repair is True
    assert result.safety_note is not None


# ═══ 超我信号叠加 ═══

def test_superego_signal_pressure():
    guard, conscience, alignment, ideal = _make_guard()
    # 模拟高压力
    for _ in range(5):
        conscience.record_value_conflict(0.9, ["v1"], "guilt", 0.5, 0.8)

    sentinel_result = {"level": "warning", "triggered_count": 3, "triggered_signals": []}
    result = guard.assess(sentinel_result)
    # 超我信号 + sentinel warning → critical
    assert result.level == "critical"


def test_superego_signal_conflict_cluster():
    guard, conscience, alignment, ideal = _make_guard()
    # 模拟冲突聚类
    for _ in range(4):
        conscience.record_value_conflict(0.5, ["v1"], "guilt", 0.3, 0.4)

    sentinel_result = {"level": "warning", "triggered_count": 3, "triggered_signals": []}
    result = guard.assess(sentinel_result)
    assert result.level == "critical"


# ═══ 修复建议 ═══

def test_advise_guilt():
    guard, _, _, _ = _make_guard()
    advice = guard.advise("guilt", ["warmth_bias"])
    # 叙事模板: warmth_bias 高变体 advice = "做一件小事让你在乎的人感受到你的关心"
    assert "关心" in advice or "在乎" in advice


def test_advise_shame():
    guard, _, _, _ = _make_guard()
    advice = guard.advise("shame", ["autonomy_guard"])
    # 叙事模板: autonomy_guard 高变体 advice = "回到你自己的节奏里，不需要迎合谁"
    assert "节奏" in advice or "迎合" in advice


def test_advise_doubt():
    guard, _, _, _ = _make_guard()
    advice = guard.advise("doubt", ["inner_coherence"])
    # 叙事模板: inner_coherence 高变体 (默认) advice = "回顾一下你真正相信的是什么"
    assert "相信" in advice or "回顾" in advice


def test_advise_righteous():
    guard, _, _, _ = _make_guard()
    advice = guard.advise("righteous", ["warmth_bias"])
    # 叙事模板: warmth_bias 高变体 advice = "做一件小事让你在乎的人感受到你的关心"
    assert "关心" in advice or "在乎" in advice


# ═══ enabled 开关 ═══

def test_enabled_false():
    original = SAFETY_CONFIG["enabled"]
    SAFETY_CONFIG["enabled"] = False
    try:
        guard, conscience, alignment, ideal = _make_guard()
        sentinel_result = {"level": "critical", "triggered_count": 5, "triggered_signals": []}
        result = guard.assess(sentinel_result)
        assert result.level == "normal"
        assert result.safety_note is None
    finally:
        SAFETY_CONFIG["enabled"] = original


# ═══ 节流 ═══

def test_critical_throttle():
    guard, conscience, alignment, ideal = _make_guard()
    sentinel_result = {"level": "critical", "triggered_count": 5, "triggered_signals": []}

    # 触发 critical_max_per_day 次
    for _ in range(SAFETY_CONFIG["critical_max_per_day"]):
        guard.assess(sentinel_result)

    # 下一次应该降级为 warning
    result = guard.assess(sentinel_result)
    assert result.level == "warning"


# ═══ 持久化 ═══

def test_persistence():
    guard, _, _, _ = _make_guard()
    guard._critical_count_24h = 2
    data = guard.to_dict()
    assert "critical_count_24h" in data

    guard2, _, _, _ = _make_guard()
    guard2.from_dict(data)
    assert guard2._critical_count_24h == 2


if __name__ == "__main__":
    test_assess_normal()
    test_assess_warning()
    test_assess_critical()
    test_superego_signal_pressure()
    test_superego_signal_conflict_cluster()
    test_advise_guilt()
    test_advise_shame()
    test_advise_doubt()
    test_advise_righteous()
    test_enabled_false()
    test_critical_throttle()
    test_persistence()
    print("All superego_guard tests passed!")