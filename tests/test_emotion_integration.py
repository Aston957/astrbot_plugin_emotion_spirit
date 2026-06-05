"""SemanticSignals 扩展 + consume() 集成测试。"""

import pytest
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
