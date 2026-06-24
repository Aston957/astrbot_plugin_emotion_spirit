# Config Migration Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a general-purpose config migration framework that auto-migrates old `cmd_config.json` to new schema, with 3 specific migration rules for the v3.0→v3.1 config refactor.

**Architecture:** Registry pattern with `@register_migration(from_version, to_version)` decorators. State persisted to `data/migrations.json`. Runner applies pending rules, fail-soft per rule. Integration point: `__init__` of plugin (BEFORE `_apply_config_overrides()` so overrides see new schema).

**Tech Stack:** Python 3.13, JSON file I/O, pytest, existing emotion_spirit module structure.

**Spec:** `docs/superpowers/specs/2026-06-24-config-migration-framework-design.md`

---

## File Structure

```
emotion_spirit/migrations/             # 新建: 迁移框架
├── __init__.py                        # 暴露 public API
├── registry.py                        # @register_migration + get_migrations
├── state.py                           # MigrationState (data/migrations.json)
├── runner.py                          # run_migrations() 主逻辑
└── rules/
    ├── __init__.py                    # 触发规则 import
    └── v3_0_to_v3_1.py                # 3 条迁移规则

tests/migrations/                      # 新建: 测试
├── __init__.py
├── test_registry.py
├── test_state.py
├── test_runner.py
├── test_rules_v3_0_to_v3_1.py
└── test_integration.py

main.py                                # 修改: 加 _setup_web_apis + 集成点
```

---

## Task 1: Create Migration Registry (`registry.py`)

**Files:**
- Create: `emotion_spirit/migrations/__init__.py`
- Create: `emotion_spirit/migrations/registry.py`
- Create: `tests/migrations/__init__.py`
- Create: `tests/migrations/test_registry.py`

- [ ] **Step 1: Create empty package directories**

```bash
mkdir -p "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit/emotion_spirit/migrations/rules"
mkdir -p "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit/tests/migrations"
touch "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit/emotion_spirit/migrations/__init__.py"
touch "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit/emotion_spirit/migrations/rules/__init__.py"
touch "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit/tests/migrations/__init__.py"
```

- [ ] **Step 2: Write the failing test for registry**

Create `tests/migrations/test_registry.py`:

```python
"""Tests for migration registry."""
from emotion_spirit.migrations.registry import (
    register_migration,
    get_migrations,
    get_latest_version,
)


def test_register_single_migration():
    """Register a single migration, retrieve via get_migrations."""
    @register_migration(from_version=1, to_version=2)
    def my_migration(config):
        return config
    
    migrations = get_migrations()
    # Filter to only this test's migration (other tests may have registered too)
    matching = [m for m in migrations if m[2] == "my_migration"]
    assert len(matching) == 1
    assert matching[0][0] == 1
    assert matching[0][1] == 2


def test_get_latest_version_returns_max_to_version():
    """get_latest_version returns the max to_version among registered rules."""
    @register_migration(from_version=10, to_version=11)
    def another_migration(config):
        return config
    
    assert get_latest_version() >= 11


def test_to_version_must_equal_from_plus_one():
    """Decorating with non-sequential versions raises ValueError."""
    import pytest
    with pytest.raises(ValueError, match="to_version must equal from_version \\+ 1"):
        register_migration(from_version=5, to_version=10)(lambda c: c)


def test_get_migrations_sorted_by_from_version():
    """get_migrations returns rules sorted by from_version ascending."""
    @register_migration(from_version=20, to_version=21)
    def late_migration(config):
        return config
    @register_migration(from_version=15, to_version=16)
    def mid_migration(config):
        return config
    
    all_migrations = get_migrations()
    from_versions = [m[0] for m in all_migrations]
    assert from_versions == sorted(from_versions)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit" && D:/python/python.exe -m pytest tests/migrations/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'emotion_spirit.migrations.registry'`

- [ ] **Step 4: Implement registry.py**

Create `emotion_spirit/migrations/registry.py`:

