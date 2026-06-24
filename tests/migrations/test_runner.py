"""Tests for migration runner."""
import pytest
from emotion_spirit.migrations.registry import register_migration, reset_registry
from emotion_spirit.migrations.state import MigrationState


@pytest.fixture(autouse=True)
def clear_registry():
    """Reset registry before each test to avoid cross-test pollution."""
    reset_registry()
    yield
    reset_registry()


def test_run_migrations_no_op_when_current(tmp_path):
    """When state.current_version >= latest, runner returns config unchanged."""
    @register_migration(from_version=1, to_version=2)
    def rule_a(config):
        config["mutated"] = True
        return config

    state = MigrationState(tmp_path).load_or_init()
    state.current_version = 2

    from emotion_spirit.migrations.runner import run_migrations
    config = {"foo": "bar"}
    new_config, new_state = run_migrations(config, state)

    assert "mutated" not in new_config
    assert new_state.current_version == 2


def test_run_migrations_applies_pending_rule(tmp_path):
    """Apply rules whose from_version >= state.current_version."""
    @register_migration(from_version=1, to_version=2)
    def rule_a(config):
        config["a_applied"] = True
        return config

    state = MigrationState(tmp_path).load_or_init()
    config = {}
    from emotion_spirit.migrations.runner import run_migrations
    new_config, new_state = run_migrations(config, state)

    assert new_config.get("a_applied") is True
    assert new_state.current_version == 2
    assert len(new_state.applied) == 1


def test_run_migrations_fail_soft_continues_other_rules(tmp_path):
    """If one rule raises, runner records error and continues with next."""
    @register_migration(from_version=1, to_version=2)
    def rule_broken(config):
        raise ValueError("intentional")

    @register_migration(from_version=2, to_version=3)
    def rule_ok(config):
        config["ok_applied"] = True
        return config

    state = MigrationState(tmp_path).load_or_init()
    config = {}
    from emotion_spirit.migrations.runner import run_migrations
    new_config, new_state = run_migrations(config, state)

    # Broken rule failed but rule_ok still applied
    assert new_config.get("ok_applied") is True
    assert len(new_state.errors) == 1
    assert new_state.errors[0]["rule"] == "rule_broken"
    # current_version advances to latest regardless
    assert new_state.current_version == 3


def test_run_migrations_force_re_runs_all(tmp_path):
    """force=True re-runs all rules regardless of state.current_version."""
    @register_migration(from_version=1, to_version=2)
    def rule_counter(config):
        config["counter"] = config.get("counter", 0) + 1
        return config

    state = MigrationState(tmp_path).load_or_init()
    state.current_version = 2  # already at latest

    from emotion_spirit.migrations.runner import run_migrations
    config = {}
    new_config, new_state = run_migrations(config, state, force=True)

    assert new_config["counter"] == 1  # re-applied once
    assert new_state.current_version == 2


def test_run_migrations_does_not_mutate_input(tmp_path):
    """Original config dict should not be modified."""
    @register_migration(from_version=1, to_version=2)
    def rule_mutates(config):
        config["added"] = "yes"
        return config

    state = MigrationState(tmp_path).load_or_init()
    original = {"foo": "bar"}
    from emotion_spirit.migrations.runner import run_migrations
    new_config, _ = run_migrations(original, state)

    assert "added" not in original
    assert new_config.get("added") == "yes"


def test_run_migrations_skip_already_applied(tmp_path):
    """Don't re-apply rules whose from_version < state.current_version."""
    @register_migration(from_version=1, to_version=2)
    def rule_with_marker(config):
        config.setdefault("applied_count", 0)
        config["applied_count"] += 1
        return config

    state = MigrationState(tmp_path).load_or_init()
    state.current_version = 5  # already past rule_with_marker

    from emotion_spirit.migrations.runner import run_migrations
    config = {}
    new_config, new_state = run_migrations(config, state)

    assert "applied_count" not in new_config  # not re-applied
