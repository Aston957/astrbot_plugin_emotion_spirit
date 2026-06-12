"""bridge sub-package — SylannEngine 集成桥接层。

职责: 连接 SylannEngine (身体层) 和 emotion_spirit (人格层)。
所有 sylanne_core 导入通过 try/except 保护, 无硬依赖。
"""
__all__ = [
    "engine_manager",
    "personality_bridge",
    "hotpool_forwarder",
]
