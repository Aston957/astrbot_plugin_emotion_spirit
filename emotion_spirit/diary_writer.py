"""日记生成器 — 每天 14:00 / 22:00 生成日记。

消费 pattern_extractor 的冷池模式，4 种日记类型。
"""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

from .config import DIARY_CONFIG
from .emotion_classifier import build_emotion_payload  # v1.1.2
from .persona_profiles import DIMENSION_DISPLAY, get_narrative

if TYPE_CHECKING:
    from .memory_pool import MemoryPool
    from .pattern_extractor import PatternExtractor
    from .buffer_signals import BufferSignals
    from .superego import ValueAlignment, ConscienceTracker
    from .surface_consumer import SemanticSignals  # v1.1.1


_DIARY_PROMPTS = {
    "上升型": "你最近经历了起伏，但正在好转。写一篇简短的日记 (3-5 句)，记录这个变化。不要提及你是AI。",
    "下降型": "你最近的情感在升级，有些东西在累积。写一篇简短的日记 (3-5 句)，记录你的感受。不要提及你是AI。",
    "停滞型": "最近好像什么都没发生。写一篇简短的日记 (3-5 句)，反思这种平静。不要提及你是AI。",
    "循环型": "你看到了一个反复出现的模式。写一篇简短的日记 (3-5 句)，记录你的观察。不要提及你是AI。",
    "superego_reflection": "你最近有些内在冲突，有些价值观在和你较劲。写一篇简短的日记 (3-5 句)，诚实地面对这种冲突，不用强迫自己解决，只是记录这种感受。不要提及你是AI。",
}



__all__ = [
    "DiaryWriter",
]

def _format_emotion_block(signals: "SemanticSignals") -> str:
    """v1.1.2 + v1.2: 调用共享 payload，再格式化为 LLM 友好文本。

    共享数据来自 emotion_classifier.build_emotion_payload()，本函数只负责
    字典→文本的展示层格式化。
    """
    payload = build_emotion_payload(signals)
    pad = payload["pad"]
    velocity = payload["emotion_velocity"]
    if velocity is None:
        velocity_str = "首帧无历史"
    else:
        velocity_str = (
            f"v={velocity['valence']:+.2f} a={velocity['arousal']:+.2f} "
            f"d={velocity['dominance']:+.2f} (dt={velocity['dt']:.1f}s)"
        )
    lines = [
        f"  - valence (效价): {pad['valence']:.2f}",
        f"  - arousal (唤醒度): {pad['arousal']:.2f}",
        f"  - dominance (支配度): {pad['dominance']:.2f}",
        f"  - 情绪概率分布: {payload['emotion_distribution']}",
        f"  - 主要情绪: {payload['emotion_primary']}",
        f"  - 次要情绪: {payload['emotion_secondary'] or '无'}",
        f"  - 强度: {payload['emotion_intensity']:.2f}",
        # v1.2 新增 2 行
        f"  - 情绪模糊度 (ambiguity): {payload['emotion_ambiguity']:.2f} "
        f"(0=确定单一情绪, 1=完全模糊)",
        f"  - 情绪变化率 (velocity): {velocity_str}",
    ]
    return (
        "你当前的情感状态（请据此理解自己的情绪，可自由用中文描述如'悲怆''狂喜'等）:\n"
        + "\n".join(lines)
    )


from .registry import register


