"""Tests for gossip_tendency simulation (Phase C, Task C3 — P0-2a 仿真验证)。

5 persona × 8 scenarios 仿真, 验证 gossip_tendency 维度真的在 drift 中起作用。

本测试目标:
  1. 5 persona gossip_tendency baseline 在 HEXACO 预测区间, 跟 KB 一致。
  2. DriftSimulator 可以按 persona_id 构造, 从 KnowledgeBase 读 baseline。
  3. gossip 话题 → gossip_tendency 上升。
  4. 中性话题 → gossip_tendency 不漂移。
  5. simulation_runner 报告字段包含 gossip_tendency。
  6. 5 persona 全跑 gossip_topic_heavy, 验证各自方向。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 让 verification/ 模块能 import, 且 emotion_spirit/ 也能 import
_VERIFICATION_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_VERIFICATION_DIR))
sys.path.insert(0, str(_VERIFICATION_DIR.parent))


# ═══ 1. 5 persona baseline 跟 KB 一致 (HEXACO 预测区间) ═══

def test_5_persona_gossip_tendency_baselines_in_kb():
    """5 persona gossip_tendency baseline 在 HEXACO 预测区间, 跟 KB 一致。

    HEXACO 预测区间依据:
      - H (Honesty-Humility) 低 → 高 gossip_tendency
      - E (Extraversion) 高 → 高 gossip_tendency
      - 5 persona gossip_tendency 全部在 HEXACO 预测区间
    """
    from emotion_spirit.knowledge import KnowledgeBase
    expected_ranges = {
        "INFP-A": (0.20, 0.40),    # 中等
        "ISTJ-S": (0.05, 0.25),    # 极低 (H 高 + E 低)
        "ENTP-AV": (0.55, 0.75),   # 高 (H 低 + E 高)
        "ISFJ-D": (0.30, 0.50),    # 中等
        "ESTP-A": (0.55, 0.80),    # 高 (E 高 + 行动导向)
    }
    for persona, (lo, hi) in expected_ranges.items():
        gt = KnowledgeBase.get_persona_baseline(persona)["gossip_tendency"]
        assert lo <= gt <= hi, (
            f"{persona}: gossip_tendency {gt} 不在 [{lo}, {hi}]"
        )


# ═══ 2. DriftSimulator 按 persona_id 构造, 读 KB ═══

def test_simulator_reads_knowledge_base_for_persona_id():
    """drift_simulator 读 KnowledgeBase.PERSONA_BASELINES (不读旧 label_mapper)。"""
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(persona_id="INFP-A")
    baseline = sim.get_initial_personality()
    # 13 维 (含 gossip_tendency)
    assert "gossip_tendency" in baseline
    assert "warmth_bias" in baseline
    assert "expression_drive" in baseline
    # gossip_tendency 应该是 KB 值 (0.30 for INFP-A), 不是 0
    assert baseline["gossip_tendency"] > 0
    # 跟 KB 一致
    from emotion_spirit.knowledge import KnowledgeBase
    kb_gt = KnowledgeBase.get_persona_baseline("INFP-A")["gossip_tendency"]
    assert baseline["gossip_tendency"] == kb_gt


def test_simulator_legacy_labels_still_works():
    """旧 API: DriftSimulator(initial_labels=...) 仍可用 (向后兼容)。"""
    from verification.drift_simulator import DriftSimulator
    labels = {
        "mbti": "INFP", "attachment": "安全型",
        "emotion_style": "表达型", "conflict_style": "合作型",
        "time_focus": "活在当下",
    }
    sim = DriftSimulator(initial_labels=labels)
    # 旧 flow 仍工作
    sim.step()
    current = sim.current
    assert "deep" in current
    assert "surface" in current
    # 13 维 (旧 _BASELINE 含 gossip_tendency)
    assert "gossip_tendency" in current["surface"]


# ═══ 3. gossip 话题 → gossip_tendency 上升 ═══

def test_gossip_drift_under_repeated_gossip_topics():
    """重复 gossip 话题 → gossip_tendency 上升。"""
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(persona_id="ISTJ-S")
    initial_gt = sim.get_initial_personality()["gossip_tendency"]

    # 20 步 gossip 话题
    for _ in range(20):
        sim.process_message(topic="gossip", content="X 说 Y 的八卦")
    sim.run_drift_check()
    final_gt = sim.get_current_personality()["gossip_tendency"]
    # ISTJ-S baseline 0.15, 20 步后应显著上升
    assert final_gt > initial_gt, (
        f"gossip_tendency 应该有上升, 实际 {initial_gt} -> {final_gt}"
    )
    # 至少 +0.10 (20 步 × 0.01)
    assert final_gt - initial_gt >= 0.10


def test_gossip_drift_for_high_gossip_persona_clamped():
    """高 gossip baseline (ENTP-AV 0.65) 经过 gossip, 不会无限上升 (clamp 到 1.0)。"""
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(persona_id="ENTP-AV")
    initial_gt = sim.get_initial_personality()["gossip_tendency"]

    for _ in range(100):
        sim.process_message(topic="gossip", content="X 说 Y 的八卦")
    sim.run_drift_check()
    final_gt = sim.get_current_personality()["gossip_tendency"]
    # 应该 clamp 到 1.0, 不超过
    assert final_gt <= 1.0
    # 应该有上升
    assert final_gt > initial_gt


# ═══ 4. 中性话题 → gossip_tendency 不漂移 ═══

def test_gossip_does_not_drift_under_neutral_topics():
    """中性话题 → gossip_tendency 不漂移。"""
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(persona_id="ENTP-AV")
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
    result = run_simulation(persona_id="ESTP-A", scenario="gossip_topic_heavy", steps=10)
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
    personas = ["INFP-A", "ISTJ-S", "ENTP-AV", "ISFJ-D", "ESTP-A"]
    for persona in personas:
        result = simulate_persona(persona_id=persona, scenario="gossip_topic_heavy", steps=20)
        assert result["persona_id"] == persona
        assert result["scenario"] == "gossip_topic_heavy"
        assert "gossip_tendency" in result["personality"]
        assert "trajectory" in result
        # gossip_topic_heavy 应该有 drift
        initial = result["trajectory"][0]["gossip_tendency"]
        final = result["personality"]["gossip_tendency"]
        assert final > initial, (
            f"{persona}: gossip_topic_heavy 应有 drift, 实际 {initial} -> {final}"
        )


def test_simulate_persona_neutral_scenario():
    """simulate_persona neutral_only scenario → gossip_tendency 不漂移。"""
    from verification.drift_simulator import simulate_persona
    result = simulate_persona(persona_id="ENTP-AV", scenario="neutral_only", steps=20)
    initial = result["trajectory"][0]["gossip_tendency"]
    final = result["personality"]["gossip_tendency"]
    assert abs(final - initial) < 0.05


# ═══ 7. 5 persona gossip_tendency 区间断言 (跟 KB 直接对, 验证 DriftSimulator 读 KB) ═══

def test_all_5_personas_gossip_tendency_via_simulator():
    """DriftSimulator(persona_id=X).get_initial_personality() 跟 KB 一致 (5 persona 全验证)。"""
    from verification.drift_simulator import DriftSimulator
    from emotion_spirit.knowledge import KnowledgeBase
    for persona in ["INFP-A", "ISTJ-S", "ENTP-AV", "ISFJ-D", "ESTP-A"]:
        sim = DriftSimulator(persona_id=persona)
        sim_gt = sim.get_initial_personality()["gossip_tendency"]
        kb_gt = KnowledgeBase.get_persona_baseline(persona)["gossip_tendency"]
        assert sim_gt == kb_gt, (
            f"{persona}: sim={sim_gt} vs kb={kb_gt} 不一致"
        )


# ═══ 8. get_current_personality 返回所有 13 维 (不只 gossip_tendency) ═══

def test_get_current_personality_has_all_13_dims():
    """get_current_personality 返回完整 13 维 (5 deep + 8 surface)。"""
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(persona_id="INFP-A")
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
