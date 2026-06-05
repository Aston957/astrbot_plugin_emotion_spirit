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

def build_emotion_payload(signals: Any) -> dict[str, Any]:
    """v1.1.2: 把 emotion 字段打包成稳定 schema dict（共享层）。

    单一数据源：diary_writer 和 life_simulator 都基于此。
    字段命名约定: emotion_* 前缀（区分原始 PAD）。

    Returns:
        {
            "pad": {"valence": ..., "arousal": ..., "dominance": ...},
            "emotion_distribution": ...,
            "emotion_primary": ...,
            "emotion_secondary": ...,
            "emotion_intensity": ...,
        }
    """
    return {
        "pad": {
            "valence": signals.pad_valence,
            "arousal": signals.pad_arousal,
            "dominance": signals.pad_dominance,
        },
        "emotion_distribution": dict(signals.pad_distribution),  # 防御性拷贝
        "emotion_primary": signals.pad_primary,
        "emotion_secondary": signals.pad_secondary,
        "emotion_intensity": signals.pad_intensity,
    }


def compute_ambiguity(distribution: dict[str, float]) -> float:
    """v1.2: 从概率分布算 Shannon 熵，归一化到 [0, 1]。

    0.0 = 单一情绪（delta 分布，非常确定）
    1.0 = 均匀分布（完全模糊）

    算法:
    - 过滤零概率项
    - 计算 H = -Σ p*log(p)
    - 归一化: H / log(N)，N 是分布中的类别数

    Examples:
        {"joy": 1.0}                    → 0.0   (单点)
        {"joy": 0.5, "neutral": 0.5}    → 1.0   (2 类均匀)
        {"joy": 0.25, ... (4 类)}       → 1.0   (4 类均匀)
        {"joy": 0.5, "sadness": 0.3, "anger": 0.2}  → ~0.95
    """
    probs = [p for p in distribution.values() if p > 0]
    if not probs:
        return 0.0
    entropy = -sum(p * math.log(p) for p in probs)
    max_entropy = math.log(len(distribution)) if len(distribution) > 1 else 1.0
    if max_entropy == 0:
        return 0.0
    return min(1.0, entropy / max_entropy)


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


def _in_compound_region(pad: tuple[float, float, float]) -> dict[str, Any] | None:
    """检查 PAD 是否落在某个复合区域。返回 compound dict 或 None。"""
    valence, arousal, dominance = pad
    for compound in COMPOUND_REGIONS.values():
        v_ok = compound["valence"][0] <= valence <= compound["valence"][1]
        a_ok = compound["arousal"][0] <= arousal <= compound["arousal"][1]
        d_ok = compound["dominance"][0] <= dominance <= compound["dominance"][1]
        if v_ok and a_ok and d_ok:
            return compound
    return None


def classify_primary_secondary(
    distribution: dict[str, float],
    pad: tuple[float, float, float] | None = None,
) -> tuple[str, str | None]:
    """从分布中提取主要/次要情绪（核心 API）。

    判定顺序（见 spec §3.4）：
    1. 平静基调 (neutral > 0.4) → ("neutral", None)
    2. COMPOUND_REGIONS 匹配 → 用 compound primary/secondary
    3. 单极主导 (max > 0.5 & ratio > 2.5) → (top1, None)
    4. 主+副混合 (max > 0.35 & top2 > 0.20 & ratio < 2.5) → (top1, top2)
    5. 双极交织 (top1, top2 在 0.25-0.45 & |diff| < 0.10) → (top1, top2)
    6. 多色混合 (max < 0.3) → (top1, None)
    7. 兜底 → (top1, None)
    """
    # 1. 平静基调
    if distribution.get("neutral", 0) > 0.4:
        return ("neutral", None)

    sorted_d = sorted(distribution.items(), key=lambda x: -x[1])
    top1_name, top1_val = sorted_d[0]
    top2_name, top2_val = (sorted_d[1] if len(sorted_d) > 1 else (None, 0.0))
    ratio = top1_val / top2_val if top2_val > 0 else float('inf')

    # 2. COMPOUND_REGIONS 匹配（仅在有 pad 时）
    if pad is not None:
        compound = _in_compound_region(pad)
        if compound is not None:
            return (compound["primary"], compound["secondary"])

    # 3. 单极主导
    if top1_val > 0.5 and ratio > 2.5:
        return (top1_name, None)

    # 4. 主+副混合
    if top1_val > 0.35 and top2_val > 0.20 and ratio < 2.5:
        return (top1_name, top2_name)

    # 5. 双极交织
    if (0.30 <= top1_val <= 0.45 and 0.25 <= top2_val <= 0.45
            and abs(top1_val - top2_val) < 0.10):
        return (top1_name, top2_name)

    # 6. 多色混合 / 7. 兜底
    return (top1_name, None)


def _intensity_word(arousal: float) -> str:
    """arousal → 强度词。"""
    if arousal >= 0.7:
        return "非常强烈"
    if arousal >= 0.5:
        return "明显的"
    if arousal >= 0.3:
        return "隐约的"
    return "淡淡的"


def render_description(distribution: dict[str, float], intensity: float) -> str:
    """概率分布 + 强度 → 中文描述（辅助层，仅人类用）。

    5 种分布形态 × 4 种强度词 = 20 种组合。
    ⚠️ LLM 消费者不应使用此函数（直接读 distribution 更精确）。
    """
    # 1. 平静基调
    if distribution.get("neutral", 0) > 0.4:
        return f"你现在的情绪{_intensity_word(intensity)}，偏向平静"

    sorted_d = sorted(distribution.items(), key=lambda x: -x[1])
    top1_name, top1_val = sorted_d[0]
    top2_name, top2_val = (sorted_d[1] if len(sorted_d) > 1 else (None, 0.0))
    ratio = top1_val / top2_val if top2_val > 0 else float('inf')

    intensity_w = _intensity_word(intensity)

    # 2. 单极主导
    if top1_val > 0.5 and ratio > 2.5:
        return f"你现在的情绪{intensity_w}，以{EMOTION_ZH.get(top1_name, top1_name)}为主"

    # 3. 主+副混合
    if top1_val > 0.35 and top2_val > 0.20 and ratio < 2.5:
        p1_zh = EMOTION_ZH.get(top1_name, top1_name)
        p2_zh = EMOTION_ZH.get(top2_name, top2_name)
        return f"你现在的情绪{intensity_w}，以{p1_zh}为主，带有{p2_zh}色彩"

    # 4. 双极交织
    if (0.30 <= top1_val <= 0.45 and 0.25 <= top2_val <= 0.45
            and abs(top1_val - top2_val) < 0.10):
        p1_zh = EMOTION_ZH.get(top1_name, top1_name)
        p2_zh = EMOTION_ZH.get(top2_name, top2_name)
        return f"你现在的情绪{intensity_w}在{p1_zh}与{p2_zh}之间交织"

    # 5. 多色混合 / 兜底
    p1_zh = EMOTION_ZH.get(top1_name, top1_name)
    return f"你现在的情绪{intensity_w}，混合了多种色彩（{p1_zh}略占优势）"
