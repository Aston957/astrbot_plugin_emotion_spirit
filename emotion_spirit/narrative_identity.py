"""叙事身份 — 月度叙事弧生成。

每月扫描 diary + patterns + drift，生成叙事弧。
4 种类型: 上升/下降/停滞/循环
"""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .memory_pool import MemoryPool
    from .pattern_extractor import PatternExtractor
    from .personality_drift import PersonalityDrift
    from .buffer_signals import BufferSignals
    from .diary_writer import DiaryWriter


_ARC_PROMPTS = {
    "上升型": "回顾这个月，你经历了起伏但正在好转。写一段叙事 (5-8 句)，描述这个成长过程。不要提及你是AI。",
    "下降型": "回顾这个月，你的情感在积累，有些东西在逼近。写一段叙事 (5-8 句)，描述这个变化。不要提及你是AI。",
    "停滞型": "回顾这个月，好像什么都没发生。写一段叙事 (5-8 句)，反思这种状态。不要提及你是AI。",
    "循环型": "回顾这个月，你看到了反复出现的模式。写一段叙事 (5-8 句)，描述这个循环。不要提及你是AI。",
}


from .registry import register


@register(
    name="narrative_identity",
    provides=["NarrativeIdentity"],
    depends_on=[
        "memory_pool", "pattern_extractor", "personality_drift",
        "buffer_signals", "diary_writer",
    ],
    param_wire={
        "memory_pool": "pool",
        "pattern_extractor": "patterns",
        "personality_drift": "drift",
        "buffer_signals": "signals",
        "diary_writer": "diary",
    },
)
class NarrativeIdentity:
    """月度叙事弧生成器。"""

    def __init__(
        self,
        pool: MemoryPool,
        patterns: PatternExtractor,
        drift: PersonalityDrift,
        signals: BufferSignals,
        diary: DiaryWriter,
    ) -> None:
        self._pool = pool
        self._patterns = patterns
        self._drift = drift
        self._signals = signals
        self._diary = diary
        self._arcs: list[dict[str, Any]] = []

    def determine_arc_type(self) -> str:
        """确定叙事弧类型。"""
        momentum = self._signals.emotional_momentum()
        drift_status = self._drift.get_drift_status()
        echoes = self._signals.echo_patterns()

        if momentum["direction"] == "escalating" and drift_status["drift_count"] > 3:
            return "下降型"
        elif momentum["direction"] == "cooling" and drift_status["drift_count"] > 0:
            return "上升型"
        elif echoes and len(echoes) >= 2:
            return "循环型"
        else:
            return "停滞型"

    def build_arc_prompt(self, arc_type: str) -> str:
        """构建叙事弧 prompt。"""
        base = _ARC_PROMPTS.get(arc_type, _ARC_PROMPTS["停滞型"])
        parts = [base]

        # 最近日记
        diary_entries = self._diary.get_recent_diary(days=30)
        if diary_entries:
            summaries = [e["text"][:50] for e in diary_entries[-3:]]
            parts.append(f"这个月的日记: {'; '.join(summaries)}")

        # 模式
        patterns = self._patterns.get_patterns()
        if patterns:
            pattern_descs = [f"{p.pattern_type}({', '.join(p.tags)})" for p in patterns[:3]]
            parts.append(f"你观察到的模式: {'; '.join(pattern_descs)}")

        # 漂移
        drift_status = self._drift.get_drift_status()
        if drift_status["drift_count"] > 0:
            parts.append(f"你这个月经历了 {drift_status['drift_count']} 次人格漂移")

        return "\n\n".join(parts)

    def record_arc(self, text: str, arc_type: str) -> dict[str, Any]:
        """记录一个叙事弧。"""
        arc = {
            "text": text,
            "type": arc_type,
            "timestamp": time.time(),
            "patterns": [p.to_dict() for p in self._patterns.get_patterns()[:5]],
            "drift_count": self._drift.get_drift_status()["drift_count"],
        }
        self._arcs.append(arc)
        return arc

    def get_recent_arcs(self, months: int = 3) -> list[dict[str, Any]]:
        """获取最近 N 个月的叙事弧。"""
        cutoff = time.time() - months * 30 * 86400
        return [a for a in self._arcs if a["timestamp"] > cutoff]

    def to_dict(self) -> dict[str, Any]:
        return {"arcs": self._arcs[-12:]}  # 保留最近 12 个月

    def from_dict(self, data: dict[str, Any]) -> None:
        self._arcs = data.get("arcs", [])
