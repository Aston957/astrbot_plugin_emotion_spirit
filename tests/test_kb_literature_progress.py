"""Tests for KB literature progress tracking (Phase 3.0C.1)。

跟踪 KB 中 confidence=A/B/C/D 数量分布 + ref count 完整性。
2 个核心 test: 验证 confidence 分布可查 + ref 数量合规。
"""
from __future__ import annotations

import pytest

from emotion_spirit.persona_labels_db import (
    REQUIRED_DIMS,
    get_persona_labels_db,
    get_persona_entry,
    register_persona_baseline,
    reset_cache,
)


def _make_baseline() -> dict[str, float]:
    return {dim: 0.5 for dim in REQUIRED_DIMS}


@pytest.fixture(autouse=True)
def _reset():
    reset_cache()
    yield
    reset_cache()


def test_confidence_distribution_tracking():
    """confidence A/B/C/D 数量分布可查。

    验证: 注册 3 个 A + 2 个 C 后, 计数正确。
    """
    for i in range(3):
        register_persona_baseline(
            f"P{i}-XX-YY-WW-VV", _make_baseline(), confidence="A"
        )
    for i in range(2):
        register_persona_baseline(
            f"Q{i}-XX-YY-WW-VV", _make_baseline(), confidence="C"
        )

    db = get_persona_labels_db()
    counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for entry in db.values():
        counts[entry["confidence"]] += 1

    assert counts["A"] == 3, f"A count={counts['A']} (expected 3)"
    assert counts["C"] == 2, f"C count={counts['C']} (expected 2)"
    assert counts["B"] == 0
    assert counts["D"] == 0


def test_refs_count_per_entry():
    """每个 entry 的 refs 数量可统计, 注册时可多 ref 存储。

    验证: 注册 1 个 entry 配 2 个 ref, 读出时一致。
    """
    refs = [
        {"dim": "curiosity", "source_type": "16p", "citation": "16p/infp"},
        {"dim": "directness", "source_type": "academic", "citation": "Furnham 1996"},
    ]
    register_persona_baseline(
        "INFP-AV-EX-CO-PR",
        _make_baseline(),
        confidence="A",
        refs=refs,
    )
    entry = get_persona_entry("INFP-AV-EX-CO-PR")
    assert len(entry["refs"]) == 2
    assert entry["refs"][0]["dim"] == "curiosity"
    assert entry["refs"][1]["source_type"] == "academic"
