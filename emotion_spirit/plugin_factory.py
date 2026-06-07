"""emotion_spirit 插件工厂 (Phase B6.x, P3-1) — thin wrapper。

走 registry.build() 全自动装配, 只剩 config 注入 + 4 NS rebind。
原 426 行手装代码 → ~50 行 thin wrapper。
"""
from __future__ import annotations
from typing import Any

from .registry import ModuleRegistry, build as _registry_build


def _instantiable_modules() -> list[str]:
    """从 registry derive 所有 instantiable module 名字 (filter utility 4: provides=[])。

    Returns:
        ModuleSpec.provides 非空的所有 module name, 顺序跟 registry insertion 一致。
        加新 @register 模块无需改 factory — 自动出现。
    """
    return [n for n, s in ModuleRegistry.get_all().items() if s.provides]


def default_config(
    *,
    data_dir: str | None = None,
    persona_id: str = "",
    labels: dict[str, str] | None = None,
    llm: Any = None,
    gossip_tendency: float = 0.0,
) -> dict[str, Any]:
    """默认配置: 所有 instantiable 模块 enabled, utility (provides=[]) 跳过。

    Args:
        data_dir: SpiritStore 数据目录
        persona_id: superego persona 标识
        labels: IdealSelf 的 5 轴标签
        llm: persona_analyzer 的 LLM callable
        gossip_tendency: bot_decision 的 gossip 倾向 [0, 1]

    Returns:
        形如 {"modules": {name: {"enabled": bool}}, "params": {...}}
    """
    modules = {name: {"enabled": True} for name in _instantiable_modules()}
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
