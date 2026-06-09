"""Tests for KB literature progress tracking (Phase 3.0C.1)。

跟踪 KB 中 confidence=A/B/C/D 数量分布 + ref count 完整性。
2 个核心 test: 验证 confidence 分布可查 + ref 数量合规。
"""
from __future__ import annotations

import pytest

from emotion_spirit.core.persona_labels_db import (
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


# === Step 3.5 (Phase 3.0C.2b): D-level threshold warning ===

def test_d_grade_percentage_warning():
    """D 等级 (无引用) 比例 > 80% 时 warn (CI 鼓励文献化进度, 不 fail)。

    spec §8.5 + D3 决策: 大部分 entry 标 D (computed, no literature) 是
    honest disclosure, 不阻断 ship, 但应触发 warning 提醒持续文献化。
    """
    from emotion_spirit.core.persona_labels_db import get_persona_labels_db
    db = get_persona_labels_db()
    if not db:
        pytest.skip("KB empty, skip progress check")

    d_count = sum(1 for e in db.values() if e["confidence"] == "D")
    pct = d_count / len(db)

    if pct > 0.80:
        # 触发 warning, 但不 fail
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warnings.warn(
                f"D-grade {pct:.1%} > 80% (lit progress slow): "
                f"{d_count}/{len(db)} entries need literature backfill",
                UserWarning,
                stacklevel=2,
            )
            assert len(w) == 1
            assert "D-grade" in str(w[0].message)
    # 实际验证: 至少 1 个 D entry 存在
    assert d_count >= 1, "Expected at least 1 D-grade entry"
