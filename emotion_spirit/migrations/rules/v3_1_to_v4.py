"""Migration rules: v3.1 → v4.

Merges life_simulator + proactive_chat into life_sim_v2.
"""
from ..registry import register_migration


@register_migration(from_version=3, to_version=4)
def merge_life_sim_config(config: dict) -> dict:
    """Merge old life_simulator + proactive_chat into life_sim_v2.

    Old:
        life_simulator:
          enable_life_fragment: bool
          mode_a_idle_seconds: int
          mode_a_max_turns: int
        proactive_chat:
          enable_proactive_prompt: bool
          mode_b_min_hours: float
          mode_b_max_hours: float
          mode_b_cooldown_after_trigger_minutes: int
          mode_b_density_threshold: float
          mode_b_density_window_hours: float
          mode_b_full_density_hours: float

    New:
        life_sim_v2:
          enable_proactive_prompt: bool  # from proactive_chat
          plan_generate_hour: 2
          events_per_day_min: 3
          events_per_day_max: 5
          adaptation_threshold: 0.3
          sleep_start_hour: 23
          sleep_end_hour: 7
    """
    # v1.2.5 PR3 (handbook §3.3): 先取旧段, 再 pop
    old_proactive = config.pop("proactive_chat", {})
    old_life_sim = config.pop("life_simulator", {})  # ← 改为 setdefault 前取

    v2 = config.setdefault("life_sim_v2", {})

    # Migrate enable_proactive_prompt from proactive_chat (default True)
    if "enable_proactive_prompt" in old_proactive:
        v2.setdefault("enable_proactive_prompt", old_proactive["enable_proactive_prompt"])
    else:
        v2.setdefault("enable_proactive_prompt", True)

    # v1.2.5 PR3 修: 补搬 enable_life_fragment (旧 schema 字段, handbook §3.3 漏搬)
    v2.setdefault("enable_life_fragment", old_life_sim.get("enable_life_fragment", True))

    # Set defaults for new keys (don't overwrite if already set)
    v2.setdefault("plan_generate_hour", 2)
    v2.setdefault("events_per_day_min", 3)
    v2.setdefault("events_per_day_max", 5)
    v2.setdefault("adaptation_threshold", 0.3)
    v2.setdefault("sleep_start_hour", 23)
    v2.setdefault("sleep_end_hour", 7)

    return config
