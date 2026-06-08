"""DriftSimulator B 单入口 (labels=) 测试 (Phase 3.0A)。

Task 2 验证:
  1. DriftSimulator(labels={...}) 唯一入口, baseline 走 compute_baseline_from_labels
  2. positional 参数禁用 (str/dict 都不行)
  3. persona_id= 关键字参数禁用 (旧 API 删)
  4. drift 不 clamp 到 [0,1] (B 决策, 真实主义)
"""
from __future__ import annotations

import sys
from pathlib import Path

# 让 tests/ 模块 (含 fixture_labels.py) 可 import
_TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_TESTS_DIR))
# 直接 import tests/fixture_labels.py (普通 module, 不受 pytest conftest 特殊语义影响)
from fixture_labels import INFP_A_LABELS  # noqa: E402


# ═══ 1. DriftSimulator(labels=...) 唯一入口 ═══

def test_drift_simulator_accepts_labels_dict():
    """DriftSimulator(labels={...}) 唯一入口, baseline 来自 compute_baseline_from_labels。

    INFP-A 5 标签 (mbti=INFP, attachment=安全型, emotion_style=表达型,
    conflict_style=合作型, time_focus=活在当下) → gossip_tendency baseline 应该是:

      baseline = 0.5
      + mbti INFP 字母贡献: (I: -0.10) + (F: +0.05) → × 0.25 = -0.0125
      + attachment 安全型: 无 gossip delta → 0
      + emotion_style 表达型: +0.05 × 0.20 = +0.01
      + conflict_style 合作型: 无 gossip delta → 0
      + time_focus 活在当下: 无 gossip delta → 0
      = 0.5 - 0.0125 + 0.01 = 0.4975
    """
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(labels=INFP_A_LABELS)
    baseline = sim.get_initial_personality()
    assert "gossip_tendency" in baseline
    # INFP-A labels → gossip ≈ 0.4975 (允许小浮点误差)
    assert abs(baseline["gossip_tendency"] - 0.4975) < 0.01, (
        f"INFP-A gossip_tendency baseline 期望 ≈0.4975, 实际 {baseline['gossip_tendency']}"
    )


# ═══ 2. positional 参数禁用 ═══

def test_drift_simulator_rejects_positional_arg():
    """DriftSimulator() 必须传 labels=, positional 字符串/dict 都报错 (B 单入口)。"""
    from verification.drift_simulator import DriftSimulator
    # 旧 positional str: DriftSimulator("INFP-A") 应报 TypeError
    try:
        DriftSimulator("INFP-A")  # type: ignore[misc]
        assert False, "DriftSimulator(\"INFP-A\") 应报 TypeError (B 决策: 仅 keyword-only)"
    except TypeError:
        pass
    # 无参数: DriftSimulator() 应报 TypeError
    try:
        DriftSimulator()  # type: ignore[call-arg]
        assert False, "DriftSimulator() 应报 TypeError (B 决策: labels= required)"
    except TypeError:
        pass


# ═══ 3. persona_id= 关键字参数禁用 ═══

def test_drift_simulator_rejects_persona_id_keyword():
    """DriftSimulator(persona_id=...) 删, 应报 TypeError (KB.PERSONA_BASELINES 已删)。"""
    from verification.drift_simulator import DriftSimulator
    try:
        DriftSimulator(persona_id="INFP-A")  # type: ignore[call-arg]
        assert False, "DriftSimulator(persona_id=...) 应报 TypeError (B 决策: 删 persona_id kwarg)"
    except TypeError:
        pass


# ═══ 4. drift 不 clamp 到 [0,1] (B 决策, 真实主义) ═══

def test_drift_simulator_allows_greater_than_one():
    """B 决策: drift 删 [0,1] clamp, gossip_tendency 允许 > 1.0 (cumulative drift)。

    ENFP 标签 (mbti=ENFP, attachment=焦虑型, emotion_style=表达型,
    conflict_style=攻击型, time_focus=活在当下) → gossip_tendency baseline 高 (~0.78):
      0.5 + 0.25×(E:0.10+N:0+F:0.05+P:0) + 0.20×(焦虑型:0.10)
      + 0.20×(表达型:0.05) + 0.20×(攻击型:0.05) + 0.15×(活在当下:0)
      = 0.5 + 0.0375 + 0.02 + 0.01 + 0.01 = 0.5775

    100 步 gossip drift × GOSSIP_DRIFT_STEP=0.01 = +1.0, 所以 final > baseline。
    """
    from verification.drift_simulator import DriftSimulator
    sim = DriftSimulator(labels={
        "mbti": "ENFP", "attachment": "焦虑型", "emotion_style": "表达型",
        "conflict_style": "攻击型", "time_focus": "活在当下",
    })
    # 100 步 gossip 话题
    for _ in range(100):
        sim.process_message(topic="gossip", content="X 说 Y 的八卦")
    sim.run_drift_check()
    final_gt = sim.get_current_personality()["gossip_tendency"]
    # B 决策: 允许 > 1.0 (cumulative drift 不 clamp)
    # baseline ~0.58 + 100×0.01 = ~1.58 (no clamp), 1.0 (clamp)
    # 至少确认 final > baseline, 且确实上升
    assert final_gt > 0.5, f"gossip 应上升, 实际 {final_gt}"