```python
"""Migration registry — @register_migration decorator + get_migrations."""
from typing import Callable

_REGISTRY: list[tuple[int, int, str, Callable[[dict], dict]]] = []


def register_migration(from_version: int, to_version: int):
    """Decorator to register a config migration rule.

    Args:
        from_version: 源 schema 版本号
        to_version: 目标 schema 版本号 (必须 = from_version + 1)

    Returns:
        Decorator that wraps the function and appends it to the registry.

    Raises:
        ValueError: If to_version != from_version + 1
    """
    if to_version != from_version + 1:
        raise ValueError(
            f"to_version must equal from_version + 1, got {from_version} -> {to_version}"
        )

    def decorator(fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
        _REGISTRY.append((from_version, to_version, fn.__name__, fn))
        return fn
    return decorator


def get_migrations() -> list[tuple[int, int, str, Callable]]:
    """Return all registered migrations sorted by from_version ascending."""
    return sorted(_REGISTRY, key=lambda x: x[0])


def get_latest_version() -> int:
    """Return the highest to_version among registered rules (= current schema version).

    Returns 0 if no rules are registered.
    """
    if not _REGISTRY:
        return 0
    return max(m[1] for m in _REGISTRY)


def reset_registry() -> None:
    """Clear the registry. Only for tests."""
    _REGISTRY.clear()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit" && D:/python/python.exe -m pytest tests/migrations/test_registry.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit"
git add emotion_spirit/migrations/__init__.py emotion_spirit/migrations/registry.py tests/migrations/__init__.py tests/migrations/test_registry.py
git commit -m "feat(migrations): add registry with @register_migration decorator"
```

---

## Task 2: Create Migration State (`state.py`)

**Files:**
- Create: `emotion_spirit/migrations/state.py`
- Create: `tests/migrations/test_state.py`

- [ ] **Step 1: Write the failing test**

Create `tests/migrations/test_state.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit" && D:/python/python.exe -m pytest tests/migrations/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'emotion_spirit.migrations.state'`

- [ ] **Step 3: Implement state.py**

Create `emotion_spirit/migrations/state.py`:

```python
"""Migration state — persists applied/error records to data/migrations.json."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MigrationState:
    """Persistent state for applied migrations and errors.

    Stored as JSON at {data_dir}/migrations.json.
    """

    def __init__(self, data_dir: Path | str):
        self._path = Path(data_dir) / "migrations.json"
        self._data: dict[str, Any] = {
            "current_version": 0,
            "applied": [],
            "errors": [],
        }

    def load_or_init(self) -> "MigrationState":
        """Load state from disk. If file missing, return fresh state with current_version=0.

        Returns self for chaining.
        """
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self._data = {
                    "current_version": loaded.get("current_version", 0),
                    "applied": loaded.get("applied", []),
                    "errors": loaded.get("errors", []),
                }
            except (json.JSONDecodeError, OSError):
                # Corrupted file → start fresh, keep corrupted as backup
                pass
        return self

    def record_applied(self, from_v: int, to_v: int, rule: str) -> None:
        """Append a successful migration to applied list."""
        self._data["applied"].append({
            "from": from_v,
            "to": to_v,
            "rule": rule,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def record_error(self, rule: str, error: str) -> None:
        """Append a failed migration to errors list."""
        self._data["errors"].append({
            "rule": rule,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def save(self) -> None:
        """Atomic write to disk (tmp + rename)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    @property
    def current_version(self) -> int:
        return self._data["current_version"]

    @current_version.setter
    def current_version(self, v: int) -> None:
        self._data["current_version"] = v

    @property
    def applied(self) -> list[dict]:
        return self._data["applied"]

    @property
    def errors(self) -> list[dict]:
        return self._data["errors"]

    def to_dict(self) -> dict:
        """Return a copy of the underlying data."""
        return {
            "current_version": self._data["current_version"],
            "applied": list(self._data["applied"]),
            "errors": list(self._data["errors"]),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit" && D:/python/python.exe -m pytest tests/migrations/test_state.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit"
git add emotion_spirit/migrations/state.py tests/migrations/test_state.py
git commit -m "feat(migrations): add MigrationState with atomic save"
```

---

## Task 3: Create Migration Runner (`runner.py`)

**Files:**
- Create: `emotion_spirit/migrations/runner.py`
- Create: `tests/migrations/test_runner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/migrations/test_runner.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit" && D:/python/python.exe -m pytest tests/migrations/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'emotion_spirit.migrations.runner'`

- [ ] **Step 3: Implement runner.py**

Create `emotion_spirit/migrations/runner.py`:

