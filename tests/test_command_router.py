"""Tests for command_router 3 ns (Phase B, P3-1 + P3-4 整合)。

CommandRouter 装配 3 个 namespace: setup / view / reflect。
12 命令分配: setup(4) + view(3) + reflect(5)。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_command_router_namespace_registration():
    """CommandRouter.namespace('setup').command() 注册子命令。"""
    from emotion_spirit.command_router import CommandRouter

    router = CommandRouter()
    ns = router.namespace("setup")

    @ns.command("init", help_text="初始化人格")
    async def cmd_init(event, *args):
        return "initialized"

    all_cmds = router.list_all()
    assert ("setup", "init", "初始化人格") in all_cmds


def test_command_router_three_namespaces_isolated():
    """3 ns 隔离, 子命令不冲突。"""
    from emotion_spirit.command_router import CommandRouter

    router = CommandRouter()

    @router.namespace("setup").command("init", help_text="setup init")
    async def setup_init(event, *args):
        return "setup_init"

    @router.namespace("view").command("status", help_text="view status")
    async def view_status(event, *args):
        return "view_status"

    @router.namespace("reflect").command("drift", help_text="reflect drift")
    async def reflect_drift(event, *args):
        return "reflect_drift"

    all_cmds = router.list_all()
    assert ("setup", "init", "setup init") in all_cmds
    assert ("view", "status", "view status") in all_cmds
    assert ("reflect", "drift", "reflect drift") in all_cmds
    # 互不干扰
    assert len(all_cmds) == 3


def test_command_router_12_commands_3_ns():
    """12 命令分配: setup(4) + view(3) + reflect(5) = 12。"""
    from emotion_spirit.command_router import CommandRouter

    router = CommandRouter()

    # setup: 4
    @router.namespace("setup").command("init", help_text="init")
    async def _1(event, *a): pass
    @router.namespace("setup").command("relabel", help_text="relabel")
    async def _2(event, *a): pass
    @router.namespace("setup").command("switch", help_text="switch")
    async def _3(event, *a): pass
    @router.namespace("setup").command("list", help_text="list")
    async def _4(event, *a): pass

    # view: 3
    @router.namespace("view").command("status", help_text="status")
    async def _5(event, *a): pass
    @router.namespace("view").command("detail", help_text="detail")
    async def _6(event, *a): pass
    @router.namespace("view").command("whoami", help_text="whoami")
    async def _7(event, *a): pass

    # reflect: 5
    @router.namespace("reflect").command("drift", help_text="drift")
    async def _8(event, *a): pass
    @router.namespace("reflect").command("sentinel", help_text="sentinel")
    async def _9(event, *a): pass
    @router.namespace("reflect").command("shadows", help_text="shadows")
    async def _10(event, *a): pass
    @router.namespace("reflect").command("diary", help_text="diary")
    async def _11(event, *a): pass
    @router.namespace("reflect").command("patterns", help_text="patterns")
    async def _12(event, *a): pass

    all_cmds = router.list_all()
    assert len(all_cmds) == 12

    by_ns: dict[str, list[str]] = {}
    for ns, sub, _ in all_cmds:
        by_ns.setdefault(ns, []).append(sub)

    assert len(by_ns["setup"]) == 4
    assert len(by_ns["view"]) == 3
    assert len(by_ns["reflect"]) == 5


def test_command_router_dispatch_routes_to_handler():
    """dispatch(ns, sub) 路由到正确 handler。"""
    from emotion_spirit.command_router import CommandRouter

    router = CommandRouter()
    called = []

    @router.namespace("view").command("status", help_text="s")
    async def cmd_status(event, *args):
        called.append(("status", args))
        return "status_result"

    # 通过 dispatch 调用
    import asyncio
    result = asyncio.run(
        router.dispatch("view", "status", "fake_event", "arg1", "arg2")
    )
    assert result == "status_result"
    assert called == [("status", ("arg1", "arg2"))]


def test_command_router_full_command_name():
    """full_command_name(ns, sub) 返回 'ns_sub' 用于 @filter.command。"""
    from emotion_spirit.command_router import CommandRouter

    router = CommandRouter()
    assert router.full_command_name("setup", "init") == "setup_init"
    assert router.full_command_name("view", "status") == "view_status"
    assert router.full_command_name("reflect", "drift") == "reflect_drift"
