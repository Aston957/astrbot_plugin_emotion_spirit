"""人格映射 — 标签 → Sylanne 12 维 + 价值观映射。

v1.7: 12 维 (autonomy_guard 拆分为 relational_autonomy + exploration_openness)

所有人格参数通过 label_mapper 从标签推导，不再使用硬编码预设。
初始化时从 AstrBot 人格报告自动解析标签，或由用户手动配置。
价值观从 12 维人格维度动态推导，不按 persona 硬编码。
"""

from __future__ import annotations

from typing import Any


# ═══ 叙事模板 ═══
# 基于 Raggatt (2006) + Mairesse (2007): 不同人格参数 → 不同叙事表达。
# 每个维度 × 2 变体 (high/low) × 3 场景 (violation/alignment/advice) = 66 条模板。

# v1.7.2: @deprecated, 数据已迁移到 KnowledgeBase (Phase B Step 2, P3-2)
# 推荐: from emotion_spirit.knowledge import KnowledgeBase
# B3 才删, B2 alias 保留
# 维度 → (选择变体的关键参数, 阈值)
_VARIANT_KEY_DEPRECATED: dict[str, tuple[str, float]] = {
    "relational_gravity": ("warmth_bias", 0.5),
    "intimacy_pull": ("warmth_bias", 0.5),
    "warmth_bias": ("intimacy_pull", 0.3),
    "expression_drive": ("directness", 0.7),
    "inner_coherence": ("directness", 0.7),
    "curiosity": ("perception_acuity", 0.7),
    "perception_acuity": ("curiosity", 0.6),
    "directness": ("expression_drive", 0.5),
    "patience": ("warmth_bias", 0.5),
    # v1.7: autonomy_guard 拆分为 2 维
    "relational_autonomy": ("intimacy_pull", 0.3),
    "exploration_openness": ("curiosity", 0.5),
    "boundary_permeability": ("relational_autonomy", 0.6),  # v1.7: 改用 relational_autonomy
}
_VARIANT_KEY = _VARIANT_KEY_DEPRECATED  # @deprecated alias

