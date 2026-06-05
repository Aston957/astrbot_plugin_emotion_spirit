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


def test_classify_distribution_neutral():
    """中性 PAD 返回 neutral 主导分布。"""
    dist = classify_distribution((0.0, 0.4, 0.5))
    assert "neutral" in dist
    assert dist["neutral"] > 0.5


def test_classify_distribution_joy_dominant():
    """喜悦 PAD 返回 joy 主导分布。"""
    dist = classify_distribution((0.7, 0.5, 0.7))
    assert dist["joy"] > 0.5
    assert dist["joy"] == max(dist.values())


def test_classify_distribution_sums_to_one():
    """概率分布求和 = 1.0。"""
    dist = classify_distribution((0.3, 0.6, 0.4))
    total = sum(dist.values())
    assert abs(total - 1.0) < 0.001


def test_classify_distribution_filters_low_probability():
    """过滤低概率项后，标签数 <= 7。"""
    dist = classify_distribution((-0.9, 0.9, 0.2))
    assert len(dist) <= 7
    for v in dist.values():
        assert v >= 0.05


def test_classify_primary_secondary_single_dominant():
    """单极主导: top1 > 0.5, top1/top2 > 2.5 → (top1, None)。"""
    dist = {"joy": 0.6, "neutral": 0.3, "anger": 0.1}
    primary, secondary = classify_primary_secondary(dist)
    assert primary == "joy"
    assert secondary is None


def test_classify_primary_secondary_mixed_shape():
    """主+副混合: top1 > 0.35, top2 > 0.20, ratio < 2.5 → (top1, top2)。"""
    dist = {"joy": 0.4, "surprise": 0.35, "neutral": 0.25}
    primary, secondary = classify_primary_secondary(dist)
    assert primary == "joy"
    assert secondary == "surprise"


def test_classify_primary_secondary_compound_region_match():
    """复合区域匹配: PAD 落在 COMPOUND_REGIONS 内 → 用 compound primary/secondary。"""
    dist = {"sadness": 0.4, "neutral": 0.3, "fear": 0.3}
    # PAD = (-0.5, 0.8, 0.2) 落在 sad_excitement 区域
    primary, secondary = classify_primary_secondary(dist, pad=(-0.5, 0.8, 0.2))
    assert primary == "sadness"
    assert secondary == "excitement"


def test_classify_primary_secondary_blended_shape():
    """双极交织: top1, top2 ∈ [0.25, 0.45] & |diff| < 0.10 → (top1, top2)。"""
    dist = {"joy": 0.35, "surprise": 0.32, "neutral": 0.2, "anger": 0.13}
    primary, secondary = classify_primary_secondary(dist)
    assert primary == "joy"
    assert secondary == "surprise"
