"""emotion_spirit 命令路由器 (Phase B, P3-1 + P3-4)。

3 个 ns: /setup (配置) + /view (查询) + /reflect (内省)。
12 命令从 main.py 搬到这, main.py 瘦身。
- setup(4): init / relabel / switch / list
- view(3): status / detail / whoami
- reflect(5): drift / sentinel / shadows / diary / patterns
"""
from __future__ import annotations
from typing import Callable, Any
import asyncio

from ..core.registry import register

try:
    from astrbot.api.event import filter as _astrbot_filter
    _ASTRBOT_AVAILABLE = True
except ImportError:  # 测试环境无 astrbot 时降级
    _ASTRBOT_AVAILABLE = False


    class _FilterStub:
        """降级 stub: 测试环境用, 不真正注册到 astrbot。"""
        def command(self, name: str):
            def decorator(func):
                func.__astrbot_command_name__ = name
                return func
            return decorator

    _astrbot_filter = _FilterStub()


__all__ = [
    "NamespaceRouter",
    "CommandRouter",
]

class NamespaceRouter:
    """单个 ns 的子命令路由器。"""

    def __init__(self, name: str) -> None:
        self._name = name
        self._commands: dict[str, tuple[Callable, str]] = {}

    @property
    def name(self) -> str:
        return self._name

    def command(self, sub: str, *, help_text: str = "") -> Callable:
        """装饰器: 注册子命令到 ns (仅内部路由, 不重复注册到 AstrBot)。

        用法:
            @ns.command("init", help_text="初始化人格")
            async def cmd_init(event, *args, **kwargs):
                ...

        Note: AstrBot 命令注册由 main.py 的 _ns_command 工厂负责,
        此处仅做内部路由表维护, 避免双重注册。
        """
        def decorator(handler: Callable) -> Callable:
            self._commands[sub] = (handler, help_text)
            return handler
        return decorator

    def list_commands(self) -> list[tuple[str, str]]:
        """列出所有子命令: [(sub, help_text), ...]"""
        return [(sub, help_text) for sub, (_, help_text) in self._commands.items()]

    def get_handler(self, sub: str) -> Callable | None:
        """获取子命令 handler。"""
        if sub not in self._commands:
            return None
        return self._commands[sub][0]


@register(
    name="command_router",
    provides=["CommandRouter"],
    depends_on=[],
)
class CommandRouter:
    """3 ns 命令路由器。"""

    def __init__(self) -> None:
        self._namespaces: dict[str, NamespaceRouter] = {}

    def namespace(self, name: str) -> NamespaceRouter:
        """获取或创建 namespace。"""
        if name not in self._namespaces:
            self._namespaces[name] = NamespaceRouter(name)
        return self._namespaces[name]

    def list_all(self) -> list[tuple[str, str, str]]:
        """列出所有 (ns, sub, help_text) 三元组。"""
        result: list[tuple[str, str, str]] = []
        for ns_name, ns in self._namespaces.items():
            for sub, help_text in ns.list_commands():
                result.append((ns_name, sub, help_text))
        return result

    def full_command_name(self, ns: str, sub: str) -> str:
        """生成完整命令名 (用于 @filter.command)。"""
        return f"{ns}_{sub}"

    async def dispatch(
        self, ns: str, sub: str, event: Any, *args: Any, **kwargs: Any
    ) -> Any:
        """路由到指定 ns + sub 的 handler。"""
        if ns not in self._namespaces:
            raise KeyError(f"Unknown namespace: {ns}")
        handler = self._namespaces[ns].get_handler(sub)
        if handler is None:
            raise KeyError(f"Unknown command: {ns}.{sub}")
        # handler 可能是 async 或 sync
        result = handler(event, *args, **kwargs)
        if asyncio.iscoroutine(result):
            result = await result
        return result