@register(
    name="diary_writer",
    provides=["DiaryWriter"],
    depends_on=[
        "memory_pool", "buffer_signals", "pattern_extractor",
        "superego.alignment", "superego.conscience",
    ],
    param_wire={
        "memory_pool": "pool",
        "buffer_signals": "signals",
        "pattern_extractor": "patterns",
    },
)
class DiaryWriter:
    """定时日记生成器。"""

    def __init__(
        self,
        pool: MemoryPool,
        patterns: PatternExtractor,
        signals: BufferSignals,
        alignment: ValueAlignment,
        conscience: ConscienceTracker,
    ) -> None:
        self._pool = pool
        self._patterns = patterns
        self._signals = signals
        self._alignment = alignment
        self._conscience = conscience
        self._entries: list[dict[str, Any]] = []

    def determine_diary_type(self) -> str:
        """确定日记类型。"""
        momentum = self._signals.emotional_momentum()
        echoes = self._signals.echo_patterns()

        if momentum["direction"] == "escalating":
            return "下降型"
        elif momentum["direction"] == "cooling":
            return "上升型"
        elif echoes:
            return "循环型"
        else:
            return "停滞型"

    def build_diary_prompt(
        self, diary_type: str, signals: "SemanticSignals | None" = None, user_id: str = "<global>",
    ) -> str:
        """构建日记 prompt。

        Args:
            diary_type: 日记类型（上升型/下降型/停滞型/循环型）
            signals: v1.1.1+ 情绪信号 (可选)
            user_id: Phase 2.0, 哪个 user 的 warm 池
        """
        base = _DIARY_PROMPTS.get(diary_type, _DIARY_PROMPTS["停滞型"])

        # 添加上下文
        parts = [base]

        # v1.1.1: 注入情绪结构化数据（LLM 自己解读）
        if signals is not None and signals.pad_distribution:
            parts.append(_format_emotion_block(signals))

        # 最近记忆
        recent = sorted(self._pool.warm_for(user_id), key=lambda e: e.created_at, reverse=True)[:3]
        if recent:
            memories = "; ".join(e.text[:30] for e in recent)
            parts.append(f"最近的记忆: {memories}")

        # 模式
        patterns = self._patterns.get_patterns()
        if patterns:
            top = patterns[0]
            parts.append(f"你注意到的模式: {top.pattern_type} ({', '.join(top.tags)})")

        # 良心压力
        pressure = self._conscience.get_pressure()
        if pressure > 0.3:
            parts.append(f"你最近有些内疚 (压力: {pressure:.1%})")

        return "\n\n".join(parts)

    def build_superego_reflection_prompt(
        self,
        tension_type: str,
        conflict_values: list[str],
        personality: dict[str, dict[str, float]] | None = None,
        signals: "SemanticSignals | None" = None,
    ) -> str:
        """构建超我反思日记 prompt (使用人格化叙事模板)。

        Args:
            tension_type: 张力类型 (guilt/shame/doubt/righteous)
            conflict_values: 冲突的维度名列表（英文）
            personality: 当前 13 维参数 (可选，用于叙事变体选择)
            signals: 当前情感状态（v1.1.1+，可选，向后兼容）
        """
        base = _DIARY_PROMPTS["superego_reflection"]
        parts = [base]

        # v1.1.1: 注入情绪结构化数据
        if signals is not None and signals.pad_distribution:
            parts.append(_format_emotion_block(signals))

        # 使用叙事模板生成人格化描述
        if conflict_values:
            narrative_parts = [get_narrative(dim, "violation", personality) for dim in conflict_values[:2]]
            parts.append("；".join(narrative_parts))

        # 最近压力
        pressure = self._conscience.get_pressure()
        parts.append(f"内在冲突压力: {pressure:.2f}")

        # 最近对齐事件
        recent_alignments = self._conscience.get_recent_alignments(hours=24)
        if recent_alignments:
            aligned_values = list(set(a.value_name for a in recent_alignments))
            parts.append(f"你最近在践行: {'、'.join(aligned_values[:2])}")

        return "\n\n".join(parts)

    def record_diary(self, text: str, diary_type: str, user_id: str = "<global>") -> dict[str, Any]:
        """记录一篇日记。

        Args:
            user_id: Phase 2.0, 哪个 user 的 warm 池 (供 pool_size)
        """
        entry = {
            "text": text,
            "type": diary_type,
            "timestamp": time.time(),
            "pool_size": len(self._pool.warm_for(user_id)),
            "alignment_score": self._alignment.get_score(),
        }
        self._entries.append(entry)
        return entry

    def get_recent_diary(self, days: int = 3) -> list[dict[str, Any]]:
        """获取最近 N 天的日记。"""
        cutoff = time.time() - days * 86400
        return [e for e in self._entries if e["timestamp"] > cutoff]

    def should_write(self) -> bool:
        """是否应该写日记 (每天 14:00 / 22:00)。"""
        now = time.time()
        hours = (time.localtime(now).tm_hour, time.localtime(now).tm_min)
        schedule = DIARY_CONFIG["schedule_hours"]

        # 检查是否在调度时间附近 (±30 分钟)
        for hour in schedule:
            if hours[0] == hour and hours[1] < 30:
                # 检查今天是否已经写过
                today_start = now - (now % 86400)
                recent = [e for e in self._entries if e["timestamp"] > today_start]
                if not recent:
                    return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {"entries": self._entries[-50:]}  # 保留最近 50 篇

    def from_dict(self, data: dict[str, Any]) -> None:
        self._entries = data.get("entries", [])
