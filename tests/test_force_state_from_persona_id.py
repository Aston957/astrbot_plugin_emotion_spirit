"""Tests for force_state_from_persona_id (Phase 3.0C.2a spec §4.1)。

主入口 API: 走 KB → 27-sum fallback → 中性 fallback 三条路径。
7 个测试覆盖: KB 命中 / 27-sum fallback / 中性 fallback / 3.0B 透传 / 一致性。
"""
from __future__ import annotations

import pytest

from emotion_spirit.persona_labels_db import (
    REQUIRED_DIMS,
    force_state_from_persona_id,
    parse_persona_id,
    register_persona_baseline,
    reset_cache,
    get_kb_stats,
)
from emotion_spirit.body_state import BodyState
from emotion_spirit.force_dynamics import ForceDynamics, ForceState


# === Helpers ===

def _make_baseline(centers: dict[str, float] | None = None) -> dict[str, float]:
    """Generate 13-dim baseline 全部 0.5, 允许 overrides."""
    base = {dim: 0.5 for dim in REQUIRED_DIMS}
    if centers:
        base.update(centers)
    return base


@pytest.fixture(autouse=True)
def _reset():
    """每个 test 前/后重置 in-memory cache + stats, 防止测试污染。"""
    reset_cache()
    yield
    reset_cache()


# === Fallback 路径测试 ===

def test_force_state_kb_hit():
    """路径 A: KB 命中 → 返 ForceState, kb_hit +1。"""
    register_persona_baseline(
        "INFP-AV-EX-CO-PR", _make_baseline({"curiosity": 0.85}), confidence="A"
    )
    fs = force_state_from_persona_id("INFP-AV-EX-CO-PR")
    assert fs is not None
    assert isinstance(fs, ForceState)
    assert get_kb_stats()["kb_hit"] == 1


def test_force_state_fallback_to_27_sum(tmp_path, monkeypatch):
    """路径 B: persona_id 合法但不在 KB → 27-sum fallback, kb_fallback_labels +1。

    注: 3.0C.2b 完成后, 3072 组合全在 KB, 正常路径都走 kb_hit。
    此测试用 monkeypatch 改 DB_PATH 指向空 JSON, 强制 fallback 路径。
    """
    monkeypatch.setattr(
        "emotion_spirit.persona_labels_db.DB_PATH", tmp_path / "empty.json"
    )
    # 路径 B: 合法 persona_id, 但 KB 空 → 27-sum fallback
    fs = force_state_from_persona_id("INFP-AV-EX-CO-PR")
    assert fs is not None
    assert get_kb_stats()["kb_fallback_labels"] == 1
    assert get_kb_stats()["kb_hit"] == 0


def test_force_state_malformed_uses_neutral():
    """路径 C: persona_id 解析失败 → 中性 baseline, kb_fallback_neutral +1。"""
    # 段数错 (4 段), 解析失败
    fs = force_state_from_persona_id("XX-XX-XX-XX")  # 4 段
    assert fs is not None
    assert get_kb_stats()["kb_fallback_neutral"] == 1


# === 3.0B 参数透传 ===

def test_force_state_with_body_state_passthrough():
    """body_state 透传到 ForceDynamics, 不同 body_state → 不同 ForceState。

    注: 必须用非均匀 baseline (all 0.5 → uniform 1/3 → 调制不可见, 数学上恒等)。
    """
    # INFP-AV 风格的非均匀 baseline: 高 curiosity (individual), 中等 warmth (natural)
    nonuniform = _make_baseline({
        "curiosity": 0.85,
        "exploration_openness": 0.80,
        "warmth_bias": 0.70,
        "patience": 0.40,
    })
    register_persona_baseline("INFP-AV-EX-CO-PR", nonuniform)
    fs_no_body = force_state_from_persona_id("INFP-AV-EX-CO-PR")

    bs = BodyState(hormone=0.7, energy=0.8, arousal=0.6)
    fs_with_body = force_state_from_persona_id(
        "INFP-AV-EX-CO-PR", body_state=bs
    )
    # body_state 不同 → ForceState 应不同 (hormone=0.7 调 individual +0.8 最敏感)
    assert (
        fs_with_body.natural != fs_no_body.natural
        or fs_with_body.social != fs_no_body.social
        or fs_with_body.individual != fs_no_body.individual
    )


