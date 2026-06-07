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
import time
from typing import Any


# === 占位实现（后续 Task 替换） ===

def build_emotion_payload(signals: Any) -> dict[str, Any]:
    """v1.1.2: 把 emotion 字段打包成稳定 schema dict（共享层）。
    v1.2: +emotion_ambiguity +emotion_velocity

    单一数据源：diary_writer 和 life_simulator 都基于此。
    字段命名约定: emotion_* 前缀（区分原始 PAD）。

    Returns:
        {
            "pad": {"valence": ..., "arousal": ..., "dominance": ...},
            "emotion_distribution": ...,
            "emotion_primary": ...,
            "emotion_secondary": ...,
            "emotion_intensity": ...,
            "emotion_ambiguity": ...,
            "emotion_velocity": ...,
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
        # v1.2 新增 2 字段
        "emotion_ambiguity": signals.emotion_ambiguity,
        "emotion_velocity": signals.emotion_velocity,
    }


def compute_ambiguity(distribution: dict[str, float]) -> float:
    """v1.3: 模糊度 = 1 - max(p)。

    0.0 = 完全确定（单一情绪主导，max=1）
    1.0 = 完全模糊（max≈0，几乎无主导）

    v1.2 → v1.3 变更理由：
    - 真实数据仿真发现 Shannon entropy / log(K) 让所有场景 ambiguity 偏高
      (0.74-0.91, 区分度差)
    - 1 - max(p) 直接测"主导度", 区分度更好

    Examples:
        {"joy": 1.0}                              → 0.0   (确定)
        {"joy": 0.5, "neutral": 0.5}              → 0.5
        {"joy": 0.6, "neutral": 0.4}              → 0.4   (joy 主导)
        {"joy": 0.4, "neutral": 0.3, "anger": 0.3} → 0.6
    """
    if not distribution:
        return 0.0
    max_p = max(distribution.values())
    return 1.0 - max_p


def compute_velocity(
    current: tuple[float, float, float],
    last: tuple[float, float, float, float] | None,
) -> dict[str, float] | None:
    """v1.2: 算 (current - last) / dt 的瞬时变化率。

    Args:
        current: (valence, arousal, dominance) 当前帧
        last: (valence, arousal, dominance, timestamp) 上一帧；None = 首帧

    Returns:
        {valence, arousal, dominance, dt} 或 None（首帧 / dt <= 0）

    字段含义:
        valence > 0   → 情绪向正向变（悲伤 → 喜悦）
        arousal > 0   → 唤醒度升高（平静 → 激动）
        dominance > 0 → 掌控感上升（被动 → 主动）
        dt            → 两帧间隔（秒）
    """
    if last is None:
        return None
    cv, ca, cd = current
    lv, la, ld, lt = last
    dt = time.time() - lt
    if dt <= 0:
        return None
    return {
        "valence": cv - lv,
        "arousal": ca - la,
        "dominance": cd - ld,
        "dt": dt,
    }


def classify_distribution(pad: tuple[float, float, float]) -> dict[str, float]:
    """PAD → 概率分布（核心 API）。

    算法：
    1. 对每个 region 计算中心点匹配分数（0-1）
    2. softmax 转换为概率分布
    3. 过滤 < 0.05 的项
    4. 归一化

    Returns: {"joy": 0.6, "neutral": 0.3, "anger": 0.1}
    """
    from .knowledge import KnowledgeBase
    valence, arousal, dominance = pad
    pad_values = {"valence": valence, "arousal": arousal, "dominance": dominance}

    # Step 1: 计算每个 region 的匹配分数 (Phase B: 走 KnowledgeBase.CATEGORICAL_REGIONS)
    scores: dict[str, float] = {}
    for label, bounds in KnowledgeBase.CATEGORICAL_REGIONS.items():
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
    from .knowledge import KnowledgeBase
    valence, arousal, dominance = pad
    for compound in KnowledgeBase.COMPOUND_REGIONS.values():
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
    from .knowledge import KnowledgeBase
    emotion_zh = KnowledgeBase.EMOTION_ZH
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
        return f"你现在的情绪{intensity_w}，以{emotion_zh.get(top1_name, top1_name)}为主"

    # 3. 主+副混合
    if top1_val > 0.35 and top2_val > 0.20 and ratio < 2.5:
        p1_zh = emotion_zh.get(top1_name, top1_name)
        p2_zh = emotion_zh.get(top2_name, top2_name)
        return f"你现在的情绪{intensity_w}，以{p1_zh}为主，带有{p2_zh}色彩"

    # 4. 双极交织
    if (0.30 <= top1_val <= 0.45 and 0.25 <= top2_val <= 0.45
            and abs(top1_val - top2_val) < 0.10):
        p1_zh = emotion_zh.get(top1_name, top1_name)
        p2_zh = emotion_zh.get(top2_name, top2_name)
        return f"你现在的情绪{intensity_w}在{p1_zh}与{p2_zh}之间交织"

    # 5. 多色混合 / 兜底
    p1_zh = emotion_zh.get(top1_name, top1_name)
    return f"你现在的情绪{intensity_w}，混合了多种色彩（{p1_zh}略占优势）"


from .registry import register


@register(name="emotion_classifier", provides=[], depends_on=[])
class _ModuleMarker:
    """纯函数模块标记 (供 ModuleRegistry 元数据用)。"""
    pass
