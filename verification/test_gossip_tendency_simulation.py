"""Tests for gossip_tendency simulation (Phase C, Task C3 — P0-2a 仿真验证)。

5 persona × 8 scenarios 仿真, 验证 gossip_tendency 维度真的在 drift 中起作用。

本测试目标:
  1. 5 persona gossip_tendency baseline 在 HEXACO 预测区间, 跟 KB 一致。
  2. DriftSimulator(labels=...) 走通用化入口, baseline 来自 compute_baseline_from_labels。
  3. gossip 话题 → gossip_tendency 上升。
  4. 中性话题 → gossip_tendency 不漂移。
  5. simulation_runner 报告字段包含 gossip_tendency。
  6. 5 persona 全跑 gossip_topic_heavy, 验证各自方向。

Phase 3.0A (Task 2): DriftSimulator 改 B 单入口 (labels= only),
5 persona fixture labels 来自 tests/fixture_labels.py (KB.PERSONA_BASELINES 已删)。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 让 verification/ 模块能 import, 且 emotion_spirit/ + tests/ 也能 import
# 项目结构: <root>/{tests, verification, emotion_spirit, conftest.py (root), main.py}
_VERIFICATION_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _VERIFICATION_DIR.parent
_TESTS_DIR = _ROOT_DIR / "tests"
sys.path.insert(0, str(_VERIFICATION_DIR))
sys.path.insert(0, str(_ROOT_DIR))
sys.path.insert(0, str(_TESTS_DIR))
# tests/ 是 package (有 __init__.py), fixture_labels.py 是普通 module, 直接 import
from fixture_labels import (  # noqa: E402
    INFP_A_LABELS, ISTJ_S_LABELS, ENTP_AV_LABELS, ISFJ_D_LABELS, ESTP_A_LABELS,
    ALL_5_FIXTURE_LABELS, ALL_5_FIXTURES,
)


# ═══ 1. 5 persona baseline 跟 KB 一致 (HEXACO 预测区间) ═══

def test_5_persona_gossip_tendency_baselines_in_kb():
    """5 persona gossip_tendency baseline 在合理区间 (HEXACO 预测 + 公式计算一致)。

    Phase 3.0A 重要变化: KB.PERSONA_BASELINES 已删, 5 persona baseline 改走
    compute_baseline_from_labels 公式 (5 标签等权, 见 tests/fixture_labels.py)。
    5 persona fixture labels 是后缀规则"猜的" (-A 安全型, -AV 回避型, -S 稳定, -D 压抑),
    未来 Phase 3.0C 文献化取代。

    当前 5 persona gossip_tendency 公式输出 (baseline 集中在 0.5 附近,
    因为 placeholder 标签区分度有限): 0.45-0.55 区间。
    """
    from emotion_spirit.utils import KnowledgeBase
    # 5 persona gossip_tendency 公式输出范围 (placeholder labels)
    # 实测: INFP-A 0.4975, ISTJ-S 0.4750, ENTP-AV 0.5350, ISFJ-D 0.5075, ESTP-A 0.5450
    # 留 ±0.10 tolerance 应对 fixture labels 未来微调
    expected_ranges = {
        "INFP-A": (0.40, 0.60),    # 中等 (placeholder)
        "ISTJ-S": (0.40, 0.60),    # placeholder (旧 ISTJ-S 极低, 现被公式均值化)
        "ENTP-AV": (0.40, 0.60),   # placeholder
        "ISFJ-D": (0.40, 0.60),    # placeholder
        "ESTP-A": (0.40, 0.60),    # placeholder
    }
    for persona_id, labels in ALL_5_FIXTURES:
        gt = KnowledgeBase.compute_baseline_from_labels(labels)["gossip_tendency"]
        lo, hi = expected_ranges[persona_id]
        assert lo <= gt <= hi, (
            f"{persona_id}: gossip_tendency {gt} 不在 [{lo}, {hi}]"
        )


# ═══ 2. DriftSimulator(labels=...) 走通用化入口 ═══

def test_simulator_reads_knowledge_base_for_persona_id():
    """DriftSimulator(labels=...) 走 compute_baseline_from_labels (Phase 3.0A 通用化)。"""
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(labels=INFP_A_LABELS)
    baseline = sim.get_initial_personality()
    # 13 维 (含 gossip_tendency)
    assert "gossip_tendency" in baseline
    assert "warmth_bias" in baseline
    assert "expression_drive" in baseline
    # gossip_tendency 应该是公式算的值 (INFP-A ≈ 0.4975), 不是 0
    assert baseline["gossip_tendency"] > 0
    # 跟 KB 公式一致
    from emotion_spirit.utils import KnowledgeBase
    kb_gt = KnowledgeBase.compute_baseline_from_labels(INFP_A_LABELS)["gossip_tendency"]
    assert baseline["gossip_tendency"] == kb_gt


def test_simulator_labels_entry_works():
    """B 决策: DriftSimulator(labels=...) 是唯一入口, baseline 走 KB 公式。"""
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(labels=INFP_A_LABELS)
    # 旧 flow 仍工作
    sim.step()
    current = sim.current
    assert "deep" in current
    assert "surface" in current
    # 13 维 (compute_baseline_from_labels 含 gossip_tendency)
    assert "gossip_tendency" in current["surface"]


# ═══ 3. gossip 话题 → gossip_tendency 上升 ═══

def test_gossip_drift_under_repeated_gossip_topics():
    """重复 gossip 话题 → gossip_tendency 上升。"""
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(labels=ISTJ_S_LABELS)
    initial_gt = sim.get_initial_personality()["gossip_tendency"]

    # 20 步 gossip 话题
    for _ in range(20):
        sim.process_message(topic="gossip", content="X 说 Y 的八卦")
    sim.run_drift_check()
    final_gt = sim.get_current_personality()["gossip_tendency"]
    # ISTJ-S baseline ≈ 0.32, 20 步后应显著上升
    assert final_gt > initial_gt, (
        f"gossip_tendency 应该有上升, 实际 {initial_gt} -> {final_gt}"
    )
    # 至少 +0.10 (20 步 × 0.01)
    assert final_gt - initial_gt >= 0.10


def test_gossip_drift_for_high_gossip_persona_no_clamp():
    """高 gossip baseline (ENTP-AV ~0.65) 经过 gossip, B 决策: 不 clamp, 允许 > 1.0。"""
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(labels=ENTP_AV_LABELS)
    initial_gt = sim.get_initial_personality()["gossip_tendency"]

    for _ in range(100):
        sim.process_message(topic="gossip", content="X 说 Y 的八卦")
    sim.run_drift_check()
    final_gt = sim.get_current_personality()["gossip_tendency"]
    # B 决策: 不 clamp, cumulative drift 允许 > 1.0
    # baseline ~0.65 + 100×0.01 = ~1.65
    assert final_gt > 1.0, f"B 决策: gossip 应允许 > 1.0, 实际 {final_gt}"
    # 应该有上升
    assert final_gt > initial_gt


# ═══ 4. 中性话题 → gossip_tendency 不漂移 ═══

def test_gossip_does_not_drift_under_neutral_topics():
    """中性话题 → gossip_tendency 不漂移。"""
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(labels=ENTP_AV_LABELS)
    initial_gt = sim.get_initial_personality()["gossip_tendency"]

    for _ in range(20):
        sim.process_message(topic="neutral", content="今天天气不错")
    sim.run_drift_check()
    final_gt = sim.get_current_personality()["gossip_tendency"]
    # 中性话题不应触发 gossip_tendency 漂移
    assert abs(final_gt - initial_gt) < 0.05, (
        f"中性话题不应漂移 gossip_tendency, 实际 {initial_gt} -> {final_gt}"
    )


# ═══ 5. simulation_runner.run_simulation 包含 gossip_tendency 字段 ═══

def test_simulation_runner_includes_gossip_tendency():
    """simulation_runner.run_simulation 报告字段包含 gossip_tendency。"""
    from verification.simulation_runner import run_simulation
    result = run_simulation(
        labels=ESTP_A_LABELS, scenario="gossip_topic_heavy", steps=10,
        persona_id="ESTP-A",
    )
    assert "personality" in result
    assert "gossip_tendency" in result["personality"]
    assert "trajectory" in result
    assert len(result["trajectory"]) > 0
    for step in result["trajectory"]:
        assert "gossip_tendency" in step


# ═══ 6. simulate_persona 模块函数 ═══

def test_simulate_persona_function():
    """simulate_persona 5 persona × gossip_topic_heavy, 全部应有 gossip_tendency drift。"""
    from verification.drift_simulator import simulate_persona
    for persona_id, labels in ALL_5_FIXTURES:
        result = simulate_persona(
            labels=labels, scenario="gossip_topic_heavy", steps=20,
            persona_id=persona_id,
        )
        assert result["persona_id"] == persona_id
        assert result["scenario"] == "gossip_topic_heavy"
        assert "gossip_tendency" in result["personality"]
        assert "trajectory" in result
        # gossip_topic_heavy 应该有 drift
        initial = result["trajectory"][0]["gossip_tendency"]
        final = result["personality"]["gossip_tendency"]
        assert final > initial, (
            f"{persona_id}: gossip_topic_heavy 应有 drift, 实际 {initial} -> {final}"
        )


def test_simulate_persona_neutral_scenario():
    """simulate_persona neutral_only scenario → gossip_tendency 不漂移。"""
    from verification.drift_simulator import simulate_persona
    result = simulate_persona(
        labels=ENTP_AV_LABELS, scenario="neutral_only", steps=20,
        persona_id="ENTP-AV",
    )
    initial = result["trajectory"][0]["gossip_tendency"]
    final = result["personality"]["gossip_tendency"]
    assert abs(final - initial) < 0.05


# ═══ 7. 5 persona gossip_tendency 一致 (DriftSimulator 读 KB 公式) ═══

def test_all_5_personas_gossip_tendency_via_simulator():
    """DriftSimulator(labels=X).get_initial_personality() 跟 KB 公式一致 (5 persona 全验证)。"""
    from verification.drift_simulator import DriftSimulator
    from emotion_spirit.utils import KnowledgeBase
    for persona_id, labels in ALL_5_FIXTURES:
        sim = DriftSimulator(labels=labels)
        sim_gt = sim.get_initial_personality()["gossip_tendency"]
        kb_gt = KnowledgeBase.compute_baseline_from_labels(labels)["gossip_tendency"]
        assert sim_gt == kb_gt, (
            f"{persona_id}: sim={sim_gt} vs kb={kb_gt} 不一致"
        )


# ═══ 8. get_current_personality 返回所有 13 维 (不只 gossip_tendency) ═══

def test_get_current_personality_has_all_13_dims():
    """get_current_personality 返回完整 13 维 (5 deep + 8 surface)。"""
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(labels=INFP_A_LABELS)
    initial = sim.get_initial_personality()
    current = sim.get_current_personality()
    # 5 deep
    for dim in ["expression_drive", "perception_acuity", "boundary_permeability",
                "inner_coherence", "relational_gravity"]:
        assert dim in initial
        assert dim in current
    # 8 surface
    for dim in ["warmth_bias", "directness", "curiosity", "patience",
                "intimacy_pull", "relational_autonomy", "exploration_openness",
                "gossip_tendency"]:
        assert dim in initial
        assert dim in current
    # 完整 13 维 set 断言 (无缺失, 无多余)
    expected_13 = {
        "expression_drive", "perception_acuity", "boundary_permeability",
        "inner_coherence", "relational_gravity",
        "warmth_bias", "directness", "curiosity", "patience",
        "intimacy_pull", "relational_autonomy", "exploration_openness",
        "gossip_tendency",
    }
    assert set(initial.keys()) == expected_13, (
        f"initial keys 偏离 13 维: 缺 {expected_13 - set(initial.keys())}, "
        f"多 {set(initial.keys()) - expected_13}"
    )
    assert set(current.keys()) == expected_13, (
        f"current keys 偏离 13 维: 缺 {expected_13 - set(current.keys())}, "
        f"多 {set(current.keys()) - expected_13}"
    )
