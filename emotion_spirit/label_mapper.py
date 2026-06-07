"""标签映射器 — 人类可读标签 ↔ SylannEngine 12 维参数。

每个标签维度对 12 维参数有增量贡献:
  最终值 = 基线 + Σ(各标签增量)

v1.7 (Phase 1.7): autonomy_guard 拆分为 relational_autonomy + exploration_openness
  - relational_autonomy (关系边界强度) — 受 attachment + conflict + T/F 主导
  - exploration_openness (探索新输入) — 受 N/S + time_focus 主导
  - 原 11 维 autonomy_guard 已删除 (Phase 1.7 design review 决策)

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
        "intimacy_pull": 0.25,  # v1.7.1: 0.15→0.25 (留 noise margin 避免触底 0)
        # v1.7: autonomy_guard 拆分
        "relational_autonomy": 0.60,  # 略高, 反映"bot 普遍偏独立"
        "exploration_openness": 0.55,  # v1.7.1: 0.50→0.55 (留 noise margin)
        "gossip_tendency": 0.40,  # v1.7.2: +gossip_tendency (HEXACO H 反向 + E 正向)
    },
}


# ═══ 13 维 personality 权威集合 (v1.7.2: 12→13, +gossip_tendency) ═══

PERSONALITY_DIMS_DEEP: frozenset[str] = frozenset({
    "expression_drive",
    "perception_acuity",
    "boundary_permeability",
    "inner_coherence",
    "relational_gravity",
})

PERSONALITY_DIMS_SURFACE: frozenset[str] = frozenset({
    "warmth_bias",
    "directness",
    "curiosity",
    "patience",
    "intimacy_pull",
    "relational_autonomy",
    "exploration_openness",
    "gossip_tendency",  # v1.7.2: Erdoğan 2014 + HEXACO 2007 支撑
})

ALL_PERSONALITY_DIMS: frozenset[str] = PERSONALITY_DIMS_DEEP | PERSONALITY_DIMS_SURFACE


# ═══ 5 persona baseline (含 gossip_tendency, v1.7.2) ═══
# 依据: Erdoğan 2014 (gossip 实证) + HEXACO 2007 (H 维度) + Dark Triad (低 A → 战略 gossip)
# spread 0.55, 强区分, 全部在 HEXACO 预测区间

PERSONA_BASELINES: dict[str, dict[str, float]] = {
    "INFP-A": {
        "warmth_bias": 0.45, "intimacy_pull": 0.30, "relational_autonomy": 0.20,
        "exploration_openness": 0.75, "gossip_tendency": 0.15,
    },
    "ISTJ-S": {
        "warmth_bias": 0.30, "intimacy_pull": 0.15, "relational_autonomy": 0.90,
        "exploration_openness": 0.40, "gossip_tendency": 0.15,
    },
    "ENTP-AV": {
        "warmth_bias": 0.40, "intimacy_pull": 0.45, "relational_autonomy": 0.85,
        "exploration_openness": 0.95, "gossip_tendency": 0.70,
    },
    "ISFJ-D": {
        "warmth_bias": 0.50, "intimacy_pull": 0.40, "relational_autonomy": 0.55,
        "exploration_openness": 0.15, "gossip_tendency": 0.15,
    },
    "ESTP-A": {
        "warmth_bias": 0.35, "intimacy_pull": 0.50, "relational_autonomy": 0.45,
        "exploration_openness": 0.55, "gossip_tendency": 0.70,
    },
}


# ═══ MBTI 增量 (每个字母维度的贡献) ═══
# @deprecated: Phase B Step 1 (P3-2) — 数据已迁移到 KnowledgeBase.MBTI_LETTER_DELTAS
# 此处保留 _DEPRECATED 副本 + 别名以便 B3 之前旧代码仍能 import。
# 包含 v1.7.2 的 I/E gossip_tendency delta (HEXACO 2007)。
_MBTI_LETTER_DELTAS_DEPRECATED: dict[str, dict[str, float]] = {
    # I vs E
    # v1.7.2: gossip_tendency 增加 I/E delta (HEXACO 2007: E 维度强烈预测 gossip 倾向)
    "I": {"expression_drive": -0.10, "warmth_bias": -0.05, "intimacy_pull": -0.10, "exploration_openness": -0.05, "gossip_tendency": -0.25},
    "E": {"expression_drive": +0.15, "warmth_bias": +0.10, "intimacy_pull": +0.10, "exploration_openness": +0.05, "gossip_tendency": +0.30},
    # N vs S (N/S 是 exploration_openness 的主导信号)
    "N": {"curiosity": +0.15, "perception_acuity": +0.05, "boundary_permeability": +0.10, "exploration_openness": +0.20},
    "S": {"curiosity": -0.10, "perception_acuity": -0.05, "inner_coherence": +0.05, "exploration_openness": -0.15},
    # F vs T (F/T 跟 relational_autonomy 相关)
    "F": {"warmth_bias": +0.20, "relational_gravity": +0.15, "intimacy_pull": +0.15, "relational_autonomy": -0.05},
    "T": {"warmth_bias": -0.10, "directness": +0.10, "inner_coherence": +0.05, "relational_autonomy": +0.10},
    # P vs J (v1.7: autonomy_guard 拆, P/J 影响 relational_autonomy 弱)
    "P": {"boundary_permeability": +0.15, "patience": -0.10, "relational_autonomy": -0.05},
    "J": {"inner_coherence": +0.05, "patience": +0.05, "relational_autonomy": +0.05},
}
# @deprecated: 别名, 保留旧 import 路径工作; B3 将删除。
_MBTI_LETTER_DELTAS = _MBTI_LETTER_DELTAS_DEPRECATED


# ═══ 依恋类型增量 ═══
# @deprecated: Phase B Step 1 (P3-2) — 数据已迁移到 KnowledgeBase.ATTACHMENT_DELTAS
_ATTACHMENT_DELTAS_DEPRECATED: dict[str, dict[str, float]] = {
    "安全型": {
        "boundary_permeability": +0.10,
        "inner_coherence": +0.10,
        "intimacy_pull": +0.05,
        "relational_autonomy": +0.05,  # v1.7: 替换 autonomy_guard
        "exploration_openness": +0.10,
    },
    "焦虑型": {
        "boundary_permeability": +0.25,
        "inner_coherence": -0.20,
        "intimacy_pull": +0.30,
        "relational_autonomy": -0.15,  # v1.7: 替换 autonomy_guard (-0.25 → -0.15)
        "exploration_openness": -0.05,
        "expression_drive": +0.15,
    },
    "回避型": {
        "boundary_permeability": -0.20,
        "inner_coherence": +0.10,
        "intimacy_pull": -0.20,
        "relational_autonomy": +0.20,  # v1.7: 替换 autonomy_guard (+0.25 → +0.20)
        "exploration_openness": -0.15,
        "expression_drive": -0.15,
    },
    "混乱型": {
        "boundary_permeability": +0.10,
        "inner_coherence": -0.30,
        "intimacy_pull": +0.10,
        "relational_autonomy": -0.10,  # v1.7: 替换 autonomy_guard
        "exploration_openness": +0.05,
        "expression_drive": +0.05,
    },
}
# @deprecated: 别名, B3 删除。
_ATTACHMENT_DELTAS = _ATTACHMENT_DELTAS_DEPRECATED


# ═══ 情绪策略增量 ═══
# @deprecated: Phase B Step 1 (P3-2) — 数据已迁移到 KnowledgeBase.EMOTION_STYLE_DELTAS
_EMOTION_STYLE_DELTAS_DEPRECATED: dict[str, dict[str, float]] = {
    "表达型": {
        "expression_drive": +0.20,
        "warmth_bias": +0.15,
        "perception_acuity": +0.05,
        "relational_autonomy": -0.05,  # v1.7: 表达 = 暴露 = 让步
        "exploration_openness": +0.10,  # v1.7: 表达 = 探索情绪
    },
    "压抑型": {
        "expression_drive": -0.15,
        "warmth_bias": -0.10,
        "directness": +0.10,
        "perception_acuity": +0.10,
        "relational_autonomy": +0.10,  # v1.7: 压抑 = 内部边界
        "exploration_openness": -0.10,  # v1.7: 压抑 = 保守
    },
    "混合型": {
        "expression_drive": +0.05,
        "warmth_bias": +0.05,
    },
}
# @deprecated: 别名, B3 删除。
_EMOTION_STYLE_DELTAS = _EMOTION_STYLE_DELTAS_DEPRECATED


# ═══ 冲突风格增量 ═══
# @deprecated: Phase B Step 1 (P3-2) — 数据已迁移到 KnowledgeBase.CONFLICT_STYLE_DELTAS
_CONFLICT_STYLE_DELTAS_DEPRECATED: dict[str, dict[str, float]] = {
    "攻击型": {
        "directness": +0.15,
        "relational_autonomy": +0.10,  # v1.7: 替换 autonomy_guard
        "patience": -0.15,
        "warmth_bias": -0.10,
        "exploration_openness": +0.10,  # v1.7: 攻击 = 主动尝试
    },
    "回避型": {
        "directness": -0.20,
        "relational_autonomy": +0.05,  # v1.7: 替换 autonomy_guard
        "patience": +0.15,
        "expression_drive": -0.10,
        "exploration_openness": -0.05,  # v1.7
    },
    "顺应型": {
        "directness": -0.10,
        "relational_autonomy": -0.05,  # v1.7: 替换 autonomy_guard (-0.15 → -0.05)
        "patience": +0.10,
        "warmth_bias": +0.15,
        "intimacy_pull": +0.10,
        "exploration_openness": -0.10,  # v1.7
    },
    "合作型": {
        "directness": +0.05,
        "patience": +0.10,
        "warmth_bias": +0.10,
        "inner_coherence": +0.05,
        "exploration_openness": +0.10,  # v1.7: 合作 = 探索解
    },
}
# @deprecated: 别名, B3 删除。
_CONFLICT_STYLE_DELTAS = _CONFLICT_STYLE_DELTAS_DEPRECATED


# ═══ 时间取向增量 ═══
# @deprecated: Phase B Step 1 (P3-2) — 数据已迁移到 KnowledgeBase.TIME_FOCUS_DELTAS
_TIME_FOCUS_DELTAS_DEPRECATED: dict[str, dict[str, float]] = {
    "活在过去": {
        "perception_acuity": +0.15,
        "inner_coherence": -0.10,
        "relational_gravity": +0.10,
        "relational_autonomy": +0.10,  # v1.7: 传统 = 强边界
        "exploration_openness": -0.10,  # v1.7: 传统 = 保守
    },
    "活在当下": {
        "perception_acuity": +0.05,
        "patience": +0.05,
    },
    "活在未来": {
        "curiosity": +0.10,
        "boundary_permeability": +0.05,
        "inner_coherence": -0.05,
        "relational_autonomy": -0.05,  # v1.7: 灵活
        "exploration_openness": +0.15,  # v1.7: 前瞻 = 探索
    },
}
# @deprecated: 别名, B3 删除。
_TIME_FOCUS_DELTAS = _TIME_FOCUS_DELTAS_DEPRECATED


# ═══ 汇总 ═══
# @deprecated: Phase B Step 1 (P3-2) — 内部聚合, B3 改为使用 KnowledgeBase 路径
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
    """将标签组合映射为 SylannEngine 13 维参数。"""
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
    """从 12 维参数推断最可能的标签组合。

    使用反向查表: 对每个标签维度，找增量组合最接近当前参数的值。
    v1.7: 12 维 (relational_autonomy + exploration_openness 替代 autonomy_guard)
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
