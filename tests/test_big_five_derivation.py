"""§1.8: Big Five 必须从 13 维派生 (v1.3.0 Y-0b).

验证 to_big_five 派生生效 + personality_feedback drift 表无 Big Five.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
BIG_FIVE = re.compile(r'"(extraversion|neuroticism|agreeableness|conscientiousness|openness)"')


def test_to_big_five_varies_across_personas():
    """to_big_five 在不同 13 维输入上产出不同 Big Five (派生生效, 非全 0.5)."""
    from emotion_spirit.utils.persona_profiles import to_big_five
    # 高 E 低 N persona vs 低 E 高 N persona
    p1 = {"warmth_bias": 0.8, "expression_drive": 0.8, "gossip_tendency": 0.7,
          "intimacy_pull": 0.7, "relational_gravity": 0.6,
          "boundary_permeability": 0.3, "inner_coherence": 0.8, "patience": 0.7,
          "directness": 0.5, "curiosity": 0.5, "perception_acuity": 0.5,
          "exploration_openness": 0.5}
    p2 = {"warmth_bias": 0.2, "expression_drive": 0.2, "gossip_tendency": 0.3,
          "intimacy_pull": 0.3, "relational_gravity": 0.4,
          "boundary_permeability": 0.8, "inner_coherence": 0.3, "patience": 0.3,
          "directness": 0.5, "curiosity": 0.5, "perception_acuity": 0.5,
          "exploration_openness": 0.5}
    b1 = to_big_five(p1)
    b2 = to_big_five(p2)
    assert b1["extraversion"] > b2["extraversion"], "高 E persona 应派生更高 extraversion"
    assert b1["neuroticism"] < b2["neuroticism"], "低 N persona 应派生更低 neuroticism"
    for v in list(b1.values()) + list(b2.values()):
        assert 0.0 <= v <= 1.0, f"Big Five 值越界 [0,1]: {v}"
    # 非全 0.5 (派生真在算)
    assert any(abs(v - 0.5) > 0.01 for v in b1.values()), "b1 不应全 0.5"


def test_personality_feedback_drift_table_no_big_five():
    """§1.8: personality_feedback drift 表必须 13 维 (无 Big Five key)."""
    pf = (REPO_ROOT / "emotion_spirit" / "regulation" / "personality_feedback.py").read_text(encoding="utf-8")
    violations = BIG_FIVE.findall(pf)
    assert not violations, f"personality_feedback 仍有 Big Five key (drift 表没迁): {violations}"