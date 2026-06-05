"""标签映射器 — 人类可读标签 ↔ SylannEngine 11 维参数。

每个标签维度对 11 维参数有增量贡献:
  最终值 = 基线 + Σ(各标签增量)

支持的标签维度:
  - mbti: MBTI 十六型人格
  - attachment: 依恋类型
  - emotion_style: 情绪策略
  - conflict_style: 冲突风格
  - time_focus: 时间取向
"""

from __future__ import annotations

from typing import Any


# ═══ 基线 (Default ISTJ 安全型) ═══

_BASELINE: dict[str, dict[str, float]] = {
    "deep": {
        "expression_drive": 0.25,
        "perception_acuity": 0.70,
        "boundary_permeability": 0.40,
        "inner_coherence": 0.95,
        "relational_gravity": 0.20,
    },
    "surface": {
        "warmth_bias": 0.30,
        "directness": 0.85,
        "curiosity": 0.60,
        "patience": 0.70,
        "intimacy_pull": 0.15,
        "autonomy_guard": 0.90,
    },
}


# ═══ MBTI 增量 (每个字母维度的贡献) ═══

_MBTI_LETTER_DELTAS: dict[str, dict[str, float]] = {
    # I vs E
    "I": {"expression_drive": -0.10, "warmth_bias": -0.05, "intimacy_pull": -0.10},
    "E": {"expression_drive": +0.15, "warmth_bias": +0.10, "intimacy_pull": +0.10},
    # N vs S
    "N": {"curiosity": +0.15, "perception_acuity": +0.05, "boundary_permeability": +0.10},
    "S": {"curiosity": -0.10, "perception_acuity": -0.05, "inner_coherence": +0.05},
    # F vs T
    "F": {"warmth_bias": +0.20, "relational_gravity": +0.15, "intimacy_pull": +0.15},
    "T": {"warmth_bias": -0.10, "directness": +0.10, "inner_coherence": +0.05},
    # P vs J
    "P": {"boundary_permeability": +0.15, "patience": -0.10, "autonomy_guard": -0.15},
    "J": {"inner_coherence": +0.05, "patience": +0.05, "autonomy_guard": +0.10},
}


# ═══ 依恋类型增量 ═══

_ATTACHMENT_DELTAS: dict[str, dict[str, float]] = {
    "安全型": {
        "boundary_permeability": +0.10,
        "inner_coherence": +0.10,
        "intimacy_pull": +0.05,
        "autonomy_guard": +0.05,
    },
    "焦虑型": {
        "boundary_permeability": +0.25,
        "inner_coherence": -0.20,
        "intimacy_pull": +0.30,
        "autonomy_guard": -0.25,
        "expression_drive": +0.15,
    },
    "回避型": {
        "boundary_permeability": -0.20,
        "inner_coherence": +0.10,
        "intimacy_pull": -0.20,
        "autonomy_guard": +0.25,
        "expression_drive": -0.15,
    },
    "混乱型": {
        "boundary_permeability": +0.10,
        "inner_coherence": -0.30,
        "intimacy_pull": +0.10,
        "autonomy_guard": -0.10,
        "expression_drive": +0.05,
    },
}


# ═══ 情绪策略增量 ═══

_EMOTION_STYLE_DELTAS: dict[str, dict[str, float]] = {
    "表达型": {
        "expression_drive": +0.20,
        "warmth_bias": +0.15,
        "perception_acuity": +0.05,
    },
    "压抑型": {
        "expression_drive": -0.15,
        "warmth_bias": -0.10,
        "directness": +0.10,
        "perception_acuity": +0.10,
    },
    "混合型": {
        "expression_drive": +0.05,
        "warmth_bias": +0.05,
    },
}


# ═══ 冲突风格增量 ═══

_CONFLICT_STYLE_DELTAS: dict[str, dict[str, float]] = {
    "攻击型": {
        "directness": +0.15,
        "autonomy_guard": +0.10,
        "patience": -0.15,
        "warmth_bias": -0.10,
    },
    "回避型": {
        "directness": -0.20,
        "autonomy_guard": +0.05,
        "patience": +0.15,
        "expression_drive": -0.10,
    },
    "顺应型": {
        "directness": -0.10,
        "autonomy_guard": -0.15,
        "patience": +0.10,
        "warmth_bias": +0.15,
        "intimacy_pull": +0.10,
    },
    "合作型": {
        "directness": +0.05,
        "patience": +0.10,
        "warmth_bias": +0.10,
        "inner_coherence": +0.05,
    },
}


# ═══ 时间取向增量 ═══

