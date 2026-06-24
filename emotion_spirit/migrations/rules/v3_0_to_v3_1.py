"""Migration rules: v3.0 → v3.1.

Three rules:
1. (1→2) split_life_simulator_modes: total switch + 3-state mode → per-mode switches
2. (2→3) rename_enable_proactive_chat: enable_proactive_chat → enable_proactive_prompt
"""
from ..registry import register_migration


@register_migration(from_version=1, to_version=2)
def split_life_simulator_modes(config: dict) -> dict:
    """Migrate feature_toggles.life_simulator_mode → per-mode switches.

    Old:
        feature_toggles:
          enable_life_simulator: bool (total)
          life_simulator_mode: "both" | "passive" | "silent"

    New:
        life_simulator:
          enable_life_fragment: bool  # Mode A: 对话中插入
        proactive_chat:
          enable_proactive_prompt: bool  # Mode B: 离线后注入 prompt
    """
    toggles = config.get("feature_toggles", {})
    total_disabled = False

    # 处理 enable_life_simulator 总开关 (false → 两个 mode 都关)
    if "enable_life_simulator" in toggles:
        if toggles["enable_life_simulator"] is False:
            config.setdefault("life_simulator", {})["enable_life_fragment"] = False
            config.setdefault("proactive_chat", {})["enable_proactive_prompt"] = False
            total_disabled = True
        del toggles["enable_life_simulator"]

    # 处理 life_simulator_mode (总开关关时不覆盖)
    mode = toggles.pop("life_simulator_mode", None)
    if mode is not None and not total_disabled:
        config.setdefault("life_simulator", {})["enable_life_fragment"] = mode in ("both", "passive")
        config.setdefault("proactive_chat", {})["enable_proactive_prompt"] = mode in ("both", "silent")

    return config


@register_migration(from_version=2, to_version=3)
def rename_enable_proactive_chat(config: dict) -> dict:
    """Migrate proactive_chat.enable_proactive_chat → enable_proactive_prompt."""
    pc = config.get("proactive_chat", {})
    if "enable_proactive_chat" in pc:
        pc["enable_proactive_prompt"] = pc.pop("enable_proactive_chat")
    return config