NARRATIVE_TEMPLATES_DEPRECATED: dict[str, dict[str, dict[str, str]]] = {
    "relational_gravity": {
        "high": {
            "violation": "你最近好像忽略了那些你在乎的人",
            "alignment": "你一直在用心对待身边的人",
            "advice": "试着主动联系一个你想念的人",
        },
        "low": {
            "violation": "你和人之间的距离好像变远了",
            "alignment": "你最近在试着靠近别人",
            "advice": "也许该给自己一个和人连接的机会",
        },
    },
    "intimacy_pull": {
        "high": {
            "violation": "你好像在回避亲密感",
            "alignment": "你最近在敞开心扉",
            "advice": "试着对一个人说出你真实的想法",
        },
        "low": {
            "violation": "你最近有点太封闭了",
            "alignment": "你最近保持着合适的距离",
            "advice": "不需要勉强自己，但可以试着打开一点点",
        },
    },
    "warmth_bias": {
        "high": {
            "violation": "你最近好像对人有点冷淡",
            "alignment": "你一直在温暖地对待周围的人",
            "advice": "做一件小事让你在乎的人感受到你的关心",
        },
        "low": {
            "violation": "你最近好像忘了照顾自己",
            "alignment": "你最近在关注自己的需求",
            "advice": "先照顾好自己，再考虑别人",
        },
    },
    "expression_drive": {
        "high": {
            "violation": "你最近好像把很多话藏在心里",
            "alignment": "你一直在诚实地表达自己",
            "advice": "试着把你想说的话说出来，哪怕只是对自己",
        },
        "low": {
            "violation": "你最近好像说得太多了",
            "alignment": "你最近保持着适当的沉默",
            "advice": "有时候沉默也是一种表达",
        },
    },
    "inner_coherence": {
        "high": {
            "violation": "你最近的言行好像不太一致",
            "alignment": "你一直在保持内心的统一",
            "advice": "回顾一下你真正相信的是什么",
        },
        "low": {
            "violation": "你最近好像有点混乱",
            "alignment": "你最近在试着理清思路",
            "advice": "不用急着找答案，先接受这种不确定",
        },
    },
    "curiosity": {
        "high": {
            "violation": "你最近好像对什么都提不起兴趣",
            "alignment": "你一直在探索新的东西",
            "advice": "去做一件你从没做过的事",
        },
        "low": {
            "violation": "你最近好像被新事物压得喘不过气",
            "alignment": "你最近在专注于已知的事物",
            "advice": "不一定要探索新的，把眼前的做好也很重要",
        },
    },
    "perception_acuity": {
        "high": {
            "violation": "你最近好像忽略了一些细节",
            "alignment": "你一直在敏锐地观察周围",
            "advice": "花点时间安静下来，感受一下周围的氛围",
        },
        "low": {
            "violation": "你最近好像过度敏感了",
            "alignment": "你最近在适当放松注意力",
            "advice": "不是每件事都需要你去注意",
        },
    },
    "directness": {
        "high": {
            "violation": "你最近好像在拐弯抹角",
            "alignment": "你一直很坦率",
            "advice": "试着直接说出你的想法",
        },
        "low": {
            "violation": "你最近好像太直接了",
            "alignment": "你最近在注意说话的方式",
            "advice": "有时候委婉一点效果更好",
        },
    },
    "patience": {
        "high": {
            "violation": "你最近好像有点急躁",
            "alignment": "你一直在耐心地等待",
            "advice": "给自己多一点时间，不用急",
        },
        "low": {
            "violation": "你最近好像等太久了",
            "alignment": "你最近在适当加快节奏",
            "advice": "有些事值得等待，但不值得无限期地等",
        },
    },
    # v1.7: autonomy_guard 拆分 → relational_autonomy + exploration_openness
    "relational_autonomy": {
        "high": {
            "violation": "你最近好像把别人推得太远了",
            "alignment": "你一直在守护自己的边界",
            "advice": "有时候让别人靠近一点也没关系",
        },
        "low": {
            "violation": "你最近好像太容易让步了",
            "alignment": "你最近在学习为自己说话",
            "advice": "试着温和但坚定地表达你的界限",
        },
    },
    # v1.7: 新维度 exploration_openness
    "exploration_openness": {
        "high": {
            "violation": "你最近好像对新事物失去了兴趣",
            "alignment": "你一直在尝试新的可能",
            "advice": "去做一件你从没做过的事",
        },
        "low": {
            "violation": "你最近好像被新事物压得喘不过气",
            "alignment": "你最近在专注于已有的一切",
            "advice": "不一定要探索新的，把眼前的做好也很重要",
        },
    },
    "boundary_permeability": {
        "high": {
            "violation": "你最近好像让太多东西进来了",
            "alignment": "你最近在适当打开自己",
            "advice": "学会说'不'也是一种自我保护",
        },
        "low": {
            "violation": "你最近好像把自己关得太紧了",
            "alignment": "你最近在保持适当的边界",
            "advice": "试着让一点点新的东西进来",
        },
    },
}
NARRATIVE_TEMPLATES = NARRATIVE_TEMPLATES_DEPRECATED  # @deprecated alias


def _select_variant(dim: str, personality: dict[str, dict[str, float]] | None) -> str:
    """根据人格参数选择叙事变体 (high/low)。

    基于 Singer (1995): 叙事是特定 Me-Self 的意识表达。
    每个维度只看最相关的 1~2 个参数来选择变体。
    """
    if not personality:
        return "high"  # 默认

    surface = personality.get("surface", {})
    key_param, threshold = _VARIANT_KEY.get(dim, ("warmth_bias", 0.5))
    val = surface.get(key_param, 0.5)
    return "high" if val > threshold else "low"


def get_narrative(
    dimension: str,
    scene: str,
    personality: dict[str, dict[str, float]] | None,
) -> str:
    """获取维度的人格化叙事。

    基于 Raggatt (2006): 不同人格 → 不同叙事主题。
    基于 Mairesse (2007): 人格影响词汇选择。

    Args:
        dimension: 维度名 (如 "relational_gravity")
        scene: 场景 ("violation" / "alignment" / "advice")
        personality: 当前 13 维参数

    Returns:
        人格化的中文叙事文本
    """
    variant = _select_variant(dimension, personality)
    template = NARRATIVE_TEMPLATES.get(dimension, {}).get(variant, {})
    return template.get(scene, DIMENSION_DISPLAY.get(dimension, dimension))


# ═══ 通用动作 → 维度映射 ═══
# 每个动作对齐/冲突的维度，用于 ValueResistance / ValueAlignment 判断。
# 不按 persona 区分 — 差异由各维度权重（从标签推导）体现。