_TIME_FOCUS_DELTAS: dict[str, dict[str, float]] = {
    "活在过去": {
        "perception_acuity": +0.15,
        "inner_coherence": -0.10,
        "relational_gravity": +0.10,
    },
    "活在当下": {
        "perception_acuity": +0.05,
        "patience": +0.05,
    },
    "活在未来": {
        "curiosity": +0.10,
        "boundary_permeability": +0.05,
        "inner_coherence": -0.05,
    },
}


# ═══ 汇总 ═══

_ALL_LABEL_DELTAS: dict[str, dict[str, dict[str, float]]] = {
    "mbti": {},  # MBTI 需要特殊处理 (逐字母)
    "attachment": _ATTACHMENT_DELTAS,
    "emotion_style": _EMOTION_STYLE_DELTAS,
    "conflict_style": _CONFLICT_STYLE_DELTAS,
    "time_focus": _TIME_FOCUS_DELTAS,
}

# 可选值列表 (供 _conf_schema.json 使用)
LABEL_OPTIONS: dict[str, list[str]] = {
    "mbti": [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP",
    ],
    "attachment": ["安全型", "焦虑型", "回避型", "混乱型"],
    "emotion_style": ["表达型", "压抑型", "混合型"],
    "conflict_style": ["攻击型", "回避型", "顺应型", "合作型"],
    "time_focus": ["活在过去", "活在当下", "活在未来"],
}


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def labels_to_personality(labels: dict[str, str]) -> dict[str, dict[str, float]]:
    """将标签组合映射为 SylannEngine 11 维参数。"""
    # 从基线开始
    result: dict[str, dict[str, float]] = {
        "deep": dict(_BASELINE["deep"]),
        "surface": dict(_BASELINE["surface"]),
    }

    # MBTI: 逐字母解析
    mbti = labels.get("mbti", "ISTJ")
    if len(mbti) == 4:
        for letter in mbti.upper():
            if letter in _MBTI_LETTER_DELTAS:
                for dim, delta in _MBTI_LETTER_DELTAS[letter].items():
                    layer = "deep" if dim in result["deep"] else "surface"
                    result[layer][dim] = result[layer].get(dim, 0.5) + delta

    # 其他标签: 直接查表
    for label_key in ["attachment", "emotion_style", "conflict_style", "time_focus"]:
        label_value = labels.get(label_key, "")
        deltas = _ALL_LABEL_DELTAS.get(label_key, {}).get(label_value, {})
        for dim, delta in deltas.items():
            layer = "deep" if dim in result["deep"] else "surface"
            result[layer][dim] = result[layer].get(dim, 0.5) + delta

    # Clamp 所有值到 [0, 1]
    for layer in ["deep", "surface"]:
        for dim in result[layer]:
            result[layer][dim] = clamp(round(result[layer][dim], 4))

    return result


def personality_to_labels(personality: dict[str, dict[str, float]]) -> dict[str, str]:
    """从 11 维参数推断最可能的标签组合。

    使用反向查表: 对每个标签维度，找增量组合最接近当前参数的值。
    """
    labels: dict[str, str] = {}

    # MBTI: 逐字母反推
    mbti_letters = []
    for dim in ["expression_drive", "warmth_bias", "intimacy_pull"]:
        val = personality.get("surface" if dim != "expression_drive" else "deep", {}).get(dim, 0.5)
        baseline_val = _BASELINE.get("surface" if dim != "expression_drive" else "deep", {}).get(dim, 0.5)
        diff = val - baseline_val
        if dim == "expression_drive":
            mbti_letters.append("E" if diff > 0 else "I")
        elif dim == "warmth_bias":
            mbti_letters.append("F" if diff > 0 else "T")
        elif dim == "intimacy_pull":
            mbti_letters.append("E" if diff > 0 else "I")
    # 简化: 只返回字母差异明显的
    if len(mbti_letters) >= 3:
        labels["mbti"] = "".join(mbti_letters[:4]) if len(mbti_letters) >= 4 else "ISTJ"

    # 其他标签: 使用默认值
    labels["attachment"] = "安全型"
    labels["emotion_style"] = "混合型"
    labels["conflict_style"] = "合作型"
    labels["time_focus"] = "活在当下"

    return labels


def _compute_distance(
    p1: dict[str, dict[str, float]],
    p2: dict[str, dict[str, float]],
) -> float:
    """计算两个人格参数的欧氏距离。"""
    total_sq = 0.0
    count = 0
    for layer in ["deep", "surface"]:
        for dim in p1.get(layer, {}):
            v1 = p1[layer].get(dim, 0.5)
            v2 = p2.get(layer, {}).get(dim, 0.5)
            total_sq += (v1 - v2) ** 2
            count += 1
    if count == 0:
        return 0.0
    return (total_sq / count) ** 0.5


def get_label_options() -> dict[str, list[str]]:
    """获取所有标签可选值 (供 _conf_schema.json 使用)。"""
    return {k: list(v) for k, v in LABEL_OPTIONS.items()}
