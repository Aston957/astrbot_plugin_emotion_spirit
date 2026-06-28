"""End-to-end integration test: simulate full upgrade flow."""
import json
from pathlib import Path

import pytest

from emotion_spirit.migrations.registry import reset_registry
from emotion_spirit.migrations.runner import run_migrations
from emotion_spirit.migrations.state import MigrationState


@pytest.fixture(autouse=True)
def _ensure_all_rules_registered():
    """autouse: 每个 test 前 reset registry + reload 两个 rule 文件, 保证
    4 rule (3 v3→v3.1 + 1 v3.1→v4) 一定在 registry. 防御性:
    同目录其他 test file (e.g. test_split_llm_tier.py, test_rules_v3_0_to_v3_1.py)
    会 reset 或 reload registry, 留半装状态, 端到端 test 需要自带保险.
    """
    import importlib
    from emotion_spirit.migrations.rules import v3_0_to_v3_1, v3_1_to_v4
    reset_registry()
    importlib.reload(v3_0_to_v3_1)
    importlib.reload(v3_1_to_v4)
    yield
    reset_registry()


def test_full_upgrade_v3_0_to_v3_1(tmp_path):
    """Simulate: user has old config, plugin starts, migration runs, new config persisted.

    v3.0 → v3.1 (3 rules) → v3.1 → v4 (1 rule: merge_life_sim_config) = 4 步
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

    # 2. Load rules (simulating main.py import). 必须 importlib.reload 而不是仅
    # import, 因为前面 _ensure_all_rules_registered (autouse) 已 import 过一次,
    # 模块已在 sys.modules 里, 第二次 import 不会触发 @register_migration 副作用.
    import importlib
    from emotion_spirit.migrations.rules import v3_0_to_v3_1, v3_1_to_v4
    reset_registry()
    importlib.reload(v3_0_to_v3_1)
    importlib.reload(v3_1_to_v4)

    # 3. Run migration (simulating main.py _run_config_migration_and_reload)
    state = MigrationState(tmp_path).load_or_init()
    file_config = json.loads(config_file.read_text("utf-8"))
    new_config, new_state = run_migrations(file_config, state)

    # 4. Write back (config first, state second)
    config_file.write_text(json.dumps(new_config, ensure_ascii=False, indent=2), encoding="utf-8")
    new_state.save()

    # 5. Verify config was migrated (v3→v3.1→v4)
    migrated = json.loads(config_file.read_text("utf-8"))
    assert "enable_life_simulator" not in migrated["feature_toggles"]
    assert "life_simulator_mode" not in migrated["feature_toggles"]
    # v4: life_simulator + proactive_chat merged into life_sim_v2
    assert "life_simulator" not in migrated
    assert "proactive_chat" not in migrated
    assert migrated["life_sim_v2"]["enable_proactive_prompt"] is True

    # 6. Verify state was saved
    state_file = tmp_path / "migrations.json"
    assert state_file.exists()
    saved_state = json.loads(state_file.read_text("utf-8"))
    assert saved_state["current_version"] == 4
    assert len(saved_state["applied"]) == 4  # 3 v3→v3.1 + 1 v3.1→v4 (merge_life_sim_config)

    # 7. Second startup with migrated config: should be no-op
    import importlib
    from emotion_spirit.migrations.rules import v3_0_to_v3_1, v3_1_to_v4
    reset_registry()
    importlib.reload(v3_0_to_v3_1)
    importlib.reload(v3_1_to_v4)
    state2 = MigrationState(tmp_path).load_or_init()
    config_v2 = json.loads(config_file.read_text("utf-8"))
    new_config_v2, _ = run_migrations(config_v2, state2)

    # No changes on second run
    assert new_config_v2 == config_v2
