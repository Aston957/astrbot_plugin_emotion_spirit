"""Tests for surface_consumer.py"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotion_spirit.output.surface_consumer import SurfaceConsumer


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
            "surface": {"warmth_bias": 0.5, "directness": 0.5, "curiosity": 0.5, "patience": 0.5, "intimacy_pull": 0.5, "relational_autonomy": 0.5, "exploration_openness": 0.5},  # v1.7: autonomy_guard 拆分
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


# ═══ v1.2: 3 个新字段默认值 ═══


def test_semantic_signals_v12_defaults():
    """v1.2 新增字段有合理默认值（向后兼容）。"""
    from emotion_spirit.output.surface_consumer import SemanticSignals

    s = SemanticSignals()
    assert s.emotion_ambiguity == 0.0
    assert s.emotion_velocity is None
    assert s.emotion_trajectory == []
    assert s.emotion_burst is False  # v1.2+


# ═══ v1.2: SurfaceConsumer 集成（session_id + per-session 状态） ═══


def test_consume_first_frame_velocity_is_none():
    """首帧无历史 → emotion_velocity = None。"""
    from emotion_spirit.output.surface_consumer import SurfaceConsumer

    consumer = SurfaceConsumer()
    surface = {"pad": {"valence": 0.5, "arousal": 0.5, "dominance": 0.5}}
    s = consumer.consume(surface, session_id="s1")
    assert s.emotion_velocity is None


def test_consume_second_frame_computes_velocity():
    """第二帧 → emotion_velocity 含 4 键。"""
    from emotion_spirit.output.surface_consumer import SurfaceConsumer

    consumer = SurfaceConsumer()
    consumer.consume(
        {"pad": {"valence": 0.3, "arousal": 0.4, "dominance": 0.5}}, session_id="s1"
    )
    s2 = consumer.consume(
        {"pad": {"valence": 0.5, "arousal": 0.6, "dominance": 0.7}}, session_id="s1"
    )
    assert s2.emotion_velocity is not None
    # 浮点容差
    assert abs(s2.emotion_velocity["valence"] - 0.2) < 1e-6
    assert abs(s2.emotion_velocity["arousal"] - 0.2) < 1e-6
    assert abs(s2.emotion_velocity["dominance"] - 0.2) < 1e-6
    assert s2.emotion_velocity["dt"] > 0


def test_consume_populates_ambiguity():
    """任何帧 → emotion_ambiguity 在 [0, 1]。"""
    from emotion_spirit.output.surface_consumer import SurfaceConsumer

    consumer = SurfaceConsumer()
    s = consumer.consume(
        {"pad": {"valence": 0.5, "arousal": 0.5, "dominance": 0.5}}, session_id="s1"
    )
    assert 0.0 <= s.emotion_ambiguity <= 1.0


def test_consume_trajectory_keeps_last_n_frames():
    """连续 12 帧（默认 N=8）→ trajectory 只保留最后 8 帧。"""
    from emotion_spirit.output.surface_consumer import SurfaceConsumer

    consumer = SurfaceConsumer()
    for i in range(12):
        consumer.consume(
            {"pad": {"valence": i * 0.05, "arousal": 0.5, "dominance": 0.5}},
            session_id="s1",
        )
    s = consumer.consume(
        {"pad": {"valence": 0.7, "arousal": 0.5, "dominance": 0.5}}, session_id="s1"
    )
    # 第 13 次 consume 后 trajectory 是当前 + 之前 7 帧 = 8 帧
    assert len(s.emotion_trajectory) == 8


def test_consume_per_session_isolation():
    """不同 session 互不干扰。"""
    from emotion_spirit.output.surface_consumer import SurfaceConsumer

    consumer = SurfaceConsumer()
    # s1 第一帧
    consumer.consume(
        {"pad": {"valence": 0.0, "arousal": 0.5, "dominance": 0.5}}, session_id="s1"
    )
    # s2 第一帧（不应影响 s1）
    s2_first = consumer.consume(
        {"pad": {"valence": 0.5, "arousal": 0.5, "dominance": 0.5}}, session_id="s2"
    )
    assert s2_first.emotion_velocity is None  # s2 首帧
    # s1 第二帧（应该是 s1 的差分，不是 s1→s2）
    s1_again = consumer.consume(
        {"pad": {"valence": 0.1, "arousal": 0.5, "dominance": 0.5}}, session_id="s1"
    )
    # s1 velocity: (0.1-0.0, 0.5-0.5, 0.5-0.5) = (0.1, 0, 0)
    assert s1_again.emotion_velocity is not None
    assert abs(s1_again.emotion_velocity["valence"] - 0.1) < 1e-6
    assert abs(s1_again.emotion_velocity["arousal"]) < 1e-6


if __name__ == "__main__":
    test_consume_returns_signals()
    test_body_integration_range()
    test_body_criticality_range()
    test_phi_ema_convergence()
    test_body_criticality_extreme()
    test_empty_surface_defaults()
    test_semantic_signals_v12_defaults()
    test_consume_first_frame_velocity_is_none()
    test_consume_second_frame_computes_velocity()
    test_consume_populates_ambiguity()
    test_consume_trajectory_keeps_last_n_frames()
    test_consume_per_session_isolation()
    test_consume_burst_detected_on_large_velocity_change()
    test_consume_no_burst_on_small_velocity_change()
    print("All surface_consumer tests passed!")


# ═══ v1.2+: VELOCITY_BURST_THRESHOLD 突变检测 ═══


def test_consume_burst_detected_on_large_velocity_change():
    """v1.2+: 帧间 |Δvalence| 或 |Δarousal| > 0.05 → emotion_burst=True。"""
    import time as time_mod
    from emotion_spirit.output.surface_consumer import SurfaceConsumer

    consumer = SurfaceConsumer()
    # 第一帧 (平静)
    consumer.consume(
        {"pad": {"valence": 0.0, "arousal": 0.4, "dominance": 0.5}}, session_id="s_burst"
    )
    # 等 10ms 强制正 dt
    time_mod.sleep(0.01)
    # 第二帧 (突然愤怒，Δvalence = -0.8, |0.8| > 0.05)
    s2 = consumer.consume(
        {"pad": {"valence": -0.8, "arousal": 0.9, "dominance": 0.7}}, session_id="s_burst"
    )
    assert s2.emotion_burst is True


def test_consume_no_burst_on_small_velocity_change():
    """v1.2+: 帧间 |Δ| <= 0.05 → emotion_burst=False。"""
    import time as time_mod
    from emotion_spirit.output.surface_consumer import SurfaceConsumer

    consumer = SurfaceConsumer()
    consumer.consume(
        {"pad": {"valence": 0.0, "arousal": 0.4, "dominance": 0.5}}, session_id="s_small"
    )
    time_mod.sleep(0.01)
    # 第二帧轻微变化 (Δvalence = 0.03, |0.03| < 0.05)
    s2 = consumer.consume(
        {"pad": {"valence": 0.03, "arousal": 0.42, "dominance": 0.5}}, session_id="s_small"
    )
    assert s2.emotion_burst is False
