"""Patch A (v1.2.11): _ns_handler __signature__ 覆盖守护.

AstrBot 4.26.x CommandFilter.init_handler_md 用 inspect.signature 解析 handler,
把 *args/**kwargs 误识别成必填命名参数 → 18 命令全 404 (不带参数 "必要参数缺失",
带参数 TypeError: _empty() takes no arguments).

workaround (main.py `_ns_command`): 覆盖 `_ns_handler.__signature__` 为 (self, event).
本测试守护覆盖逻辑不被回归删除.

注意两层守护各司其职, 不冲突:
- `test_v122_regression.test_ns_handler_accepts_varargs` 守护"函数定义保持 *args/**kwargs"
  (运行时接 CommandFilter 传参, 不能删 — `_ns_handler` body 从 *args 取参数).
- 本测试守护"inspect.signature 看到的 signature 不含 *args/**kwargs" (框架不误解析).

`__signature__` 覆盖只改元数据 (inspect.signature 优先读 __signature__ 属性),
不改函数定义 — 所以两层能共存.

用户反馈: 2026-07-04-emotion-spirit-v1210-feedback.md §3.
"""
from __future__ import annotations

import inspect

from main import _ns_command


def test_ns_handler_signature_has_no_var_args_kwargs():
    """inspect.signature(handler) 不含 *args (VAR_POSITIONAL) / **kwargs (VAR_KEYWORD)."""
    handler = _ns_command("test_cmd", "some_attr", "test desc")
    kinds = {p.kind for p in inspect.signature(handler).parameters.values()}
    assert inspect.Parameter.VAR_POSITIONAL not in kinds, (
        "_ns_handler 的 __signature__ 含 *args (VAR_POSITIONAL) — "
        "AstrBot 4.26.x CommandFilter.init_handler_md 会误解析成必填参数, "
        "导致 18 个命令全 404. Patch A 的 __signature__ 覆盖被删了?"
    )
    assert inspect.Parameter.VAR_KEYWORD not in kinds, (
        "_ns_handler 的 __signature__ 含 **kwargs (VAR_KEYWORD) — 同上."
    )


def test_ns_handler_signature_is_self_event_only():
    """覆盖后 signature 恰好 (self, event) — 框架靠这俩传参, 不多不少."""
    handler = _ns_command("test_cmd", "some_attr", "test desc")
    params = list(inspect.signature(handler).parameters)
    assert params == ["self", "event"], (
        f"期望 __signature__ == (self, event), 实际 {params}"
    )


def test_ns_handler_definition_still_has_varargs():
    """函数定义层仍保持 *args/**kwargs (运行时接 CommandFilter 传参).

    这重申 test_v122_regression.test_ns_handler_accepts_varargs 的约束:
    Patch A 的 __signature__ 覆盖不能误删函数定义里的 *args/**kwargs.
    """
    from pathlib import Path
    main_py = Path(__file__).parent.parent / "main.py"
    source = main_py.read_text(encoding="utf-8")
    assert "async def _ns_handler(self, event: AstrMessageEvent, *args, **kwargs):" in source, (
        "_ns_handler 函数定义必须保持 *args, **kwargs (运行时接 CommandFilter 传参); "
        "Patch A 只覆盖 __signature__ 属性, 不能改函数定义."
    )
