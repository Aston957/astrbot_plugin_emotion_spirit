"""Tests for parse_persona_id (Phase 3.0C.2a spec §4.2)。

解析 persona_id (5 段 2 字母编码) → 5-key labels dict (中文标签)。
覆盖 10 场景: 合法解析 / 4 个 attachment code / AV 位置冲突 / 各类解析失败。
"""
from __future__ import annotations

import pytest

from emotion_spirit.persona_labels_db import parse_persona_id


# === 合法解析 ===

def test_parse_valid_persona_id():
    """合法 persona_id → 5-key labels dict (中文标签)。"""
    result = parse_persona_id("INFP-AV-EX-CO-PR")
    assert result == {
        "mbti": "INFP",
        "attachment": "回避型",
        "emotion_style": "表达型",
        "conflict_style": "合作型",
        "time_focus": "活在当下",
    }


def test_parse_all_attachment_codes():
    """4 个 attachment code 全覆盖。"""
    assert parse_persona_id("INFP-SE-EX-CO-PR")["attachment"] == "安全型"
    assert parse_persona_id("INFP-AP-EX-CO-PR")["attachment"] == "焦虑型"
    assert parse_persona_id("INFP-AV-EX-CO-PR")["attachment"] == "回避型"
    assert parse_persona_id("INFP-DS-EX-CO-PR")["attachment"] == "混乱型"


def test_parse_all_mbti_types():
    """16 MBTI 类型全部可解析。"""
    for mbti in [
        "INFP", "ENFP", "INFJ", "ENFJ", "INTJ", "ENTJ", "INTP", "ENTP",
        "ISFP", "ESFP", "ISFJ", "ESFJ", "ISTP", "ESTP", "ISTJ", "ESTJ",
    ]:
        result = parse_persona_id(f"{mbti}-SE-EX-CO-PR")
        assert result["mbti"] == mbti, f"{mbti} failed to parse"


def test_parse_av_collision_via_position():
    """AV 出现在 attachment (段 2) 和 conflict_style (段 4), 靠位置区分。

    spec §3.2 + memory 8 spec 偏离 #7: AV 双重含义, 位置解析消歧。
    """
    result = parse_persona_id("INFP-AV-EX-AV-PR")
    assert result["attachment"] == "回避型"
    assert result["conflict_style"] == "回避型"
    # 验证两者独立解析, 不互相覆盖
    assert result["attachment"] != result["conflict_style"] or result["attachment"] == "回避型"


# === 解析失败: 输入格式错误 ===

def test_parse_empty_string_returns_none():
    """空字符串 → None (不抛错)。"""
    assert parse_persona_id("") is None


def test_parse_wrong_segment_count():
    """段数 ≠ 5 → None。"""
    assert parse_persona_id("INFP-AV-EX") is None  # 3 段
    assert parse_persona_id("INFP-AV-EX-CO-PR-XX") is None  # 6 段
    assert parse_persona_id("INFP") is None  # 1 段


# === 解析失败: 段内容不合法 ===

def test_parse_invalid_mbti():
    """MBTI 段不在 16 合法集合 → None。"""
    assert parse_persona_id("XXXX-AV-EX-CO-PR") is None


def test_parse_invalid_attachment_code():
    """attachment 段不在 {SE, AP, AV, DS} → None。"""
    assert parse_persona_id("INFP-XX-EX-CO-PR") is None


def test_parse_invalid_emotion_code():
    """emotion_style 段不在 {EX, IH, ST, VO} → None。"""
    assert parse_persona_id("INFP-AV-XX-CO-PR") is None


def test_parse_invalid_conflict_code():
    """conflict_style 段不在 {CO, CP, AV, CM} → None。"""
    assert parse_persona_id("INFP-AV-EX-XX-PR") is None
