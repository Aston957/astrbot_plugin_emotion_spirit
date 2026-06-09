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
# Phase B Step 3: 数据已迁移到 KnowledgeBase.NARRATIVE_TEMPLATES / KnowledgeBase.VARIANT_KEY



__all__ = [
    "get_narrative",
    "get_personality_params",
    "get_intimacy_weights",
    "get_intimacy_modulation",
    "get_value_behaviors",
    "get_personality_from_labels",
    "get_labels_from_config",
]

def _select_variant(dim: str, personality: dict[str, dict[str, float]] | None) -> str:
    """根据人格参数选择叙事变体 (high/low)。

    基于 Singer (1995): 叙事是特定 Me-Self 的意识表达。
    每个维度只看最相关的 1~2 个参数来选择变体。
    """
    from ..core.knowledge import KnowledgeBase
    if not personality:
        return "high"  # 默认

    surface = personality.get("surface", {})
    key_param, threshold = KnowledgeBase.VARIANT_KEY.get(dim, ("warmth_bias", 0.5))
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
    from ..core.knowledge import KnowledgeBase
    variant = _select_variant(dimension, personality)
    template = KnowledgeBase.NARRATIVE_TEMPLATES.get(dimension, {}).get(variant, {})
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
    from ..core.label_mapper import labels_to_personality

    if isinstance(labels, str):
        # 兼容旧代码: 如果传入字符串，返回空字典
        return {}
    return labels_to_personality(labels)


def get_intimacy_weights() -> dict[str, float]:
    """获取通用亲密度维度权重。"""
    from ..core.config import INTIMACY_CONFIG
    return INTIMACY_CONFIG["weights"]


def get_intimacy_modulation() -> dict[str, float]:
    """获取通用亲密度调制系数。"""
    from ..core.config import INTIMACY_CONFIG
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
    from ..core.label_mapper import labels_to_personality
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


from ..core.registry import register


@register(name="persona_profiles", provides=[], depends_on=[])
class _ModuleMarker:
    """纯函数模块标记 (供 ModuleRegistry 元数据用)。"""
    pass
