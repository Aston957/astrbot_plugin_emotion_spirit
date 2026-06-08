"""Tests for 3.0C backward compatibility (Phase 3.0C spec §5)。

3.0C 新增 persona_labels_db + force_state_from_persona_id, 必须**不**破坏:
1. 3.0A API: KnowledgeBase.compute_baseline_from_labels (5 label → 13 dim baseline)
2. 3.0B API: ForceDynamics.force_state_with_conscience (ConscienceTracker 集成)
3. 5 fixture labels (3.0A): INFP-A/ISTJ-S/ENTP-AV/ISFJ-D/ESTP-A
   - 4/5 用 3.0A 旧 label (e.g. "压抑型" "攻击型"), 不属于 3.0C persona_id 命名空间
   - spec §5.1 隔离: 5 fixture 走 force_state_from_labels (3.0A), 跟 3.0C 命名空间分离
4. 3.0B ConscienceTracker: force_state_from_persona_id_with_conscience 桥接
"""
from __future__ import annotations

import pytest

from emotion_spirit.knowledge import KnowledgeBase
from emotion_spirit.force_dynamics import ForceDynamics
from emotion_spirit.persona_labels_db import (
    force_state_from_persona_id,
    force_state_from_persona_id_with_conscience,
    get_baseline_for_persona,
    register_persona_baseline,
    reset_cache,
)


# === Fixtures ===

@pytest.fixture(autouse=True)
def _reset():
    """每个 test 前重置 in-memory cache + stats."""
    reset_cache()
    yield
    reset_cache()


def _make_baseline(centers: dict[str, float] | None = None) -> dict[str, float]:
    """Generate 13-dim baseline (跟 3.0A KnowledgeBase 兼容)."""
    base = {dim: 0.5 for dim in [
        "warmth_bias", "boundary_permeability", "relational_gravity",
        "expression_drive", "gossip_tendency", "directness",
        "inner_coherence", "patience", "intimacy_pull",
        "curiosity", "perception_acuity", "relational_autonomy", "exploration_openness",
    ]}
    if centers:
        base.update(centers)
    return base


# === 3.0A compat: KnowledgeBase.compute_baseline_from_labels ===

def test_compute_baseline_from_labels_still_works():
    """3.0A API 不破坏: 5 标签 → 13 dim baseline."""
    labels = {
        "mbti": "INFP",
        "attachment": "安全型",
        "emotion_style": "表达型",
        "conflict_style": "合作型",
        "time_focus": "活在当下",
    }
    baseline = KnowledgeBase.compute_baseline_from_labels(labels)
    assert "curiosity" in baseline
    assert "warmth_bias" in baseline
    assert len(baseline) == 13
    for dim, val in baseline.items():
        assert 0.0 <= val <= 1.0, f"{dim} = {val} not in [0, 1]"


# === 3.0B compat: ForceDynamics.force_state_with_conscience ===

def test_force_state_with_conscience_still_works():
    """3.0B API 不破坏: ForceDynamics 实例方法 force_state_with_conscience 仍可用."""
    personality = _make_baseline({"curiosity": 0.85})
    fs = ForceDynamics().force_state_with_conscience(
        personality=personality, conscience_tracker=None,
    )
    assert fs is not None
    # 3 权重 sum=1.0
    assert abs(fs.natural + fs.social + fs.individual - 1.0) < 1e-9


def test_force_state_with_conscience_with_tracker():
    """3.0B API: 真 ConscienceTracker 实例不破坏。"""
    from emotion_spirit.superego import ConscienceTracker
    tracker = ConscienceTracker()
    personality = _make_baseline({"curiosity": 0.85})
    fs = ForceDynamics().force_state_with_conscience(
        personality=personality, conscience_tracker=tracker,
    )
    assert fs is not None
    # pressure=0 (初始) → 跟没 tracker 等价
    assert abs(fs.natural + fs.social + fs.individual - 1.0) < 1e-9


# === 5 fixture labels (3.0A) regression ===

