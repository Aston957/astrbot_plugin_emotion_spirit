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
