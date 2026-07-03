"""v1.2.9 HP-1: /reflect_force_current offset 显示"""
import asyncio
from unittest.mock import MagicMock


def _collect_async_gen(agen):
    """Helper: run async generator and collect all yielded values."""
    async def _collect():
        results = []
        async for r in agen:
            results.append(r)
        return results
    return asyncio.run(_collect())


def test_reflect_force_current_shows_offset():
    """/reflect_force_current 输出含 'Cumulative offset' + 三力 offset 值"""
    from emotion_spirit.output.commands import CommandImpl

    # mock plugin
    plugin = MagicMock()
    plugin._force_dynamics = MagicMock()
    plugin._force_dynamics.get_cumulative_offset = MagicMock(
        return_value={"natural": 0.1, "social": 0.2, "individual": 0.3}
    )
    plugin.get_current_force_state = MagicMock(
        return_value=MagicMock(natural=0.6, social=0.4, individual=0.5)
    )
    plugin._segmented_coordinator = MagicMock()
    plugin._segmented_coordinator.get_history = MagicMock(return_value={})
    plugin._labels = {}

    # 初始化 CommandImpl
    cmd = CommandImpl(plugin)
    event = MagicMock()
    event.plain_result = MagicMock()

    # 收集所有 yield
    _collect_async_gen(cmd.reflect_force_current(event))

    # 找到 plain_result 被调用的参数
    assert event.plain_result.call_count >= 1
    output = event.plain_result.call_args[0][0]

    # 验证输出含 offset 信息
    assert "Cumulative offset" in output, f"Output missing 'Cumulative offset': {output}"
    assert "natural: 0.100" in output, f"Output missing natural offset: {output}"
    assert "social: 0.200" in output, f"Output missing social offset: {output}"
    assert "individual: 0.300" in output, f"Output missing individual offset: {output}"
    # 验证 force_state 仍在
    assert "ForceState" in output
    assert "natural: 0.60" in output


def test_reflect_force_current_offset_label():
    """/reflect_force_current 的 offset 行含 'v1.3 L3 激活' 标注"""
    from emotion_spirit.output.commands import CommandImpl

    plugin = MagicMock()
    plugin._force_dynamics = MagicMock()
    plugin._force_dynamics.get_cumulative_offset = MagicMock(
        return_value={"natural": 0.0, "social": 0.0, "individual": 0.0}
    )
    plugin.get_current_force_state = MagicMock(
        return_value=MagicMock(natural=0.5, social=0.5, individual=0.5)
    )
    plugin._segmented_coordinator = MagicMock()
    plugin._segmented_coordinator.get_history = MagicMock(return_value={})
    plugin._labels = {}

    cmd = CommandImpl(plugin)
    event = MagicMock()
    event.plain_result = MagicMock()

    _collect_async_gen(cmd.reflect_force_current(event))

    output = event.plain_result.call_args[0][0]
    assert "Cumulative offset" in output, f"Output missing 'Cumulative offset': {output}"
    assert "v1.3 L3 激活" in output, f"Output missing activation label: {output}"