```python
"""Migration runner — applies pending rules from registry to config."""
import copy
import logging
from typing import Any

from .registry import get_migrations, get_latest_version
from .state import MigrationState

logger = logging.getLogger(__name__)


def run_migrations(
    config: dict,
    state: MigrationState,
    force: bool = False,
) -> tuple[dict, MigrationState]:
    """Apply pending migration rules to config.

    Args:
        config: Current config dict (NOT mutated; deep copy is made).
        state: MigrationState instance (NOT saved; caller must save).
        force: True to re-run all rules regardless of state.current_version.

    Returns:
        (new_config, updated_state) tuple.

    Behavior:
        - Each rule's `from_version` must be >= state.current_version to run
          (unless force=True).
        - Rules run in order of from_version ascending.
        - Failed rule: error logged, state.errors updated, runner continues.
        - On any rule application (success or fail), state.current_version
          advances to that rule's to_version.
        - After all rules, state.current_version = get_latest_version().
        - state.save() is NOT called; caller controls persistence order.
    """
    new_config = copy.deepcopy(config)
    target_version = get_latest_version()

    if not force and state.current_version >= target_version:
        return new_config, state

    for from_v, to_v, rule_name, fn in get_migrations():
        if not force and from_v < state.current_version:
            continue  # already applied
        try:
            new_config = fn(new_config)
            state.record_applied(from_v, to_v, rule_name)
            logger.info("Migration applied: %s (%d -> %d)", rule_name, from_v, to_v)
        except Exception as e:
            state.record_error(rule_name, str(e))
            logger.warning("Migration %s failed: %s", rule_name, e)

    state.current_version = target_version
    return new_config, state
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit" && D:/python/python.exe -m pytest tests/migrations/test_runner.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit"
git add emotion_spirit/migrations/runner.py tests/migrations/test_runner.py
git commit -m "feat(migrations): add runner with fail-soft per-rule behavior"
```

---

## Task 4: Create v3.0 → v3.1 Migration Rules

**Files:**
- Create: `emotion_spirit/migrations/rules/v3_0_to_v3_1.py`
- Create: `tests/migrations/test_rules_v3_0_to_v3_1.py`

- [ ] **Step 1: Write the failing test**

Create `tests/migrations/test_rules_v3_0_to_v3_1.py`:

```python
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
    """Import rules module to register them."""
    from emotion_spirit.migrations.rules import v3_0_to_v3_1  # noqa: F401


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

    # State recorded all 3 applications
    assert new_state.current_version == 3
    assert len(new_state.applied) == 3


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit" && D:/python/python.exe -m pytest tests/migrations/test_rules_v3_0_to_v3_1.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'emotion_spirit.migrations.rules.v3_0_to_v3_1'`

- [ ] **Step 3: Implement rules/v3_0_to_v3_1.py**

Create `emotion_spirit/migrations/rules/v3_0_to_v3_1.py`:

```python
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

    # 处理 enable_life_simulator 总开关 (false → 两个 mode 都关)
    if "enable_life_simulator" in toggles:
        if toggles["enable_life_simulator"] is False:
            config.setdefault("life_simulator", {})["enable_life_fragment"] = False
            config.setdefault("proactive_chat", {})["enable_proactive_prompt"] = False
        del toggles["enable_life_simulator"]

    # 处理 life_simulator_mode
    mode = toggles.pop("life_simulator_mode", None)
    if mode is not None:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit" && D:/python/python.exe -m pytest tests/migrations/test_rules_v3_0_to_v3_1.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit"
git add emotion_spirit/migrations/rules/v3_0_to_v3_1.py tests/migrations/test_rules_v3_0_to_v3_1.py
git commit -m "feat(migrations): add v3.0→v3.1 rules (split_modes + rename)"
```

---

## Task 5: Wire Migration into main.py (`__init__` integration)

**Files:**
- Modify: `main.py` (add `_run_config_migration_and_reload` + `_setup_web_apis` + `_api_re_run_migration`)

- [ ] **Step 1: Add imports and method `_run_config_migration_and_reload`**

Find the `_apply_config_overrides` call in `__init__` (around line 90). BEFORE that call, add:

```python
        # 跑 config migration (必须在 _apply_config_overrides 之前, 否则旧 config 升级后
        # apply overrides 用的是旧 schema 字段, 整个 plugin 用错配置跑)
        self._config = self._run_config_migration_and_reload(self._config)
```

Add the new method (place it right after `_apply_config_overrides`):

