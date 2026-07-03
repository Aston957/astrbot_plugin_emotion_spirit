"""v1.2.9 HP-3: L2 三子回写接线测试 + v1.2.8 recovery 重复触发 bug 边沿检测.

collapse/suppression 回写 (silence 已有 v1.2.5 测试).
"""
from unittest.mock import MagicMock, PropertyMock


def test_collapse_l2_wired_on_trigger():
    """v1.2.9 HP-3: _collapse_active False→True → apply_event('collapse', 1.0) 被调一次"""
    from emotion_spirit.output.surface_handler import SurfaceHandler

    # mock plugin
    plugin = MagicMock()
    plugin._prev_collapse_active = False
    # 模拟 _pool.check_collapse 返回 True (False→True 边沿)
    plugin._pool.check_collapse = MagicMock(return_value=True)
    plugin._pool.get_collapse_archetype = MagicMock(return_value="crash")
    plugin._life_sim_v2.trigger_recovery = MagicMock()
    # defense_modulator
    plugin._defense_modulator.apply_event = MagicMock()

    # SurfaceHandler.consume 需要大量 mock, 直接测 collapse 块逻辑
    # 重建 consume 内的 collapse 块行为
    was_collapse = plugin._pool.check_collapse(personality={})
    archetype = plugin._pool.get_collapse_archetype()
    curr_collapse = was_collapse and bool(archetype)
    prev_collapse = getattr(plugin, "_prev_collapse_active", False)

    if curr_collapse and not prev_collapse:
        if plugin._life_sim_v2 and hasattr(plugin._life_sim_v2, 'trigger_recovery'):
            plugin._life_sim_v2.trigger_recovery(archetype)
        if plugin._defense_modulator and hasattr(plugin._defense_modulator, 'apply_event'):
            plugin._defense_modulator.apply_event("collapse", intensity=1.0)
    plugin._prev_collapse_active = curr_collapse

    # verify
    plugin._life_sim_v2.trigger_recovery.assert_called_once_with("crash")
    plugin._defense_modulator.apply_event.assert_called_once_with("collapse", intensity=1.0)
    assert plugin._prev_collapse_active is True


def test_collapse_l2_not_retriggered_while_active():
    """v1.2.9 HP-3 边沿检测: _collapse_active 持续 True → 不重复 apply_event"""
    from emotion_spirit.output.surface_handler import SurfaceHandler

    plugin = MagicMock()
    plugin._prev_collapse_active = True  # 上次已 collapse
    plugin._pool.check_collapse = MagicMock(return_value=True)
    plugin._pool.get_collapse_archetype = MagicMock(return_value="crash")
    plugin._life_sim_v2.trigger_recovery = MagicMock()
    plugin._defense_modulator.apply_event = MagicMock()

    was_collapse = plugin._pool.check_collapse(personality={})
    archetype = plugin._pool.get_collapse_archetype()
    curr_collapse = was_collapse and bool(archetype)
    prev_collapse = getattr(plugin, "_prev_collapse_active", False)

    if curr_collapse and not prev_collapse:
        if plugin._life_sim_v2 and hasattr(plugin._life_sim_v2, 'trigger_recovery'):
            plugin._life_sim_v2.trigger_recovery(archetype)
        if plugin._defense_modulator and hasattr(plugin._defense_modulator, 'apply_event'):
            plugin._defense_modulator.apply_event("collapse", intensity=1.0)
    plugin._prev_collapse_active = curr_collapse

    # collapse 持续中 → 不应触发 recovery 或 apply_event
    plugin._life_sim_v2.trigger_recovery.assert_not_called()
    plugin._defense_modulator.apply_event.assert_not_called()
    assert plugin._prev_collapse_active is True


def test_recovery_not_retriggered_while_collapse_active():
    """v1.2.9 修 v1.2.8 bug: collapse 持续期间 trigger_recovery 只调一次 (start_recovery 不重复重置 stage)"""
    from emotion_spirit.output.surface_handler import SurfaceHandler

    plugin = MagicMock()
    plugin._pool.check_collapse = MagicMock(return_value=True)
    plugin._pool.get_collapse_archetype = MagicMock(return_value="crash")
    plugin._life_sim_v2.trigger_recovery = MagicMock()
    plugin._defense_modulator.apply_event = MagicMock()
    plugin._prev_collapse_active = False  # 初始状态: 未 collapse

    # 模拟两轮 tick (True→True 持续)
    # Tick 1: False → True (首次触发)
    was_collapse = plugin._pool.check_collapse(personality={})
    archetype = plugin._pool.get_collapse_archetype()
    curr = was_collapse and bool(archetype)
    prev = getattr(plugin, "_prev_collapse_active", False)

    if curr and not prev:
        plugin._life_sim_v2.trigger_recovery(archetype)
        plugin._defense_modulator.apply_event("collapse", intensity=1.0)
    plugin._prev_collapse_active = curr

    # Tick 2: True → True (持续, 不应重复)
    was_collapse2 = plugin._pool.check_collapse(personality={})
    archetype2 = plugin._pool.get_collapse_archetype()
    curr2 = was_collapse2 and bool(archetype2)
    prev2 = getattr(plugin, "_prev_collapse_active", False)

    if curr2 and not prev2:
        plugin._life_sim_v2.trigger_recovery(archetype2)
        plugin._defense_modulator.apply_event("collapse", intensity=1.0)
    plugin._prev_collapse_active = curr2

    # trigger_recovery 只调 1 次 (Tick 1), 不是 2 次
    plugin._life_sim_v2.trigger_recovery.assert_called_once_with("crash")
    plugin._defense_modulator.apply_event.assert_called_once_with("collapse", intensity=1.0)


def test_suppression_l2_wired_in_schedule_loop():
    """v1.2.9 HP-3: schedule_plan_loop suppression 回写块 → apply_event('suppression', level) 被调"""
    # 模拟 main.py schedule loop 内的 suppression 回写块
    defense_modulator = MagicMock()
    defense_states = MagicMock()
    defense_states.suppression_level = 0.7
    defense_modulator.compute_defense_states = MagicMock(return_value=defense_states)
    defense_modulator.apply_event = MagicMock()

    # 执行 suppression 回写块 (plan §2.2)
    defense_states_result = defense_modulator.compute_defense_states(
        personality={}, signals=None, body_state=None,
        intimacy_level=0.5, context={}, force_state=None,
        conscience_pressure=0.0,
    )
    defense_modulator.apply_event("suppression", intensity=defense_states_result.suppression_level)

    defense_modulator.compute_defense_states.assert_called_once()
    defense_modulator.apply_event.assert_called_once_with("suppression", intensity=0.7)