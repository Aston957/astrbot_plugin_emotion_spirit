"""Tests for persona_labels_db loader (Phase 3.0C.1)。

覆盖范围 (11 tests):
- Loader API: load / get / register / bulk / export / list / stats / reset
- 校验: confidence / missing dims / range
- 4 组合 stub 加载验证 (Step 1.3 集成)
- N-type curiosity 显著 (INFP/ENTP > 0.8) vs S-type (ISTJ < 0.5)
"""
from __future__ import annotations

import pytest

from emotion_spirit.persona_labels_db import (
    REQUIRED_DIMS,
    DB_PATH,
    get_persona_labels_db,
    get_baseline_for_persona,
    get_persona_entry,
    register_persona_baseline,
    bulk_register_persona_baselines,
    export_persona_labels_db,
    list_persona_ids,
    get_kb_stats,
    reset_cache,
)


# === Helpers ===

def _make_baseline(centers: dict[str, float] | None = None) -> dict[str, float]:
    """Generate 13-dim baseline 全部 0.5, 允许 overrides."""
    base = {dim: 0.5 for dim in REQUIRED_DIMS}
    if centers:
        base.update(centers)
    return base


@pytest.fixture(autouse=True)
def _reset():
    """每个 test 前/后重置 in-memory cache, 防止测试污染。"""
    reset_cache()
    yield
    reset_cache()


# === Loader API tests ===

def test_get_persona_labels_db_empty_when_no_json(tmp_path, monkeypatch):
    """KB JSON 不存在 → 返空 dict, 不抛错 (log warning)。

    路径覆盖: monkeypatch 改 DB_PATH 指向 tmp_path/nope.json (不存在)。
    """
    monkeypatch.setattr(
        "emotion_spirit.persona_labels_db.DB_PATH", tmp_path / "nope.json"
    )
    db = get_persona_labels_db()
    assert db == {}


def test_register_and_get_baseline():
    """注册 + 查找 baseline dict 一致。"""
    baseline = _make_baseline({"curiosity": 0.85})
    register_persona_baseline(
        "INFP-AV-EX-CO-PR", baseline, confidence="A"
    )
    result = get_baseline_for_persona("INFP-AV-EX-CO-PR")
    assert result == baseline
    assert result["curiosity"] == 0.85


def test_get_baseline_returns_none_for_missing():
    """未注册 persona_id → 返 None (不抛错)。"""
    assert get_baseline_for_persona("XXXX-YY-ZZ-WW-VV") is None


def test_register_validates_confidence():
    """非 A/B/C/D → ValueError。"""
    with pytest.raises(ValueError, match="confidence"):
        register_persona_baseline(
            "INFP-AV-EX-CO-PR", _make_baseline(), confidence="X"
        )


def test_register_validates_missing_dims():
    """baseline 缺 dim → ValueError。"""
    incomplete = {"warmth_bias": 0.5}  # 只 1 dim
    with pytest.raises(ValueError, match="missing dims"):
        register_persona_baseline("INFP-AV-EX-CO-PR", incomplete)


def test_register_validates_range():
    """baseline 超出 [0, 1] → ValueError。"""
    bad = _make_baseline({"curiosity": 1.5})  # > 1.0
    with pytest.raises(ValueError, match=r"not in \[0, 1\]"):
        register_persona_baseline("INFP-AV-EX-CO-PR", bad)


def test_bulk_register():
    """批量注册多个 entry。"""
    entries = [
        {
            "persona_id": "INFP-AV-EX-CO-PR",
            "baseline": _make_baseline(),
            "confidence": "A",
        },
        {
            "persona_id": "ISTJ-SE-IH-CO-PR",
            "baseline": _make_baseline(),
            "confidence": "B",
        },
    ]
    bulk_register_persona_baselines(entries)
    db = get_persona_labels_db()
    assert len(db) == 2
    assert "INFP-AV-EX-CO-PR" in db
    assert "ISTJ-SE-IH-CO-PR" in db


