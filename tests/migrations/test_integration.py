"""End-to-end integration test: simulate full upgrade flow."""
import json
from pathlib import Path

from emotion_spirit.migrations.registry import reset_registry
from emotion_spirit.migrations.runner import run_migrations
from emotion_spirit.migrations.state import MigrationState


def test_full_upgrade_v3_0_to_v3_1(tmp_path):
    """Simulate: user has old config, plugin starts, migration runs, new config persisted.

    This is the integration test that the main.py integration code relies on.
    """
    # 1. Pre-write an old config file
    config_file = tmp_path / "config.json"
    old_config = {
        "persona_mode": "auto",
        "auto_source": "小芙",
        "feature_toggles": {
            "enable_shadow_detector": True,
            "enable_life_simulator": False,  # OLD
            "life_simulator_mode": "passive",  # OLD
        },
        "proactive_chat": {
            "enable_proactive_chat": True,  # OLD NAME
        },
    }
    config_file.write_text(json.dumps(old_config), encoding="utf-8")

    # 2. Load rules (simulating main.py import)
    reset_registry()
    from emotion_spirit.migrations.rules import v3_0_to_v3_1  # noqa: F401

    # 3. Run migration (simulating main.py _run_config_migration_and_reload)
    state = MigrationState(tmp_path).load_or_init()
    file_config = json.loads(config_file.read_text("utf-8"))
    new_config, new_state = run_migrations(file_config, state)

    # 4. Write back (config first, state second)
    config_file.write_text(json.dumps(new_config, ensure_ascii=False, indent=2), encoding="utf-8")
    new_state.save()

    # 5. Verify config was migrated
    migrated = json.loads(config_file.read_text("utf-8"))
    assert "enable_life_simulator" not in migrated["feature_toggles"]
    assert "life_simulator_mode" not in migrated["feature_toggles"]
    assert migrated["life_simulator"]["enable_life_fragment"] is False
    # enable_proactive_chat=True was renamed → True (rename rule runs after split)
    assert migrated["proactive_chat"]["enable_proactive_prompt"] is True
    assert "enable_proactive_chat" not in migrated["proactive_chat"]

    # 6. Verify state was saved
    state_file = tmp_path / "migrations.json"
    assert state_file.exists()
    saved_state = json.loads(state_file.read_text("utf-8"))
    assert saved_state["current_version"] == 3
    assert len(saved_state["applied"]) == 2
    assert all(a["rule"] in ("split_life_simulator_modes", "rename_enable_proactive_chat")
               for a in saved_state["applied"])

    # 7. Second startup with migrated config: should be no-op
    reset_registry()
    from emotion_spirit.migrations.rules import v3_0_to_v3_1  # noqa: F401
    state2 = MigrationState(tmp_path).load_or_init()
    config_v2 = json.loads(config_file.read_text("utf-8"))
    new_config_v2, _ = run_migrations(config_v2, state2)

    # No changes on second run
    assert new_config_v2 == config_v2
