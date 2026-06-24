"""Tests for v3.0 → v3.1 migration rules."""
import pytest
from emotion_spirit.migrations.registry import register_migration, reset_registry
from emotion_spirit.migrations.runner import run_migrations
from emotion_spirit.migrations.state import MigrationState


@pytest.fixture(autouse=True)
def clear_registry():
    reset_registry()
    yield
    reset_registry()


def _load_rules():
    """Import rules module to register them (reload to re-register after reset)."""
    import importlib
    from emotion_spirit.migrations.rules import v3_0_to_v3_1
    importlib.reload(v3_0_to_v3_1)


def test_split_modes_both():
    """life_simulator_mode='both' → both per-mode switches True."""
    _load_rules()
    config = {"feature_toggles": {"life_simulator_mode": "both"}}
    state = MigrationState.__new__(MigrationState)  # avoid file IO
    state._data = {"current_version": 0, "applied": [], "errors": []}
    new_config, _ = run_migrations(config, state)

    assert "life_simulator_mode" not in new_config["feature_toggles"]
    assert new_config["life_simulator"]["enable_life_fragment"] is True
    assert new_config["proactive_chat"]["enable_proactive_prompt"] is True


def test_split_modes_passive():
    """life_simulator_mode='passive' → Mode A on, Mode B off."""
    _load_rules()
    config = {"feature_toggles": {"life_simulator_mode": "passive"}}
    state = MigrationState.__new__(MigrationState)
    state._data = {"current_version": 0, "applied": [], "errors": []}
    new_config, _ = run_migrations(config, state)

    assert new_config["life_simulator"]["enable_life_fragment"] is True
    assert new_config["proactive_chat"]["enable_proactive_prompt"] is False


def test_split_modes_silent():
    """life_simulator_mode='silent' → Mode A off, Mode B on."""
    _load_rules()
    config = {"feature_toggles": {"life_simulator_mode": "silent"}}
    state = MigrationState.__new__(MigrationState)
    state._data = {"current_version": 0, "applied": [], "errors": []}
    new_config, _ = run_migrations(config, state)

    assert new_config["life_simulator"]["enable_life_fragment"] is False
    assert new_config["proactive_chat"]["enable_proactive_prompt"] is True


def test_enable_life_simulator_false_disables_both():
    """enable_life_simulator=False → both per-mode switches off."""
    _load_rules()
    config = {"feature_toggles": {"enable_life_simulator": False}}
    state = MigrationState.__new__(MigrationState)
    state._data = {"current_version": 0, "applied": [], "errors": []}
    new_config, _ = run_migrations(config, state)

    assert "enable_life_simulator" not in new_config["feature_toggles"]
    assert new_config["life_simulator"]["enable_life_fragment"] is False
    assert new_config["proactive_chat"]["enable_proactive_prompt"] is False


def test_enable_life_simulator_true_no_change():
    """enable_life_simulator=True → both per-mode switches default (no override)."""
    _load_rules()
    config = {"feature_toggles": {"enable_life_simulator": True}}
    state = MigrationState.__new__(MigrationState)
    state._data = {"current_version": 0, "applied": [], "errors": []}
    new_config, _ = run_migrations(config, state)

    assert "enable_life_simulator" not in new_config["feature_toggles"]
    # per-mode switches NOT set by this rule (they keep their defaults)
    assert "enable_life_fragment" not in new_config.get("life_simulator", {})


def test_rename_enable_proactive_chat():
    """proactive_chat.enable_proactive_chat → enable_proactive_prompt."""
    _load_rules()
    config = {"proactive_chat": {"enable_proactive_chat": False}}
    state = MigrationState.__new__(MigrationState)
    state._data = {"current_version": 0, "applied": [], "errors": []}
    new_config, _ = run_migrations(config, state)

    assert "enable_proactive_chat" not in new_config["proactive_chat"]
    assert new_config["proactive_chat"]["enable_proactive_prompt"] is False


def test_combined_old_config_full_migration(tmp_path):
    """Old config with all 3 issues → fully migrated to new schema."""
    _load_rules()
    old_config = {
        "feature_toggles": {
            "enable_life_simulator": False,
            "life_simulator_mode": "passive",
        },
        "proactive_chat": {
            "enable_proactive_chat": False,
        },
    }
    state = MigrationState(tmp_path).load_or_init()
    new_config, new_state = run_migrations(old_config, state)

    # Old keys gone
    assert "enable_life_simulator" not in new_config["feature_toggles"]
    assert "life_simulator_mode" not in new_config["feature_toggles"]
    assert "enable_proactive_chat" not in new_config["proactive_chat"]

    # New keys present
    assert new_config["life_simulator"]["enable_life_fragment"] is False  # enable_life_simulator=False
    assert new_config["proactive_chat"]["enable_proactive_prompt"] is False  # both rules agree

    # State recorded both rule applications
    assert new_state.current_version == 3
    assert len(new_state.applied) == 2


def test_idempotent_no_op_when_already_migrated(tmp_path):
    """Running migration on already-migrated config is a no-op."""
    _load_rules()
    new_config_already = {
        "feature_toggles": {},
        "life_simulator": {"enable_life_fragment": True},
        "proactive_chat": {"enable_proactive_prompt": True},
    }
    state = MigrationState(tmp_path).load_or_init()
    state.current_version = 3
    result, _ = run_migrations(new_config_already, state)

    # No changes
    assert result == new_config_already