def test_5_fixture_labels_still_works():
    """5 fixture labels (3.0A) 不破坏 — regression。"""
    from tests.fixture_labels import ALL_5_FIXTURE_LABELS
    for labels in ALL_5_FIXTURE_LABELS:
        baseline = KnowledgeBase.compute_baseline_from_labels(labels)
        assert 13 == len(baseline), f"{labels.get('mbti', '?')}: expected 13 dims, got {len(baseline)}"
        for dim, val in baseline.items():
            assert 0.0 <= val <= 1.0, f"{labels.get('mbti', '?')}/{dim} = {val}"


def test_5_fixture_labels_have_diverse_baselines():
    """5 fixture 产生 5 个不同的 baseline (regression sanity, 避免 27-sum 退化成同值)。"""
    from tests.fixture_labels import ALL_5_FIXTURE_LABELS
    baselines = [
        KnowledgeBase.compute_baseline_from_labels(labels)
        for labels in ALL_5_FIXTURE_LABELS
    ]
    # 5 baseline 不全相等
    assert len({tuple(sorted(b.items())) for b in baselines}) >= 3, (
        "5 fixture baselines 太相似, 27-sum 可能退化了"
    )


# === 3.0B → 3.0C bridge: force_state_from_persona_id_with_conscience ===

def test_3c_bridge_accepts_conscience_tracker():
    """3.0C 便捷方法接受 ConscienceTracker 实例, 不破坏 3.0B 既有类型。"""
    from emotion_spirit.superego import ConscienceTracker
    register_persona_baseline("INFP-AV-EX-CO-PR", _make_baseline())
    tracker = ConscienceTracker()
    fs = force_state_from_persona_id_with_conscience("INFP-AV-EX-CO-PR", tracker)
    assert fs is not None
    assert abs(fs.natural + fs.social + fs.individual - 1.0) < 1e-9


def test_3c_bridge_accepts_float():
    """3.0C 便捷方法接受 float 标量。"""
    register_persona_baseline("INFP-AV-EX-CO-PR", _make_baseline())
    fs = force_state_from_persona_id_with_conscience("INFP-AV-EX-CO-PR", 0.5)
    assert fs is not None


def test_3c_bridge_accepts_none():
    """3.0C 便捷方法接受 None (压力=0)。"""
    register_persona_baseline("INFP-AV-EX-CO-PR", _make_baseline())
    fs = force_state_from_persona_id_with_conscience("INFP-AV-EX-CO-PR", None)
    assert fs is not None


def test_3c_bridge_rejects_invalid_type():
    """3.0C 便捷方法拒绝非法类型 (TypeError, 3.0B 偏离 E 防御)。"""
    with pytest.raises(TypeError, match="conscience_tracker"):
        force_state_from_persona_id_with_conscience("INFP-AV-EX-CO-PR", "not_a_tracker")


# === KB 27-sum fallback: 跟 3.0A 27-sum 等价 (3.0A 算法不破坏) ===

def test_force_state_27sum_fallback_matches_3a_when_kb_miss(tmp_path, monkeypatch):
    """3.0C path B (KB miss → 27-sum) 跟 3.0A 直接 27-sum 等价 — 3.0A 行为不破坏。

    强制 KB 失效 (DB_PATH → 不存在), 走 27-sum fallback 路径, 验证 fallback 跟
    3.0A `KnowledgeBase.compute_baseline_from_labels` 严格一致 (3.0A 算法不破坏)。
    """
    from tests.fixture_labels import INFP_A_LABELS
    # 强制 KB 失效
    monkeypatch.setattr(
        "emotion_spirit.persona_labels_db.DB_PATH",
        tmp_path / "nope.json",
    )
    reset_cache()  # 重置以读到新 path
    # 3.0A 直接调: 走 27-sum
    fs_3a = ForceDynamics().compute(
        personality=KnowledgeBase.compute_baseline_from_labels(INFP_A_LABELS)
    )
    # 3.0C 调 parse OK 但 KB miss → 27-sum (跟 3.0A 同路径)
    fs_3c = force_state_from_persona_id("INFP-SE-EX-CO-PR")
    # 27-sum 等价
    assert abs(fs_3a.natural - fs_3c.natural) < 1e-9, (
        f"3.0C 27-sum fallback 跟 3.0A 不一致: "
        f"fs_3a.natural={fs_3a.natural}, fs_3c.natural={fs_3c.natural}"
    )
    assert abs(fs_3a.social - fs_3c.social) < 1e-9
    assert abs(fs_3a.individual - fs_3c.individual) < 1e-9
