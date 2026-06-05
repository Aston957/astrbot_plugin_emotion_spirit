"""情绪分类器 — emotion_spirit 独立实现。

SylannEngine 的 pad_interop.py 维护 emotion 区域定义，本模块保留一份同步副本，
不依赖 SylannEngine 改动。当上游合并 PR 后可平滑切换到上游版本。

基于文献：
- Russell & Mehrabian 1977: 7 类基本情绪的 PAD 边界
- Fontaine et al. 2007: PAD 充分性
- RAF-DB (Li 2017): 复合情绪由 2 个基本情绪组合
- Juslin & Laukka 2003: arousal = 强度指标
"""

from __future__ import annotations

import math
from typing import Any

# 7 类基本情绪的 PAD 区域（与 SylannEngine pad_interop.py 同步）
CATEGORICAL_REGIONS: dict[str, dict[str, tuple[float, float]]] = {
    "joy":     {"valence": (0.3, 1.0),   "arousal": (0.3, 0.7), "dominance": (0.4, 1.0)},
    "anger":   {"valence": (-1.0, -0.2), "arousal": (0.6, 1.0), "dominance": (0.6, 1.0)},
    "sadness": {"valence": (-1.0, -0.2), "arousal": (0.0, 0.4), "dominance": (0.0, 0.4)},
    "fear":    {"valence": (-1.0, -0.2), "arousal": (0.5, 1.0), "dominance": (0.0, 0.4)},
    "surprise":{"valence": (-1.0, 1.0),  "arousal": (0.7, 1.0), "dominance": (0.0, 1.0)},
    "disgust": {"valence": (-1.0, -0.4), "arousal": (0.3, 0.6), "dominance": (0.4, 1.0)},
    "neutral": {"valence": (-0.2, 0.2),  "arousal": (0.3, 0.5), "dominance": (0.0, 1.0)},
}

# 4 类复合情绪区域（基于 spec §3.3 + RAF-DB）
COMPOUND_REGIONS: dict[str, dict[str, Any]] = {
    "sad_excitement": {
        "valence": (-0.8, -0.2), "arousal": (0.6, 1.0), "dominance": (0.0, 0.4),
        "primary": "sadness", "secondary": "excitement",
    },
    "angry_despair": {
        "valence": (-1.0, -0.4), "arousal": (0.7, 1.0), "dominance": (0.5, 1.0),
        "primary": "anger", "secondary": "despair",
    },
    "joyful_anxiety": {
        "valence": (0.2, 0.8), "arousal": (0.6, 1.0), "dominance": (0.3, 0.7),
        "primary": "joy", "secondary": "anxiety",
    },
    "sad_calm": {
        "valence": (-0.6, -0.1), "arousal": (0.0, 0.4), "dominance": (0.0, 0.4),
        "primary": "sadness", "secondary": "calm",
    },
}

# 中文标签映射（仅用于 render_description 辅助层）
EMOTION_ZH: dict[str, str] = {
    "joy": "喜悦",
    "anger": "愤怒",
    "sadness": "悲伤",
    "fear": "恐惧",
    "surprise": "惊讶",
    "disgust": "厌恶",
    "neutral": "平静",
    "excitement": "激动",
    "despair": "绝望",
    "anxiety": "紧张",
    "calm": "宁静",
}


# === 占位实现（后续 Task 替换） ===

def classify_distribution(pad: tuple[float, float, float]) -> dict[str, float]:
    """PAD → 概率分布（核心 API）。

    算法：
    1. 对每个 region 计算中心点匹配分数（0-1）
    2. softmax 转换为概率分布
    3. 过滤 < 0.05 的项
    4. 归一化

    Returns: {"joy": 0.6, "neutral": 0.3, "anger": 0.1}
    """
    valence, arousal, dominance = pad
    pad_values = {"valence": valence, "arousal": arousal, "dominance": dominance}

    # Step 1: 计算每个 region 的匹配分数
    scores: dict[str, float] = {}
    for label, bounds in CATEGORICAL_REGIONS.items():
        score = 0.0
        for dim_name, (lo, hi) in bounds.items():
            val = pad_values[dim_name]
            if lo <= val <= hi:
                # 在区域内：基于到中心的距离打分
                mid = (lo + hi) / 2.0
                half_range = (hi - lo) / 2.0
                if half_range > 0:
                    score += 1.0 - abs(val - mid) / half_range
                else:
                    score += 1.0
            else:
                # 区域外：距离惩罚
                dist = min(abs(val - lo), abs(val - hi))
                score -= dist * 2.0
        scores[label] = score

    # Step 2: softmax 转换
    max_score = max(scores.values())
    exp_scores = {k: math.exp(v - max_score) for k, v in scores.items()}
    total = sum(exp_scores.values())
    distribution = {k: v / total for k, v in exp_scores.items()}

    # Step 3: 过滤低概率项
    threshold = 0.05
    filtered = {k: v for k, v in distribution.items() if v >= threshold}
    if not filtered:
        filtered = {"neutral": 1.0}

    # Step 4: 归一化
    total = sum(filtered.values())
    return {k: v / total for k, v in filtered.items()}


def classify_primary_secondary(
    distribution: dict[str, float],
    pad: tuple[float, float, float] | None = None,
) -> tuple[str, str | None]:
    """从分布提取主要/次要情绪。Task 3 实现。"""
    return ("neutral", None)


def render_description(distribution: dict[str, float], intensity: float) -> str:
    """概率分布 + 强度 → 中文描述。Task 4 实现。"""
    return "当前情绪平静"
