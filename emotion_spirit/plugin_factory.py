"""emotion_spirit 插件工厂 (Phase B6.x, P3-1) — thin wrapper。

走 registry.build() 全自动装配, 只剩 config 注入 + 4 NS rebind。
原 426 行手装代码 → ~50 行 thin wrapper。
"""
from __future__ import annotations
from typing import Any

from .registry import build as _registry_build


# 24 个有 provides 的模块 (utility 4 不实例化: emotion_classifier/label_mapper/persona_profiles/trend_utils)
_INSTANTIABLE_MODULES = [
    "store", "surface_consumer", "memory_pool", "buffer_signals", "intimacy",
    "superego", "superego_guard", "meaning_reservoir", "pattern_extractor",
    "shadow_detector", "life_simulator", "diary_writer", "prompt_injector",
    "personality_drift", "predictive_sentinel", "narrative_identity",
    "counterfactual", "persona_analyzer", "relationship_personality",
    "social_graph", "topic_privacy", "bot_decision", "knowledge",
    "persona_report_parser",
]


def default_config(
    *,
    data_dir: str | None = None,
    persona_id: str = "",
    labels: dict[str, str] | None = None,
    llm: Any = None,
    gossip_tendency: float = 0.0,
) -> dict[str, Any]:
    """默认配置: 24 模块 enabled, utility 4 跳过。

    Args:
        data_dir: SpiritStore 数据目录
        persona_id: superego persona 标识
        labels: IdealSelf 的 5 轴标签
        llm: persona_analyzer 的 LLM callable
        gossip_tendency: bot_decision 的 gossip 倾向 [0, 1]

    Returns:
        形如 {"modules": {name: {"enabled": bool}}, "params": {...}}
    """
    modules = {name: {"enabled": True} for name in _INSTANTIABLE_MODULES}
    return {
        "modules": modules,
        "params": {
            "data_dir": data_dir or "data",
            "persona_id": persona_id,
            "labels": labels or {},
            "llm": llm,
            "gossip_tendency": gossip_tendency,
        },
    }


def build(config: dict[str, Any]) -> dict[str, Any]:
    """装配所有 enabled 模块, 返回 dict[name, instance]。

    Thin wrapper around registry.build() — 99% 工作在 registry。
    这一层只处理:
    1. 调 registry.build() 装配
    2. store._rebind_ns() 兜底 (Phase C1 NS shared-ref)
    3. main.py 接口一致性 (旧 build() 跟新 build() 同形)
    """
    out = _registry_build(config)
    return out
