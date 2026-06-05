"""SemanticSignals 扩展 + consume() 集成测试。"""

import pytest
from emotion_spirit.emotion_classifier import CATEGORICAL_REGIONS
from emotion_spirit.surface_consumer import SemanticSignals


def test_semantic_signals_has_new_pad_fields():
    """SemanticSignals 包含 4 个新 pad 字段，默认值正确。"""
    s = SemanticSignals()
    assert hasattr(s, "pad_distribution")
    assert s.pad_distribution == {"neutral": 1.0}
    assert hasattr(s, "pad_primary")
    assert s.pad_primary == "neutral"
    assert hasattr(s, "pad_secondary")
    assert s.pad_secondary is None
    assert hasattr(s, "pad_intensity")
    assert s.pad_intensity == 0.0


def test_semantic_signals_preserves_pad_label():
    """pad_label 和 pad_confidence 保留作为向后兼容。"""
    s = SemanticSignals()
    assert s.pad_label == "neutral"
    assert s.pad_confidence == 0.5


def test_consume_populates_distribution():
    """consume() 后 signals.pad_distribution 非空且求和 ≈ 1.0。"""
    from emotion_spirit.surface_consumer import SurfaceConsumer
    consumer = SurfaceConsumer()
    surface = {
        "state": {},
        "dynamics": {},
        "decision": {},
        "guard": {},
        "personality": {},
        "pad": {"valence": 0.7, "arousal": 0.5, "dominance": 0.7, "label": "joy", "confidence": 0.8},
        "pipeline": {},
        "debug": {},
    }
    signals = consumer.consume(surface)
    assert signals.pad_distribution
    total = sum(signals.pad_distribution.values())
    assert abs(total - 1.0) < 0.001
    assert "joy" in signals.pad_distribution


def test_consume_populates_primary_secondary():
    """consume() 后 signals.pad_primary 是字符串，pad_secondary 可选。"""
    from emotion_spirit.surface_consumer import SurfaceConsumer
    consumer = SurfaceConsumer()
    surface = {
        "state": {},
        "dynamics": {},
        "decision": {},
        "guard": {},
        "personality": {},
        "pad": {"valence": 0.7, "arousal": 0.5, "dominance": 0.7, "label": "joy", "confidence": 0.8},
        "pipeline": {},
        "debug": {},
    }
    signals = consumer.consume(surface)
    assert isinstance(signals.pad_primary, str)
    assert signals.pad_primary in CATEGORICAL_REGIONS
    assert signals.pad_secondary is None or signals.pad_secondary in (
        set(CATEGORICAL_REGIONS.keys()) | {"excitement", "despair", "anxiety", "calm"}
    )
    assert signals.pad_intensity == signals.pad_arousal