_ACTION_ALIGN: dict[str, list[str]] = {
    "express": ["expression_drive", "warmth_bias"],
    "reach_out": ["relational_gravity", "intimacy_pull"],
    "explore": ["curiosity", "perception_acuity"],
    "repair": ["warmth_bias", "relational_gravity"],
    "hold": ["relational_autonomy", "inner_coherence"],  # v1.7: 替换 autonomy_guard
    "withdraw": ["relational_autonomy"],  # v1.7: 替换 autonomy_guard
    "observe": ["perception_acuity", "patience"],
    "recover": ["inner_coherence", "patience"],
}

_ACTION_MISALIGN: dict[str, list[str]] = {
    "express": ["relational_autonomy"],  # v1.7: 替换 autonomy_guard
    "hold": ["expression_drive"],  # v2: 减少混合动作 (Weiner; 行为语义匹配)
    "withdraw": ["relational_gravity", "intimacy_pull"],
    "reach_out": ["relational_autonomy"],  # v1.7: 替换 autonomy_guard
    "explore": ["patience", "inner_coherence"],
    "observe": [],  # v2: 中性观察动作，无冲突维度
    "recover": ["curiosity", "directness"],
    "repair": ["boundary_permeability"],
    # 纯冲突动作 (用于 tension 分类测试，无 aligned 值)
    "deny": ["warmth_bias", "relational_gravity"],       # → guilt
    "suppress": ["inner_coherence", "curiosity"],         # → doubt
    "avoid": ["patience", "relational_autonomy"],         # v1.7: 替换 autonomy_guard → shame
}

# 维度 → 中文显示名（用于自然语言输出）
DIMENSION_DISPLAY: dict[str, str] = {
    "expression_drive": "表达自我",
    "perception_acuity": "感知敏锐",
    "boundary_permeability": "边界通透",
    "inner_coherence": "内在一致",
    "relational_gravity": "关系维系",
    "warmth_bias": "温暖关怀",
    "directness": "直接坦率",
    "curiosity": "好奇探索",
    "patience": "耐心等待",
    "intimacy_pull": "亲密渴望",
    # v1.7: autonomy_guard 拆分为 2 维
    "relational_autonomy": "关系边界",
    "exploration_openness": "探索开放",
}


def get_personality_params(labels: dict[str, str] | str) -> dict[str, dict[str, float]]:
    """从标签推导 Sylanne 12 维 personality 参数 (v1.7: 11→12)。

    支持两种输入:
    - dict: 直接使用标签字典
    - str: 视为 persona 名称，返回空字典 (已弃用预设)
    """
    from .label_mapper import labels_to_personality

    if isinstance(labels, str):
        # 兼容旧代码: 如果传入字符串，返回空字典
        return {}
    return labels_to_personality(labels)


def get_intimacy_weights() -> dict[str, float]:
    """获取通用亲密度维度权重。"""
    from .config import INTIMACY_CONFIG
    return INTIMACY_CONFIG["weights"]


def get_intimacy_modulation() -> dict[str, float]:
    """获取通用亲密度调制系数。"""
    from .config import INTIMACY_CONFIG
    return INTIMACY_CONFIG["modulation"]


def get_value_behaviors() -> dict[str, dict[str, list[str]]]:
    """获取通用动作→维度映射。

    返回 {维度名: {aligned: [动作], misaligned: [动作]}} 格式。
    不按 persona 区分 — 差异由各维度权重体现。
    """
    result: dict[str, dict[str, list[str]]] = {}
    for action, dims in _ACTION_ALIGN.items():
        for dim in dims:
            result.setdefault(dim, {"aligned": [], "misaligned": []})
            result[dim]["aligned"].append(action)
    for action, dims in _ACTION_MISALIGN.items():
        for dim in dims:
            result.setdefault(dim, {"aligned": [], "misaligned": []})
            result[dim]["misaligned"].append(action)
    return result


def get_personality_from_labels(labels: dict[str, str]) -> dict[str, dict[str, float]]:
    """从标签组合推导 13 维参数。"""
    from .label_mapper import labels_to_personality
    return labels_to_personality(labels)


def get_labels_from_config(config: dict[str, Any]) -> dict[str, str]:
    """从 AstrBot 配置中提取标签。"""
    return {
        "mbti": config.get("mbti", ""),
        "attachment": config.get("attachment", ""),
        "emotion_style": config.get("emotion_style", ""),
        "conflict_style": config.get("conflict_style", ""),
        "time_focus": config.get("time_focus", ""),
    }
