"""emotion_classifier 单元测试。"""

import pytest
from emotion_spirit.emotion_classifier import (
    CATEGORICAL_REGIONS,
    COMPOUND_REGIONS,
    EMOTION_ZH,
    classify_distribution,
    classify_primary_secondary,
    render_description,
)


def test_categorical_regions_has_7_emotions():
    """7 类基本情绪的 PAD 区域定义完整。"""
    assert len(CATEGORICAL_REGIONS) == 7
    assert set(CATEGORICAL_REGIONS.keys()) == {
        "joy", "anger", "sadness", "fear", "surprise", "disgust", "neutral"
    }
    for region in CATEGORICAL_REGIONS.values():
        assert set(region.keys()) == {"valence", "arousal", "dominance"}


def test_compound_regions_has_4_emotions():
    """4 类复合情绪的 PAD 区域定义完整。"""
    assert len(COMPOUND_REGIONS) == 4
    assert set(COMPOUND_REGIONS.keys()) == {
        "sad_excitement", "angry_despair", "joyful_anxiety", "sad_calm"
    }
    for region in COMPOUND_REGIONS.values():
        assert "primary" in region
        assert "secondary" in region


def test_emotion_zh_translates_all_labels():
    """中文标签映射覆盖 7 基本 + 4 复合中的非基本标签。"""
    assert EMOTION_ZH["joy"] == "喜悦"
    assert EMOTION_ZH["sadness"] == "悲伤"
    assert EMOTION_ZH["excitement"] == "激动"
    assert EMOTION_ZH["calm"] == "宁静"
    assert EMOTION_ZH["neutral"] == "平静"