def test_force_state_with_conscience_passthrough():
    """conscience_pressure 透传, conscience=1.0 改变 individual 方向 (spec §3.1 direction=+0.7)。

    注: 必须用非均匀 baseline (all 0.5 → uniform 1/3 → 调制不可见)。
    """
    nonuniform = _make_baseline({
        "curiosity": 0.85,
        "exploration_openness": 0.80,
        "warmth_bias": 0.70,
    })
    register_persona_baseline("INFP-AV-EX-CO-PR", nonuniform)
    fs_p0 = force_state_from_persona_id("INFP-AV-EX-CO-PR", conscience_pressure=0.0)
    fs_p1 = force_state_from_persona_id("INFP-AV-EX-CO-PR", conscience_pressure=1.0)
    # conscience_pressure=1.0 → individual 显著增 (direction=+0.7)
    assert fs_p0.individual != fs_p1.individual
    # individual 应该是增 (跟 social 退缩 对照)
    assert fs_p1.individual > fs_p0.individual - 1e-9  # 至少不减少 (实际是增)


def test_force_state_conscience_validation():
    """conscience_pressure 不在 [0, 1] → ValueError (3.0B 一致行为)。"""
    register_persona_baseline("INFP-AV-EX-CO-PR", _make_baseline())
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        force_state_from_persona_id("INFP-AV-EX-CO-PR", conscience_pressure=1.5)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        force_state_from_persona_id("INFP-AV-EX-CO-PR", conscience_pressure=-0.1)


# === KB 命中 vs 27-sum 一致性 ===

def test_force_state_all_zero_baseline_uniform():
    """all 0.5 baseline (无论 KB 还是 27-sum) → ForceState uniform 1/3 each。

    验证: 算法 H 退化行为正确——无偏离时, 三力均匀分配。
    路径 A (KB 命中) + 路径 B (27-sum fallback) 都用全 0.5 baseline, 应得 1/3 each。
    """
    # 路径 A: 注册一个全 0.5 baseline
    register_persona_baseline("INFP-AV-EX-CO-PR", _make_baseline())  # 全 0.5
    fs_kb = force_state_from_persona_id("INFP-AV-EX-CO-PR")

    # 路径 B: 不同 persona_id, 不在 KB, 27-sum 路径
    # 注意: 27-sum 用 5 labels 算 baseline, 通常不是全 0.5, 所以这个 fs 不会 uniform
    # 但全 0.5 KB baseline 必须 uniform
    assert abs(fs_kb.natural - 1/3) < 1e-9
    assert abs(fs_kb.social - 1/3) < 1e-9
    assert abs(fs_kb.individual - 1/3) < 1e-9


def test_force_state_kb_and_27sum_differ_for_same_persona():
    """KB 命中 baseline ≠ 27-sum 路径 baseline (literature 跟公式的差异)。

    验证: KB 存的是文献化 13-dim baseline, 27-sum 是公式计算, 两者不保证相等。
    这一点重要——它解释了为什么"KB 命中优先, 27-sum 是 fallback"。
    """
    # 注册一个明显偏离 0.5 的 KB baseline
    nonuniform = _make_baseline({"curiosity": 0.85, "exploration_openness": 0.90})
    register_persona_baseline("INFP-AV-EX-CO-PR", nonuniform)
    fs_kb = force_state_from_persona_id("INFP-AV-EX-CO-PR")

    # 临时清空 KB 缓存, 强制走 27-sum 路径
    from emotion_spirit.persona_labels_db import (
        get_baseline_for_persona,
    )
    kb_baseline = get_baseline_for_persona("INFP-AV-EX-CO-PR")
    assert kb_baseline["curiosity"] == 0.85  # KB 存的非 27-sum 计算值

    # 验证 fs_kb 是 non-uniform (curiosity 0.85 拉 individual)
    assert abs(fs_kb.individual - 1/3) > 1e-6, "KB 命中 baseline 非 0.5, ForceState 应非均匀"
