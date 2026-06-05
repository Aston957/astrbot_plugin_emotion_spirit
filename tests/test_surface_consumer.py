"""Tests for surface_consumer.py"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotion_spirit.surface_consumer import SurfaceConsumer


def _make_surface(**overrides) -> dict:
    """构造最小有效 Surface。"""
    surface = {
        "state": {
            "rhythm": {"beat": 10, "stability": 0.8, "strain": 0.1},
            "connection": {"warmth": 0.5, "circulation": 0.3, "memory_flow": 0.4},
            "adaptation": {"plasticity": 0.3, "sensitivity": 0.5, "repetition": 1, "threshold_drift": 0.05},
            "responsiveness": {"readiness": 0.6, "fatigue": 0.2, "trained_reach": 0.3},
            "valence": {"warmth": 0.5, "volatility": 0.2, "recovery_heat": 0.1},
            "damage": {"open": 0.1, "accumulated": 0.3, "sensitivity": 0.4, "recovery": 0.2},
            "boundary": {"pressure": 0.3, "autonomy": 0.8, "interruption_budget": 0.7, "cooldown": 0.0, "paused": False},
            "capacity": {"load": 0.2, "exhaustion": 0.1, "recovery_debt": 0.05},
            "needs": {"expression": 0.4, "quiet": 0.2, "recovery": 0.1, "contact": 0.3},
        },
        "dynamics": {
            "hot_pool": {"temperature": 0.2, "volume": 0.1, "pressure": 0.1, "cascade_active": False, "cascade_intensity": 0.0, "collapse_count": 0, "in_recovery": False, "sensitivity_multiplier": 1.0},
            "relational_time": {"interval_seconds": 3600, "total_duration": 86400, "phase": "active"},
            "affect": {"recovery_drive": 0.1, "expression_drive": 0.4, "quiet_drive": 0.2},
            "uncertainty": {"claim_caution": 0.1, "events": 0},
        },
        "decision": {"action": "express", "reason": "test", "reason_code": "test", "confidence": 0.7, "urgency": 0.3},
        "guard": {"allowed": True, "reason": "", "risk_score": 0.1},
        "personality": {
            "deep": {"expression_drive": 0.5, "perception_acuity": 0.5, "boundary_permeability": 0.5, "inner_coherence": 0.5, "relational_gravity": 0.5},
            "surface": {"warmth_bias": 0.5, "directness": 0.5, "curiosity": 0.5, "patience": 0.5, "intimacy_pull": 0.5, "autonomy_guard": 0.5},
        },
        "pad": {"valence": 0.3, "arousal": 0.5, "dominance": 0.6, "label": "neutral", "confidence": 0.7},
        "pipeline": {
            "resonance": {"sync_order": 0.4, "energy": 5.0, "active_channels": 42, "plasticity_ratio": 0.8, "attractor_count": 2},
        },
        "debug": {
            "emergence": {"phi": 0.45, "order": {"synchronization": 0.4, "coherence": 0.5, "criticality": 0.2}},
        },
    }
    surface.update(overrides)
    return surface


def test_consume_returns_signals():
    consumer = SurfaceConsumer()
    signals = consumer.consume(_make_surface())
    assert hasattr(signals, "rhythm_strain")
    assert hasattr(signals, "phi_smoothed")
    assert hasattr(signals, "sync_order_smoothed")
    assert hasattr(signals, "body_integration")
    assert hasattr(signals, "body_criticality")


def test_body_integration_range():
    consumer = SurfaceConsumer()
    signals = consumer.consume(_make_surface())
    assert 0.0 <= signals.body_integration <= 1.0


def test_body_criticality_range():
    consumer = SurfaceConsumer()
    signals = consumer.consume(_make_surface())
    assert 0.0 <= signals.body_criticality <= 1.0


def test_phi_ema_convergence():
    consumer = SurfaceConsumer()
    surface = _make_surface()
    for _ in range(100):
        signals = consumer.consume(surface)
    assert abs(signals.phi_smoothed - 0.45) < 0.1


def test_body_criticality_extreme():
    consumer = SurfaceConsumer()
    surface = _make_surface()
    surface["state"]["rhythm"]["strain"] = 0.8
    surface["state"]["damage"]["open"] = 0.6
    surface["state"]["boundary"]["pressure"] = 0.8
    surface["state"]["capacity"]["exhaustion"] = 0.7
    surface["dynamics"]["hot_pool"]["cascade_active"] = True
    signals = consumer.consume(surface)
    assert signals.body_criticality > 0.5


def test_empty_surface_defaults():
    """空 Surface 输入不崩溃，所有字段有默认值。"""
    consumer = SurfaceConsumer()
    signals = consumer.consume({})

    assert 0.0 <= signals.body_integration <= 1.0
    assert 0.0 <= signals.body_criticality <= 1.0
    assert signals.decision_action == "hold"
    assert isinstance(signals.personality_deep, dict)
    assert isinstance(signals.personality_surface, dict)


if __name__ == "__main__":
    test_consume_returns_signals()
    test_body_integration_range()
    test_body_criticality_range()
    test_phi_ema_convergence()
    test_body_criticality_extreme()
    test_empty_surface_defaults()
    print("All surface_consumer tests passed!")
