"""EngineManager — SylannEngine 生命周期管理桥接。

封装 SylannEngine 的初始化、消息处理、信号注入和状态读取。
sylanne 已内嵌到 emotion_spirit.sylanne，无引擎时降级为纯 emotion_spirit 模式。

设计哲学:
  - SylannEngine 是可选的计算加速器, 不是必须依赖
  - process() 返回原始 Surface dict, 不返回 SemanticSignals (那是 SurfaceConsumer 的职责)
  - inject() 双写: 既写引擎 HotPool, 又通过 HotPoolForwarder 写 MemoryPool
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .hotpool_forwarder import HotPoolForwarder

logger = logging.getLogger(__name__)

__all__ = ["EngineManager"]


class EngineManager:
    """SylannEngine 生命周期管理器。

    所有 sylanne 访问通过 try/except 保护。
    引擎不可用时所有方法优雅降级 (返回 None / 静默跳过)。
    """

    def __init__(self) -> None:
        self._engine: Any = None
        self._forwarder: HotPoolForwarder | None = None
        self._started: bool = False

    def set_forwarder(self, forwarder: HotPoolForwarder) -> None:
        """注入 HotPoolForwarder, 用于 inject() 双写。"""
        self._forwarder = forwarder

    @property
    def available(self) -> bool:
        """引擎是否可用。"""
        return self._engine is not None

    def start(self) -> bool:
        """启动引擎。返回是否成功。

        try/except 保护: 没装 sylanne 就跳过。
        """
        if self._started:
            return True
        try:
            from ..sylanne import get_engine
            self._engine = get_engine()
            self._started = True
            logger.info("EngineManager: SylannEngine 连接成功")
            return True
        except (ImportError, RuntimeError) as e:
            logger.info("EngineManager: SylannEngine 不可用 (%s), 降级模式", e)
            self._engine = None
            self._started = False
            return False

    def stop(self) -> None:
        """优雅关闭引擎。"""
        if self._engine is not None:
            try:
                # 清理监听器等资源
                if hasattr(self._engine, "off"):
                    self._engine.off(None)
            except Exception:
                pass
        self._engine = None
        self._started = False
        logger.info("EngineManager: 已关闭")

    def process(self, session_id: str, text: str) -> dict[str, Any] | None:
        """处理消息, 返回 Surface dict。无引擎返回 None。

        Args:
            session_id: 会话标识 (通常是 unified_msg_origin)。
            text: 用户消息文本。

        Returns:
            SylannEngine 的 Surface dict, 或 None (无引擎时)。
        """
        if self._engine is None:
            return None
        try:
            import asyncio
            # process() 可能是 async 也可能是 sync
            result = self._engine.process(session_id, text)
            if hasattr(result, "__await__"):
                # async — 在 sync 上下文中无法直接 await
                # 调用方需要自行处理 async 场景
                logger.warning("EngineManager: process() 返回协程, 需要 async 调用")
                return None
            return result
        except Exception as e:
            logger.warning("EngineManager: process() 失败: %s", e, exc_info=True)
            return None

    async def process_async(self, session_id: str, text: str) -> dict[str, Any] | None:
        """异步版本的 process()。"""
        if self._engine is None:
            return None
        try:
            result = self._engine.process(session_id, text)
            if hasattr(result, "__await__"):
                return await result
            return result
        except Exception as e:
            logger.warning("EngineManager: process_async() 失败: %s", e, exc_info=True)
            return None

    def inject(
        self,
        session_id: str,
        source: str,
        signal_type: str,
        intensity: float,
        source_text: str = "",
    ) -> None:
        """注入信号到引擎, 同时转发到 UnifiedMemory (通过 HotPoolForwarder)。

        Args:
            session_id: 会话标识。
            source: 信号来源 (如 "emotion_spirit", "user_message")。
            signal_type: 信号类型 (contradiction/reinforcement/revelation/betrayal/validation)。
            intensity: 信号强度 [0, 1]。
            source_text: 源文本, 用于 HotPoolForwarder 的关键词匹配。
        """
        # 1. 写引擎 HotPool
        if self._engine is not None:
            try:
                self._engine.inject(
                    session_id=session_id,
                    source=source,
                    influence_type=signal_type,
                    intensity=intensity,
                )
            except Exception as e:
                logger.warning("EngineManager: inject() 到引擎失败: %s", e)

        # 2. 转发到 UnifiedMemory
        if self._forwarder is not None:
            try:
                self._forwarder.forward(
                    session_id=session_id,
                    signal_type=signal_type,
                    intensity=intensity,
                    source_text=source_text,
                )
            except Exception as e:
                logger.warning("EngineManager: forward() 到 UnifiedMemory 失败: %s", e)

    def state(self, session_id: str) -> dict[str, Any] | None:
        """读取当前引擎状态。无引擎返回 None。"""
        if self._engine is None:
            return None
        try:
            return self._engine.state(session_id)
        except Exception as e:
            logger.warning("EngineManager: state() 失败: %s", e)
            return None

    def on_surface(self, listener: Any) -> None:
        """注册 Surface 监听器。无引擎时静默跳过。"""
        if self._engine is not None:
            try:
                self._engine.on(listener)
            except Exception as e:
                logger.warning("EngineManager: on() 注册监听器失败: %s", e)

    def off_surface(self, listener: Any) -> None:
        """注销 Surface 监听器。无引擎时静默跳过。"""
        if self._engine is not None:
            try:
                self._engine.off(listener)
            except Exception as e:
                logger.warning("EngineManager: off() 注销监听器失败: %s", e)
