"""Migration rules: v3.0 → v3.1.

Three rules:
1. (1→2) split_life_simulator_modes: total switch + 3-state mode → per-mode switches
2. (2→3) rename_enable_proactive_chat: enable_proactive_chat → enable_proactive_prompt
3. (3→4) split_llm_tier: llm_tier.*_provider_id → 各功能段 + diary_schedule → diary
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


@register_migration(from_version=3, to_version=4)
def split_llm_tier(config: dict) -> dict:
    """Migrate llm_tier.*_provider_id → per-feature sections + diary_schedule → diary.

    Old:
        llm_tier:
          engine_provider_id, life_sim_provider_id, analyzer_provider_id,
          dream_provider_id, reflection_provider_id
        diary_schedule:
          schedule_hours

    New:
        sylanne:
          engine_provider_id, analyzer_provider_id
        life_sim_v2:
          ..., life_sim_provider_id
        dream:
          ..., dream_provider_id
        diary:
          enable_diary_llm (default false), diary_provider_id, schedule_hours

    reflection_provider_id → diary.diary_provider_id (semantic rename).
    Idempotent: only migrates keys that exist in source.
    """
    # ─── 1. llm_tier → 各功能段 ───
    llm_tier = config.get("llm_tier", {})
    if isinstance(llm_tier, dict):
        # engine + analyzer → sylanne 段
        for src_key, dst_seg, dst_key in [
            ("engine_provider_id", "sylanne", "engine_provider_id"),
            ("analyzer_provider_id", "sylanne", "analyzer_provider_id"),
            ("life_sim_provider_id", "life_sim_v2", "life_sim_provider_id"),
            ("dream_provider_id", "dream", "dream_provider_id"),
            ("reflection_provider_id", "diary", "diary_provider_id"),
        ]:
            if src_key in llm_tier and llm_tier[src_key]:
                config.setdefault(dst_seg, {})[dst_key] = llm_tier[src_key]

        # 删旧 llm_tier 段 (保守: 只在我们确实迁了内容之后删)
        config.pop("llm_tier", None)

    # ─── 2. diary_schedule → diary 段 ───
    ds = config.get("diary_schedule", {})
    if isinstance(ds, dict) and "schedule_hours" in ds:
        config.setdefault("diary", {})["schedule_hours"] = ds["schedule_hours"]
        config.pop("diary_schedule", None)

    # ─── 3. diary 段默认值兜底 ───
    diary = config.setdefault("diary", {})
    diary.setdefault("enable_diary_llm", False)

    return config
