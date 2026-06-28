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
    """Import rules module to register them (reload to re-register after reset).

    默认只 reload v3_0_to_v3_1 (单元测 test 期望 v3.0→v3.1 schema)。
    端到端 test_combined_old_config_full_migration / test_idempotent
    显式调用 _load_rules_v4() 加载 v3.1→v4 链路以覆盖 v4 schema 期望。
    """
    import importlib
    from emotion_spirit.migrations.rules import v3_0_to_v3_1
    importlib.reload(v3_0_to_v3_1)


def _load_rules_v4():
    """End-to-end tests: load both v3.0→v3.1 and v3.1→v4 rule chains."""
    _load_rules()
    import importlib
    from emotion_spirit.migrations.rules import v3_1_to_v4
    importlib.reload(v3_1_to_v4)


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
    """Old config with all 3 issues → fully migrated to new schema.

    v3.0 → v3.1 → v4 端到端:
    - feature_toggles 里的 enable_life_simulator / life_simulator_mode 被 split 到 life_simulator / proactive_chat
    - proactive_chat.enable_proactive_chat 被 rename 到 enable_proactive_prompt
    - v4 进一步把 life_simulator + proactive_chat 段合并到 life_sim_v2 (merge_life_sim_config)
    - split_llm_tier 兜底 diary.enable_diary_llm=False (idempotent)
    """
    _load_rules_v4()
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

    # Old keys gone (from feature_toggles 段 — v3.1 已 split 完, v4 不会再碰)
    assert "enable_life_simulator" not in new_config["feature_toggles"]
    assert "life_simulator_mode" not in new_config["feature_toggles"]

    # v4 schema: life_simulator + proactive_chat 段已合并到 life_sim_v2
    assert "life_simulator" not in new_config
    assert "proactive_chat" not in new_config
    # enable_proactive_prompt from old proactive_chat.enable_proactive_prompt=False
    assert new_config["life_sim_v2"]["enable_proactive_prompt"] is False
    # merge_life_sim_config 注入 5 个默认参数 (idempotent, 已存在则不覆盖)
    for k, v in [("plan_generate_hour", 2), ("events_per_day_min", 3),
                  ("events_per_day_max", 5), ("adaptation_threshold", 0.3),
                  ("sleep_start_hour", 23), ("sleep_end_hour", 7)]:
        assert new_config["life_sim_v2"][k] == v, f"{k} 期望 {v}, got {new_config['life_sim_v2'].get(k)}"

    # split_llm_tier (3→4) 兜底注入 diary 段 (idempotent 默认值)
    assert new_config["diary"]["enable_diary_llm"] is False

    # State recorded all 4 rule applications (3 v3→v3.1 + 1 v3.1→v4)
    assert new_state.current_version == 4
    assert len(new_state.applied) == 4


def test_idempotent_no_op_when_already_migrated(tmp_path):
    """Running migration on already-migrated config is a no-op.

    注意: state.current_version=3 时, runner 只跑 from_v >= 3 的 rule,
    即 split_llm_tier (3→4) + merge_life_sim_config (3→4)。
    期望 new_config_already 必须包含 split_llm_tier 兜底注入的 diary 段
    (enable_diary_llm=False) + merge_life_sim_config 合并后的 life_sim_v2
    段,才能表达"idempotent after v3→v4 完成"的状态。
    """
    _load_rules_v4()
    # state.current_version=3 时, runner 跑 split_llm_tier (3→4) + merge_life_sim_config (3→4)。
    # new_config_already 必须是 runner 跑完后的"v4 完成"状态:
    # - life_simulator + proactive_chat 已合并到 life_sim_v2
    # - merge_life_sim_config 注入 5 个默认参数到 life_sim_v2
    # - split_llm_tier 兜底注入 diary 段
    new_config_already = {
        "feature_toggles": {},
        "diary": {"enable_diary_llm": False},
        "life_sim_v2": {
            "enable_proactive_prompt": True,
            "plan_generate_hour": 2,
            "events_per_day_min": 3,
            "events_per_day_max": 5,
            "adaptation_threshold": 0.3,
            "sleep_start_hour": 23,
            "sleep_end_hour": 7,
        },
    }
    state = MigrationState(tmp_path).load_or_init()
    state.current_version = 3
    result, _ = run_migrations(new_config_already, state)

    # No changes
    assert result == new_config_already
