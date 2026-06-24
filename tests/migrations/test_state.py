"""Tests for MigrationState."""
import json
from pathlib import Path


def test_load_or_init_when_no_file(tmp_path):
    """No state file → current_version=0, empty applied/errors."""
    from emotion_spirit.migrations.state import MigrationState
    state = MigrationState(tmp_path).load_or_init()
    assert state.current_version == 0
    assert state.applied == []
    assert state.errors == []


def test_record_applied_then_save(tmp_path):
    """record_applied adds entry, save writes to file."""
    from emotion_spirit.migrations.state import MigrationState
    state = MigrationState(tmp_path).load_or_init()
    state.record_applied(1, 2, "rule_a")
    state.record_applied(2, 3, "rule_b")
    state.save()

    # Read back
    raw = json.loads((tmp_path / "migrations.json").read_text("utf-8"))
    assert raw["current_version"] == 0  # not updated until setter
    assert len(raw["applied"]) == 2
    assert raw["applied"][0]["rule"] == "rule_a"
    assert raw["applied"][1]["from"] == 2
    assert "timestamp" in raw["applied"][0]


def test_record_error(tmp_path):
    """record_error appends to errors list."""
    from emotion_spirit.migrations.state import MigrationState
    state = MigrationState(tmp_path).load_or_init()
    state.record_error("rule_x", "KeyError: foo")
    state.save()

    raw = json.loads((tmp_path / "migrations.json").read_text("utf-8"))
    assert len(raw["errors"]) == 1
    assert raw["errors"][0]["rule"] == "rule_x"
    assert raw["errors"][0]["error"] == "KeyError: foo"


def test_load_existing_state(tmp_path):
    """load_or_init reads existing file and restores state."""
    from emotion_spirit.migrations.state import MigrationState
    # Pre-write state file
    state_file = tmp_path / "migrations.json"
    state_file.write_text(json.dumps({
        "current_version": 5,
        "applied": [{"from": 1, "to": 2, "rule": "old_rule", "timestamp": "2026-06-24T10:00:00+08:00"}],
        "errors": [],
    }), encoding="utf-8")

    state = MigrationState(tmp_path).load_or_init()
    assert state.current_version == 5
    assert len(state.applied) == 1
    assert state.applied[0]["rule"] == "old_rule"


def test_current_version_setter(tmp_path):
    """current_version can be set and persists on save."""
    from emotion_spirit.migrations.state import MigrationState
    state = MigrationState(tmp_path).load_or_init()
    state.current_version = 7
    state.save()

    raw = json.loads((tmp_path / "migrations.json").read_text("utf-8"))
    assert raw["current_version"] == 7


def test_to_dict_roundtrip(tmp_path):
    """to_dict returns dict that can be loaded back."""
    from emotion_spirit.migrations.state import MigrationState
    state = MigrationState(tmp_path).load_or_init()
    state.record_applied(1, 2, "test_rule")
    state.current_version = 2

    d = state.to_dict()
    # Manually write and reload
    (tmp_path / "migrations.json").write_text(json.dumps(d), encoding="utf-8")
    state2 = MigrationState(tmp_path).load_or_init()
    assert state2.current_version == 2
    assert state2.applied[0]["rule"] == "test_rule"
