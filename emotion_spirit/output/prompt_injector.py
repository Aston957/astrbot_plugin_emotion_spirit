"""Prompt 组装器 — 将记忆、关系、超我、阴影组装为注入文本。

注入到 system_prompt，不会被持久化到对话历史。
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..memory.memory_pool import MemoryPool
    from ..memory.memory_sampler import MemorySampler
    from ..memory.intimacy import IntimacyTracker
    from ..regulation.superego import ValueAlignment, ConscienceTracker, IdealSelf
    from ..regulation.shadow_detector import ShadowDetector
    from .diary_writer import DiaryWriter
    from .buffer_signals import BufferSignals


from ..core.registry import register



__all__ = [
    "PromptInjector",
]

@register(
    name="prompt_injector",
    provides=["PromptInjector"],
    depends_on=[
        "memory_pool", "intimacy", "diary_writer", "buffer_signals",
        "shadow_detector",
        "superego.alignment", "superego.conscience", "superego.ideal",
    ],
    param_wire={
        "memory_pool": "pool",
        "diary_writer": "diary",
        "shadow_detector": "shadow",
    },
)
class PromptInjector:
    """Prompt 上下文组装器。"""

    def __init__(
        self,
        pool: MemoryPool,
        intimacy: IntimacyTracker,
        alignment: ValueAlignment,
        conscience: ConscienceTracker,
        ideal: IdealSelf,
        shadow: ShadowDetector,
        diary: DiaryWriter,
        buffer_signals: "BufferSignals | None" = None,
    ) -> None:
        self._pool = pool
        self._intimacy = intimacy
        self._alignment = alignment
        self._conscience = conscience
        self._ideal = ideal
        self._shadow = shadow
        self._diary = diary
        self._buffer_signals = buffer_signals  # v1.7.2: P2-1 保留 aggregate_* 真消费点
        # Phase D: MemorySampler now uses MemoryPool directly
        from ..memory.memory_sampler import MemorySampler
        self._sampler = MemorySampler(pool)
        # Phase 2.5: 亲密度段 (per-user 4 段)
        self._intimacy_segment: dict[str, str] = {}

    def set_intimacy_segment(self, user_id: str, segment: str) -> None:
        """Phase 2.5: 设置 user 的亲密度段 (stranger/acquaintance/friend/inner_circle)。

        由 caller (main.py) 在调用 build_context 之前设置。
        """
        self._intimacy_segment[user_id] = segment

    def get_intimacy_segment(self, user_id: str) -> str:
        """Phase 2.5: 获取 user 的亲密度段 (未设置返回 default 'stranger')。"""
        return self._intimacy_segment.get(user_id, "stranger")

    def build_context(
        self,
        user_id: str,
        persona: str,
        current_personality: dict[str, dict[str, float]] | None = None,
        safety_level: str = "normal",
        safety_note: str | None = None,
        repair_advice: str | None = None,
        gossip_tendency: float = 0.0,
    ) -> str:
        """构建注入到 system_prompt 的上下文。

        Args:
            safety_level: SuperegoGuard 输出的干预级别 ("normal"|"warning"|"critical")
            safety_note: 人格化安全提示文本 (critical 时由 SuperegoGuard 生成)
            repair_advice: 修复建议文本 (critical 时由 SuperegoGuard 生成)
            gossip_tendency: v1.7.2 新增 13 维之一, 用于渲染 [边界] 块 (bot 社交姿态)
        """
        from ..core.config import SAFETY_CONFIG

        parts: list[str] = []

        # [印象] 温池最近 3 条 (Phase 2.0: per-user)
        recent = sorted(self._pool.warm_for(user_id), key=lambda e: e.created_at, reverse=True)[:3]
        if recent:
            impressions = "; ".join(e.text[:30] for e in recent)
            parts.append(f"[印象] 最近你感觉: {impressions}")

        # [向量回忆] PAD 向量空间语义检索 (Phase D: 通过 MemoryPool)
        if self._sampler is not None:
            entries = self._pool.all_entries()
            if entries:
                mean_temp = self._pool.mean_temperature()
                # 从最近 warm entry 取向量作为查询
                warm_entries = self._pool.get_layer("warm")
                if warm_entries:
                    latest = max(warm_entries, key=lambda e: e.created_at)
                    mood_vec = latest.vector
                    results = self._sampler.search_similar(mood_vec, k=3)
                    if results:
                        recalls = "; ".join(
                            f"{r.entry.text[:30]}({r.score:.1f})" for r in results
                        )
                        parts.append(f"[向量回忆] 情感相近的记忆: {recalls}")

        # [日记] 最近日记摘要
        diary_entries = self._diary.get_recent_diary(days=3)
        if diary_entries:
            parts.append(f"[日记] 你上次写到: {diary_entries[-1]['text'][:50]}")

        # [关系] 亲密度阶段 (Phase 2.5: 加 segment 标签)
        lifecycle = self._intimacy.get_lifecycle(user_id)
        score = self._intimacy.get_intimacy(user_id, persona)
        segment = self.get_intimacy_segment(user_id)
        parts.append(
            f"[关系] 你和TA的关系: {lifecycle} (亲密度: {score:.2f}, 段: {segment})"
        )

        # ═══ 超我: 价值冲突 (阈值随安全级别动态调整) ═══
        conscience_threshold = SAFETY_CONFIG.get(
            f"conscience_threshold_{safety_level}",
            SAFETY_CONFIG["conscience_threshold_normal"],
        )
        breakdown = self._conscience.get_pressure_breakdown()
        if breakdown["pressure"] > conscience_threshold:
            dominant = breakdown.get("dominant_tension")
            type_notes = {
                "guilt": "你觉得最近有些事违背了你的价值观",
                "shame": "你最近对自己不太满意",
                "doubt": "你最近有些事觉得说不通",
                "righteous": "你最近在坚持一些事，虽然不容易",
                "value_conflict": "有些事和你的价值观冲突了",
                "guard_reflex": "你的直觉在阻止一些事",
                "guard_rejected": "你的直觉在阻止一些事",
            }
            note = type_notes.get(dominant, "你最近有些内在冲突")
            parts.append(f"[内在冲突] {note} (压力: {breakdown['pressure']:.2f})")

        # ═══ 价值对齐 (计数阈值随安全级别动态调整) ═══
        alignment_count_threshold = SAFETY_CONFIG.get(
            f"alignment_show_count_{safety_level}",
            SAFETY_CONFIG["alignment_show_count_normal"],
        )
        alignments = self._conscience.get_recent_alignments(hours=24)
        if len(alignments) >= alignment_count_threshold:
            value_names = list(set(a.value_name for a in alignments[-5:]))
            parts.append(f"[价值对齐] 你最近在践行: {'、'.join(value_names)}")

        # ═══ 理想自我 ═══
        if current_personality:
            gap = self._ideal.compute_gap(current_personality)
            if gap > 0.2:
                direction = self._ideal.get_direction(current_personality)
                top_drift = sorted(direction.items(), key=lambda x: abs(x[1]), reverse=True)[:2]
                drift_desc = ", ".join(
                    f"{k.split('.')[-1]}({'↑' if v > 0 else '↓'})" for k, v in top_drift
                )
                parts.append(f"[理想] 你想成为的样子，最近在: {drift_desc} 偏离")

        # ═══ 安全提示 (critical 时由 SuperegoGuard 提供) ═══
        if safety_note:
            parts.append(f"[安全提示] {safety_note}")

        # ═══ 修复建议 (critical 时由 SuperegoGuard 提供) ═══
        if repair_advice:
            parts.append(f"[修复] {repair_advice}")

        # [阴影] 阴影检测 (如果有)
        if self._shadow:
            shadows = self._shadow.detect()
        else:
            shadows = []
        if shadows:
            top = shadows[0]
            parts.append(f"[阴影] 你一直在回避关于 {top['tag']} 的事")

        # ═══ [边界] gossip_tendency 真消费点 (v1.7.2, P0-2b) ═══
        boundary_text = self._render_boundary(gossip_tendency)
        if boundary_text:
            parts.append(boundary_text)

        # ═══ [全局] BufferSignals.aggregate_temperature 真消费点 (v1.7.2, P2-1 保留) ═══
        if self._buffer_signals is not None:
            global_text = self._render_global_state()
            if global_text:
                parts.append(global_text)

        return "\n".join(parts) if parts else ""

    def _render_boundary(self, gossip_tendency: float) -> str:
        """v1.7.2: 把 gossip_tendency 翻译为 bot 社交姿态的 prompt 块 (5 档)。

        基于 Erdoğan 2014 (gossip 实证构念) + HEXACO 2007 (H 反向 + E 正向 + A 反向)。
        bot 对"主动提及其他人"的倾向直接影响多人对话的边界感。
        """
        if gossip_tendency < 0.2:
            return "[边界] bot 不会主动提其他人, 等用户先开口"
        elif gossip_tendency < 0.4:
            return "[边界] bot 偶尔会提, 但需要明确关系基础"
        elif gossip_tendency < 0.6:
            return "[边界] bot 视情况而定, 关系好会提"
        elif gossip_tendency < 0.8:
            return "[边界] bot 习惯提及其他人的事, 像朋友八卦"
        else:
            return "[边界] bot 主动分享听到的事, 活跃社交"

    def _render_global_state(self) -> str:
        """v1.7.2: 把 BufferSignals.aggregate_temperature 翻译为 [全局] 块 (3 档)。

        反 YAGNI 修正 (P2-1): aggregate_* 类方法保留, 通过 PromptInjector 注入
        给 LLM 全局 bot 整体情绪压力, 跨 user buffer 总堆积量做信号。
        """
        if self._buffer_signals is None:
            return ""
        temp = self._buffer_signals.aggregate_temperature(self._pool)
        if temp < 0.3:
            return "[全局] bot 整体情绪压力: 轻松 (aggregate=%.2f)" % temp
        elif temp < 0.6:
            return "[全局] bot 整体情绪压力: 中等 (aggregate=%.2f)" % temp
        else:
            return "[全局] bot 整体情绪压力: 紧张 (aggregate=%.2f)" % temp

    def to_dict(self) -> dict[str, Any]:
        return {}

    def from_dict(self, data: dict[str, Any]) -> None:
        pass