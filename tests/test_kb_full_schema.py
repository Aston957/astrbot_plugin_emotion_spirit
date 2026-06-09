"""Tests for full 3072 KB schema validation (Phase 3.0C.2b spec §3.3)。

6 个测试: 验证 3072 KB 完整 schema 一致性 + 5 fixture regression。
"""
from __future__ import annotations

import pytest

from emotion_spirit.core.persona_labels_db import (
    REQUIRED_DIMS,
    get_persona_labels_db,
    parse_persona_id,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _reset():
    """每个 test 前/后重置 in-memory cache, 防止测试污染。"""
    reset_cache()
    yield
    reset_cache()


def test_kb_has_3072_entries():
    """最终 KB 必须 3072 entries (16 × 4 × 4 × 4 × 3 = 3072)。"""
    db = get_persona_labels_db()
    assert len(db) == 3072, f"Expected 3072, got {len(db)}"


def test_all_persona_ids_parseable():
    """所有 persona_id 都能 parse_persona_id 成功。"""
    db = get_persona_labels_db()
    failed = []
    for pid in db.keys():
        parsed = parse_persona_id(pid)
        if parsed is None:
            failed.append(pid)
    assert not failed, f"{len(failed)} persona_id(s) failed to parse: {failed[:5]}"


def test_all_baselines_have_13_dims():
    """所有 baseline 13 dim 完整 + ∈ [0, 1]。"""
    db = get_persona_labels_db()
    bad = []
    for pid, entry in db.items():
        baseline = entry["baseline"]
        if set(baseline.keys()) != REQUIRED_DIMS:
            bad.append((pid, "dim_mismatch"))
            continue
        for dim, val in baseline.items():
            if not (0.0 <= val <= 1.0):
                bad.append((pid, f"{dim}={val}"))
                break
    assert not bad, f"{len(bad)} entry(s) bad: {bad[:5]}"


def test_all_confidence_valid():
    """所有 confidence ∈ {A, B, C, D}。"""
    db = get_persona_labels_db()
    valid = {"A", "B", "C", "D"}
    bad = [pid for pid, e in db.items() if e["confidence"] not in valid]
    assert not bad, f"{len(bad)} entry(s) bad confidence: {bad[:5]}"


def test_all_have_at_least_one_ref():
    """所有 entry 至少 1 ref (spec §3.4 强制要求)。"""
    db = get_persona_labels_db()
    no_ref = [pid for pid, e in db.items() if len(e["refs"]) < 1]
    assert not no_ref, f"{len(no_ref)} entry(s) without refs: {no_ref[:5]}"


def test_known_5_fixture_personas_in_kb():
    """5 fixture 核心 MBTI × 安全型 组合都在 KB (3.0A/3.0B regression baseline)。

    5 fixture labels 走的 force_state_from_labels 路径不依赖 persona_id, 但
    对应的 persona_id 也在 KB 里说明 16 MBTI × 安全型 schema 完整。
    """
    db = get_persona_labels_db()
    # INFP-A 安全型 → INFP-SE-EX-CO-PR
    # ISTJ-S 安全型 → ISTJ-SE-EX-CO-PR
    # ENTP-AV 回避型 → ENTP-AV-EX-CO-PR
    # ISFJ-D 混乱型 → ISFJ-DS-EX-CO-PR
    # ESTP-A 安全型 → ESTP-SE-EX-CO-PR
    expected = {
        "INFP-SE-EX-CO-PR",  # INFP-A
        "ISTJ-SE-EX-CO-PR",  # ISTJ-S
        "ENTP-AV-EX-CO-PR",  # ENTP-AV
        "ISFJ-DS-EX-CO-PR",  # ISFJ-D
        "ESTP-SE-EX-CO-PR",  # ESTP-A
    }
    missing = expected - set(db.keys())
    assert not missing, f"Missing fixture personas: {missing}"
