"""Tests for v3.1 → v4 migration rules."""
import importlib
from emotion_spirit.migrations.registry import reset_registry
from emotion_spirit.migrations.runner import run_migrations
from emotion_spirit.migrations.state import MigrationState


def setup_function():
    reset_registry()


def test_merge_life_sim_config(tmp_path):
    """Merges life_simulator + proactive_chat into life_sim_v2."""
    from emotion_spirit.migrations.rules import v3_1_to_v4  # noqa: F401
    importlib.reload(v3_1_to_v4)

    old_config = {
        "life_simulator": {
            "enable_life_fragment": True,
            "mode_a_idle_seconds": 60,
            "mode_a_max_turns": 15,
        },
        "proactive_chat": {
            "enable_proactive_prompt": False,
            "mode_b_min_hours": 2.0,
            "mode_b_max_hours": 4.0,
            "mode_b_cooldown_after_trigger_minutes": 30,
        },
    }
    state = MigrationState(tmp_path)
    state.current_version = 3
    new_config, _ = run_migrations(old_config, state)

    # Old sections removed
    assert "life_simulator" not in new_config
    assert "proactive_chat" not in new_config

    # New section created with migrated value
    v2 = new_config["life_sim_v2"]
    assert v2["enable_proactive_prompt"] is False  # migrated from proactive_chat

    # Defaults set
    assert v2["plan_generate_hour"] == 2
    assert v2["events_per_day_min"] == 3
    assert v2["events_per_day_max"] == 5
    assert v2["adaptation_threshold"] == 0.3
    assert v2["sleep_start_hour"] == 23
    assert v2["sleep_end_hour"] == 7


def test_merge_life_sim_config_no_old_sections(tmp_path):
    """No old sections → defaults only."""
    from emotion_spirit.migrations.rules import v3_1_to_v4  # noqa: F401
    importlib.reload(v3_1_to_v4)

    old_config = {"persona_mode": "auto"}
    state = MigrationState(tmp_path)
    state.current_version = 3
    new_config, _ = run_migrations(old_config, state)

    v2 = new_config["life_sim_v2"]
    assert v2["enable_proactive_prompt"] is True  # default
    assert v2["plan_generate_hour"] == 2


def test_merge_preserves_existing_v2(tmp_path):
    """If life_sim_v2 already exists, don't overwrite."""
    from emotion_spirit.migrations.rules import v3_1_to_v4  # noqa: F401
    importlib.reload(v3_1_to_v4)

    old_config = {
        "proactive_chat": {"enable_proactive_prompt": False},
        "life_sim_v2": {"plan_generate_hour": 5, "sleep_start_hour": 22},
    }
    state = MigrationState(tmp_path)
    state.current_version = 3
    new_config, _ = run_migrations(old_config, state)

    v2 = new_config["life_sim_v2"]
    assert v2["plan_generate_hour"] == 5  # preserved
    assert v2["sleep_start_hour"] == 22  # preserved
    assert v2["enable_proactive_prompt"] is False  # migrated
