"""阴影检测 — 基于荣格构想: 阴影 = 未被符号化的情感模式。

检测信号:
  1. 回声模式: 同标签在缓冲池反复出现但未确认
  2. 回避模式: 预期出现但未出现的标签
  3. 确认偏差: 特定类型标签被系统性丢弃
  4. Φ 持续低 + expression_drive 持续下降

行为影响:
  - 不注入 prompt — 只影响 Mode B 事件语气
  - 阴影不被告知, 只被感知
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .memory_pool import MemoryPool
    from .buffer_signals import BufferSignals
    from .pattern_extractor import PatternExtractor


from .registry import register



__all__ = [
    "ShadowDetector",
]

@register(
    name="shadow_detector",
    provides=["ShadowDetector"],
    depends_on=["memory_pool", "buffer_signals", "pattern_extractor"],
    param_wire={
        "memory_pool": "pool",
        "buffer_signals": "signals",
        "pattern_extractor": "patterns",
    },
)
class ShadowDetector:
    """阴影检测器。"""

    def __init__(
        self,
        pool: MemoryPool,
        signals: BufferSignals,
        patterns: PatternExtractor,
    ) -> None:
        self._pool = pool
        self._signals = signals
        self._patterns = patterns
        self._active_shadows: list[dict[str, Any]] = []

    def detect(self) -> list[dict[str, Any]]:
        """返回潜在阴影列表。"""
        shadows: list[dict[str, Any]] = []

        # 1. 回声模式: 同标签在缓冲池反复出现但未确认
        for echo in self._signals.echo_patterns():
            if echo["count"] >= 5 and echo.get("expired", 0) > echo.get("in_buffer", 0):
                shadows.append({
                    "tag": echo["tag"],
                    "evidence": "echo_pattern",
                    "confidence": min(1.0, echo["count"] / 10),
                    "suggestion": f"你一直在经历 {echo['tag']} 但无法消化",
                })

        # 2. 回避模式: 预期但未出现
        for pattern in self._patterns.get_patterns(pattern_type="回避"):
            if pattern.tags:
                shadows.append({
                    "tag": pattern.tags[0],
                    "evidence": "avoidance_pattern",
                    "confidence": 0.5,
                    "suggestion": f"你好像在回避 {pattern.tags[0]}",
                })

        # 3. 确认偏差: 某标签被系统性丢弃
        bias = self._signals.confirmation_bias()
        for tag, rate in bias.items():
            if rate < 0.2:  # 80%+ 被丢弃
                shadows.append({
                    "tag": tag,
                    "evidence": "confirmation_bias",
                    "confidence": 1 - rate,
                    "suggestion": f"系统在回避 {tag} 类型的记忆",
                })

        # 去重 (同一 tag 只保留最高置信度)
        seen_tags: dict[str, dict] = {}
        for shadow in shadows:
            tag = shadow["tag"]
            if tag not in seen_tags or shadow["confidence"] > seen_tags[tag]["confidence"]:
                seen_tags[tag] = shadow

        self._active_shadows = list(seen_tags.values())
        return self._active_shadows

    def get_active_shadows(self) -> list[dict[str, Any]]:
        """获取当前活跃的阴影。"""
        return self._active_shadows

    def to_dict(self) -> dict[str, Any]:
        return {"active_shadows": self._active_shadows}

    def from_dict(self, data: dict[str, Any]) -> None:
        self._active_shadows = data.get("active_shadows", [])