```python
    def _run_config_migration_and_reload(self, config: dict) -> dict:
        """从 cmd_config.json 读 config, 跑 migration, 写回, 返回新 config.

        即使 AstrBot 已经把 config 传给我们, 我们仍然从文件读:
        1. AstrBot 传入的 config 可能不是最新 (缓存)
        2. 写盘需要文件路径
        """
        from emotion_spirit.migrations import run_migrations, MigrationState
        config_path = (
            Path(get_astrbot_data_path())
            / "config"
            / "astrbot_plugin_emotion_spirit_config.json"
        )
        data_dir = (
            Path(get_astrbot_data_path()) / "plugin_data" / "emotion_spirit"
        )

        if not config_path.exists():
            return config

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
            state = MigrationState(data_dir).load_or_init()
            new_config, new_state = run_migrations(file_config, state)

            # 写盘顺序: config 先, state 后. 这样如果 state.save 失败,
            # 下次启动会重跑 migration (幂等), 不会丢数据
            if new_config != file_config:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(new_config, f, ensure_ascii=False, indent=2)
                logger.info(
                    "Config migration applied, saved %s", config_path
                )
            new_state.save()

            # 合并: 用文件的新 config 覆盖 AstrBot 传入的
            return new_config
        except Exception as e:
            logger.warning(
                "Config migration failed: %s, using AstrBot-passed config", e
            )
            return config
```

Add these imports at the top of `main.py` (with other stdlib imports):

```python
import json
```

- [ ] **Step 2: Verify syntax**

Run: `D:/python/python.exe -c "import py_compile; py_compile.compile('D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit/main.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Add `_setup_web_apis` + `_api_re_run_migration`**

Find the `__init__` method's `# ═══ 5. Surface 处理器 ═══` section. BEFORE it, add (or near the existing `_setup_commands` method):

```python
    def _setup_web_apis(self) -> None:
        """注册 Web API 端点. 本次只加 migration 端点."""
        from quart import jsonify as quart_jsonify  # noqa: F401
        self.context.register_web_api(
            route="emotion_spirit/re_run_migration",
            view_handler=self._api_re_run_migration,
            methods=["POST"],
            desc="手动重跑 config migration",
        )

    async def _api_re_run_migration(self, **kwargs):
        """POST /emotion_spirit/re_run_migration — 强制重跑 migration."""
        from emotion_spirit.migrations import run_migrations, MigrationState
        from quart import jsonify as quart_jsonify
        try:
            config_path = (
                Path(get_astrbot_data_path())
                / "config"
                / "astrbot_plugin_emotion_spirit_config.json"
            )
            data_dir = (
                Path(get_astrbot_data_path()) / "plugin_data" / "emotion_spirit"
            )
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            state = MigrationState(data_dir).load_or_init()
            new_config, new_state = run_migrations(config, state, force=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, ensure_ascii=False, indent=2)
            new_state.save()
            return quart_jsonify({
                "status": "ok",
                "config": new_config,
                "state": new_state.to_dict(),
            })
        except Exception as e:
            logger.warning("Manual re-run migration failed: %s", e)
            return quart_jsonify({"status": "error", "msg": str(e)}), 500
```

Add `from emotion_spirit.migrations import run_migrations as _run_migrations, MigrationState as _MigrationState` to the top (or use local imports — local is fine, used only in `_api_re_run_migration`).

Find the `initialize` method and add `self._setup_web_apis()` call BEFORE the `asyncio.get_event_loop().call_later(...)` lines (around line 686):

```python
        # 注册 Web API 端点 (migration re-run)
        self._setup_web_apis()

        asyncio.get_event_loop().call_later(2.0, self._connect_engine_sync)
```

- [ ] **Step 4: Verify syntax again**

Run: `D:/python/python.exe -c "import py_compile; py_compile.compile('D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit/main.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Run all tests to ensure no regression**

Run: `cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit" && D:/python/python.exe -m pytest tests/ -q`
Expected: PASS (886 existing + ~20 new = ~906 tests)

- [ ] **Step 6: Commit**

```bash
cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit"
git add main.py
git commit -m "feat(main): wire migration into __init__ + add re_run_migration endpoint"
```

---

## Task 6: End-to-end Integration Test

**Files:**
- Create: `tests/migrations/test_integration.py`

- [ ] **Step 1: Write the test**

Create `tests/migrations/test_integration.py`:

```python
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
    assert migrated["proactive_chat"]["enable_proactive_prompt"] is False  # enable_life_simulator=False wins
    assert "enable_proactive_chat" not in migrated["proactive_chat"]

    # 6. Verify state was saved
    state_file = tmp_path / "migrations.json"
    assert state_file.exists()
    saved_state = json.loads(state_file.read_text("utf-8"))
    assert saved_state["current_version"] == 3
    assert len(saved_state["applied"]) == 3
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
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit" && D:/python/python.exe -m pytest tests/migrations/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd "D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit"
git add tests/migrations/test_integration.py
git commit -m "test(migrations): add end-to-end upgrade integration test"
```

