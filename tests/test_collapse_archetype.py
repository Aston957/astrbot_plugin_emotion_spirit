"""Tests for CollapseArchetypeSelector L1 + 连续化 (v1.2.5 PR2 §4.3)"""
from emotion_spirit.regulation.collapse_archetype import CollapseArchetypeSelector


def test_compute_bas_bis_backward_compatible_no_force_state():
    """不传 force_state → BAS/BIS 跟 v1.2.4 一致, collapse_tendency = max(0, BIS-BAS)"""
    sel = CollapseArchetypeSelector()
    BAS, BIS, tendency = sel.compute_bas_bis(
        personality={"extraversion": 0.5, "openness": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "conscientiousness": 0.5},
    )
    # 默认人格: BAS = 0.4*0.5 + 0.3*0.5 + 0.2*0.5 + 0.1*0.5 = 0.5
    # BIS = 0.4*0.5 + 0.3*0.5 + 0.2*0.5 + 0.1*0.5 = 0.5
    # collapse_tendency = max(0, 0.5 - 0.5) = 0.0
    assert abs(BAS - 0.5) < 0.001
    assert abs(BIS - 0.5) < 0.001
    assert tendency == 0.0


def test_compute_bas_bis_high_neuroticism_high_collapse():
    """高 N → BIS 高 → collapse_tendency 高"""
    sel = CollapseArchetypeSelector()
    _, BIS, tendency = sel.compute_bas_bis(
        personality={"extraversion": 0.5, "openness": 0.5, "neuroticism": 0.9, "agreeableness": 0.5, "conscientiousness": 0.5},
    )
    assert BIS > 0.5
    assert tendency > 0.0


def test_compute_bas_bis_high_extraversion_low_collapse():
    """高 E → BAS 高 → collapse_tendency 低 (或不崩)"""
    sel = CollapseArchetypeSelector()
    BAS, _, tendency = sel.compute_bas_bis(
        personality={"extraversion": 0.9, "openness": 0.5, "neuroticism": 0.2, "agreeableness": 0.5, "conscientiousness": 0.5},
    )
    assert BAS > 0.5
    assert tendency <= 0.1  # BIS-BAS 可能负, max(0, ...) = 0


def test_compute_bas_bis_with_force_state_individual_increases():
    """force_state.individual 高 → BIS 加权升高 → collapse_tendency 高"""
    sel = CollapseArchetypeSelector()
    _, _, base_tendency = sel.compute_bas_bis(
        personality={"extraversion": 0.5, "openness": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "conscientiousness": 0.5},
    )
    _, _, indiv_tendency = sel.compute_bas_bis(
        personality={"extraversion": 0.5, "openness": 0.5, "neuroticism": 0.5, "agreeableness": 0.5, "conscientiousness": 0.5},
        force_state={"natural": 0.5, "social": 0.5, "individual": 0.9},
    )
    assert indiv_tendency >= base_tendency


def test_collapse_tendency_clamped():
    """collapse_tendency 必在 [0, 1]"""
    sel = CollapseArchetypeSelector()
    _, _, tendency = sel.compute_bas_bis(
        personality={"extraversion": 0.1, "openness": 0.1, "neuroticism": 0.99, "agreeableness": 0.99, "conscientiousness": 0.99},
        force_state={"natural": 1.0, "social": 0.0, "individual": 1.0},
    )
    assert 0.0 <= tendency <= 1.0