def test_export_and_reload(tmp_path, monkeypatch):
    """导出 JSON → 重置 cache → 重新加载, 数据一致。"""
    out = tmp_path / "exported.json"
    monkeypatch.setattr("emotion_spirit.persona_labels_db.DB_PATH", out)
    register_persona_baseline("INFP-AV-EX-CO-PR", _make_baseline())
    export_persona_labels_db()
    assert out.exists()

    # 重置 cache, 强制重新加载
    reset_cache()
    db = get_persona_labels_db()
    assert "INFP-AV-EX-CO-PR" in db
    assert db["INFP-AV-EX-CO-PR"]["confidence"] == "D"  # 默认 confidence


def test_list_persona_ids_sorted():
    """list_persona_ids 返排序列表 (sorted)。"""
    for pid in ["ZZZ-XX-YY-WW-VV", "AAA-BB-CC-DD-EE", "MMM-NN-OO-PP-QQ"]:
        register_persona_baseline(pid, _make_baseline())
    ids = list_persona_ids()
    assert ids == sorted(ids)
    assert ids[0] == "AAA-BB-CC-DD-EE"
    assert ids[-1] == "ZZZ-XX-YY-WW-VV"


def test_get_kb_stats():
    """stats 计数器工作: register_count +1/次。"""
    assert get_kb_stats()["register_count"] == 0
    register_persona_baseline("INFP-AV-EX-CO-PR", _make_baseline())
    assert get_kb_stats()["register_count"] == 1
    register_persona_baseline("ISTJ-SE-IH-CO-PR", _make_baseline())
    assert get_kb_stats()["register_count"] == 2


def test_get_persona_entry_returns_full():
    """get_persona_entry 返完整 entry (含 confidence + refs), 不是 baseline dict。"""
    refs = [{"dim": "curiosity", "source_type": "16p", "citation": "16p/infp"}]
    register_persona_baseline(
        "INFP-AV-EX-CO-PR",
        _make_baseline(),
        confidence="B",
        refs=refs,
        notes="test entry",
    )
    entry = get_persona_entry("INFP-AV-EX-CO-PR")
    assert entry["confidence"] == "B"
    assert entry["refs"] == refs
    assert entry["notes"] == "test entry"
    assert entry["baseline"]["curiosity"] == 0.5
    assert entry["persona_id"] == "INFP-AV-EX-CO-PR"


# === Step 1.3 integration: 4 组合 stub 加载验证 ===

def test_kb_json_loads_4_stub_entries():
    """默认 KB JSON (4 stub) 加载成功, 4 个 entry 都在。"""
    # 不 monkeypatch DB_PATH, 走默认路径 (4 stub JSON)
    db = get_persona_labels_db()
    assert len(db) == 4
    expected = {"INFP-SE-EX-CO-PR", "ISTJ-SE-EX-CO-PR", "ENTP-SE-EX-CO-PR", "ESTP-SE-EX-CO-PR"}
    assert set(db.keys()) == expected


def test_n_type_curiosity_high_s_type_low():
    """N-type (INFP/ENTP) curiosity > 0.8, S-type (ISTJ) curiosity < 0.5。

    验证 16p 特色, 不全 0.5 (spec §3.1 N vs S dim 显著)。
    """
    infp = get_baseline_for_persona("INFP-SE-EX-CO-PR")
    entp = get_baseline_for_persona("ENTP-SE-EX-CO-PR")
    istj = get_baseline_for_persona("ISTJ-SE-EX-CO-PR")
    assert infp["curiosity"] >= 0.80, f"INFP curiosity={infp['curiosity']} (expect ≥0.80)"
    assert entp["curiosity"] >= 0.80, f"ENTP curiosity={entp['curiosity']} (expect ≥0.80)"
    assert istj["curiosity"] <= 0.50, f"ISTJ curiosity={istj['curiosity']} (expect ≤0.50)"


def test_all_stubs_have_valid_schema():
    """4 stub entry 全部 13 dim 完整 + ∈ [0, 1] + confidence 合法。"""
    db = get_persona_labels_db()
    valid_conf = {"A", "B", "C", "D"}
    for pid, entry in db.items():
        assert entry["confidence"] in valid_conf, f"{pid}: bad confidence"
        assert set(entry["baseline"].keys()) == REQUIRED_DIMS, f"{pid}: dim set mismatch"
        for dim, val in entry["baseline"].items():
            assert 0.0 <= val <= 1.0, f"{pid}/{dim}={val} out of [0,1]"
        assert len(entry["refs"]) >= 1, f"{pid}: no refs"