---

## Task 7: Manual Production Verification

- [ ] **Step 1: Restart AstrBot with old config present**

Setup: backup current `data/config/astrbot_plugin_emotion_spirit_config.json`, restore old config (with `enable_life_simulator`, `life_simulator_mode`, `enable_proactive_chat`):

```bash
# Backup current
cp D:/astrbot/data/config/astrbot_plugin_emotion_spirit_config.json D:/tmp/config_backup.json

# Create old-style config
python -c "
import json
old = {
    'persona_mode': 'auto',
    'auto_source': '小芙',
    'feature_toggles': {
        'enable_shadow_detector': True,
        'enable_life_simulator': False,
        'life_simulator_mode': 'passive',
    },
    'proactive_chat': {
        'enable_proactive_chat': True,
    },
    'llm_tier': {
        'engine_provider_id': 'minimax/MiniMax-M3',
        'life_sim_provider_id': 'minimax/MiniMax-M3',
        'analyzer_provider_id': 'minimax/MiniMax-M3',
    }
}
with open('D:/astrbot/data/config/astrbot_plugin_emotion_spirit_config.json', 'w', encoding='utf-8') as f:
    json.dump(old, f, ensure_ascii=False, indent=2)
"
```

- [ ] **Step 2: Restart AstrBot and check log**

```bash
taskkill //F //IM python.exe; sleep 1
cd D:/astrbot && D:/python/python.exe -m astrbot.cli run > D:/astrbot/astrbot.log 2>&1 &
sleep 10
grep -i "migration" D:/astrbot/astrbot.log
```

Expected log:
```
[INFO] Migration applied: split_life_simulator_modes (1 -> 2)
[INFO] Migration applied: rename_enable_proactive_chat (2 -> 3)
[INFO] Config migration applied, saved ...
```

- [ ] **Step 3: Verify config file was migrated**

```bash
cat D:/astrbot/data/config/astrbot_plugin_emotion_spirit_config.json
```

Expected:
- `feature_toggles` no longer has `enable_life_simulator` or `life_simulator_mode`
- `life_simulator.enable_life_fragment` is `false` (from `enable_life_simulator=False`)
- `proactive_chat.enable_proactive_prompt` is `false` (from `enable_life_simulator=False`)

- [ ] **Step 4: Verify state file**

```bash
cat D:/astrbot/data/plugin_data/emotion_spirit/migrations.json
```

Expected: `{"current_version": 3, "applied": [...3 entries...], "errors": []}`

- [ ] **Step 5: Restart again, verify no-op**

```bash
taskkill //F //IM python.exe; sleep 1
cd D:/astrbot && D:/python/python.exe -m astrbot.cli run > D:/astrbot/astrbot.log 2>&1 &
sleep 10
grep -i "migration" D:/astrbot/astrbot.log
```

Expected: no "Migration applied" log lines (state.current_version already at 3).

- [ ] **Step 6: Test manual re-run endpoint (optional)**

```bash
curl -X POST http://localhost:6185/api/plug/emotion_spirit/re_run_migration
```

Expected: `{"status": "ok", "config": {...}, "state": {...}}`

- [ ] **Step 7: Restore backup config**

```bash
cp D:/tmp/config_backup.json D:/astrbot/data/config/astrbot_plugin_emotion_spirit_config.json
```

---

## Self-Review

1. **Spec coverage:**
   - ✅ Architecture (registry + state + runner pattern) — Tasks 1-3
   - ✅ State file format and API — Task 2
   - ✅ Runner with fail-soft behavior — Task 3
   - ✅ 3 specific migration rules — Task 4
   - ✅ WebUI API endpoint — Task 5
   - ✅ main.py integration BEFORE `_apply_config_overrides` — Task 5
   - ✅ Write order: config first, state second — Task 5
   - ✅ SpiritStore boundary documented — Task 5
   - ✅ Testing strategy — Tasks 1-6
   - ✅ Manual production verification — Task 7

2. **Placeholder scan:** No TBD/TODO. All code is concrete.

3. **Type consistency:**
   - `MigrationState.__init__(data_dir: Path | str)` used consistently
   - `run_migrations(config, state, force=False)` returns `tuple[dict, MigrationState]` consistent across all calls
   - `register_migration(from_version, to_version)` decorator signature consistent
   - `MigrationState.record_applied(from_v, to_v, rule)` consistent