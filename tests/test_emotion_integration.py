"""SemanticSignals 扩展 + consume() 集成测试。"""

import pytest
from emotion_spirit.knowledge import KnowledgeBase
from emotion_spirit.surface_consumer import SemanticSignals

# Phase B: 数据走 KnowledgeBase (单一数据源)
CATEGORICAL_REGIONS = KnowledgeBase.CATEGORICAL_REGIONS


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


def test_get_emotion_state_lazy_description():
    """get_emotion_state() 返回 9 字段 dict，description 每次调用都重新计算。"""
    import asyncio
    from main import EmotionSpiritPlugin
    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    from emotion_spirit.surface_consumer import SemanticSignals
    signals = SemanticSignals(
        pad_valence=0.7, pad_arousal=0.5, pad_dominance=0.7,
        pad_distribution={"joy": 0.6, "neutral": 0.3, "anger": 0.1},
        pad_primary="joy", pad_secondary=None, pad_intensity=0.5,
    )
    plugin._latest_signals = {"test_key": signals}

    state = asyncio.run(plugin.get_emotion_state("test_key"))
    assert state is not None
    assert state["pad"] == {"valence": 0.7, "arousal": 0.5, "dominance": 0.7}
    assert state["distribution"] == {"joy": 0.6, "neutral": 0.3, "anger": 0.1}
    assert state["primary"] == "joy"
    assert state["secondary"] is None
    assert state["intensity"] == 0.5
    assert "description" in state
    assert "label" in state
    assert isinstance(state["description"], str)


def test_get_emotion_state_returns_none_for_unknown_key():
    """未知 session_key 返回 None。"""
    import asyncio
    from main import EmotionSpiritPlugin
    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    plugin._latest_signals = {}
    assert asyncio.run(plugin.get_emotion_state("nonexistent")) is None


# ═══ v1.2: get_emotion_state 11 字段 (v1.7.2: trajectory 合并到 include_trajectory) ═══


def test_get_emotion_state_includes_v12_ambiguity_velocity():
    """v1.2: get_emotion_state 增加 emotion_ambiguity + emotion_velocity 字段。"""
    import asyncio
    from main import EmotionSpiritPlugin
    from emotion_spirit.surface_consumer import SemanticSignals

    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    signals = SemanticSignals(
        pad_valence=0.5, pad_arousal=0.6, pad_dominance=0.7,
        pad_distribution={"joy": 0.6, "neutral": 0.4},
        pad_primary="joy", pad_secondary="neutral", pad_intensity=0.6,
        emotion_ambiguity=0.97,
        emotion_velocity={"valence": 0.1, "arousal": 0.2, "dominance": 0.3, "dt": 1.0},
    )
    plugin._latest_signals = {"v12_key": signals}

    state = asyncio.run(plugin.get_emotion_state("v12_key"))
    assert state is not None
    assert state["emotion_ambiguity"] == 0.97
    assert state["emotion_velocity"]["valence"] == 0.1
    assert state["emotion_velocity"]["arousal"] == 0.2
    assert state["emotion_velocity"]["dominance"] == 0.3
    assert state["emotion_velocity"]["dt"] == 1.0


def test_get_emotion_state_keeps_backward_compat_9_fields():
    """v1.2 兼容老消费者：9 个原字段仍在。"""
    import asyncio
    from main import EmotionSpiritPlugin
    from emotion_spirit.surface_consumer import SemanticSignals

    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    signals = SemanticSignals(
        pad_valence=0.7, pad_arousal=0.5, pad_dominance=0.7,
        pad_distribution={"joy": 0.6, "neutral": 0.3, "anger": 0.1},
        pad_primary="joy", pad_secondary=None, pad_intensity=0.5,
    )
    plugin._latest_signals = {"bc_key": signals}

    state = asyncio.run(plugin.get_emotion_state("bc_key"))
    # 老字段必须存在
    assert "pad" in state
    assert "distribution" in state
    assert "primary" in state
    assert "secondary" in state
    assert "intensity" in state
    assert "description" in state
    assert "label" in state
    # 新增字段也必须存在（v1.2 特征）
    assert "emotion_ambiguity" in state
    assert "emotion_velocity" in state


# ═══ v1.7.2 Phase A: get_emotion_state(include_trajectory=False) 替代独立 API ═══


def test_get_emotion_state_with_trajectory_includes_field():
    """v1.7.2 Phase A: include_trajectory=True 时返回 emotion_trajectory 字段。"""
    import asyncio
    from main import EmotionSpiritPlugin
    from emotion_spirit.surface_consumer import SemanticSignals

    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    signals = SemanticSignals(
        emotion_trajectory=[
            (0.5, 0.6, 0.7, 1234.0),
            (0.4, 0.5, 0.6, 1235.0),
        ]
    )
    plugin._latest_signals = {"traj_key": signals}

    state = asyncio.run(plugin.get_emotion_state("traj_key", include_trajectory=True))
    assert state is not None
    assert "emotion_trajectory" in state
    assert isinstance(state["emotion_trajectory"], list)
    assert len(state["emotion_trajectory"]) == 2
    assert state["emotion_trajectory"][0]["valence"] == 0.5
    assert state["emotion_trajectory"][0]["timestamp"] == 1234.0


def test_get_emotion_state_without_trajectory_omits_field():
    """v1.7.2 Phase A: include_trajectory 默认 False, 不返回 emotion_trajectory 字段 (向后兼容)。"""
    import asyncio
    from main import EmotionSpiritPlugin
    from emotion_spirit.surface_consumer import SemanticSignals

    plugin = EmotionSpiritPlugin.__new__(EmotionSpiritPlugin)
    signals = SemanticSignals(
        emotion_trajectory=[(0.5, 0.6, 0.7, 1234.0)]
    )
    plugin._latest_signals = {"no_traj_key": signals}

    state = asyncio.run(plugin.get_emotion_state("no_traj_key"))
    assert state is not None
    assert "emotion_trajectory" not in state
