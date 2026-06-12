"""BotDecisionMaker — bot 自主决策接口 stub (Phase 2.0 Step 7, Phase 4 完整实现)。

设计依据 (支柱 2: Gossip as Social Grooming):
- Erdoğan 2014: 八卦倾向是独立人格维度
- 高 gossip_tendency 的人更可能传话, 低 gossip_tendency 的人保持可靠性
- Phase 2.0 stub: 默认保守 (不主动提), Phase 4 接通 gossip_tendency

决策场景 (Phase 2.0 范围):
1. can_mention_person(src_user, dst_user, person) — 能否提某人
2. can_mention_topic(src_user, dst_user, topic) — 能否提某话题 (委托 TopicPrivacy)
3. should_initiate_proactive() — 是否主动发起对话 (Phase 2.0 永远 False)

Phase 4 扩展:
- gossip_tendency (从 13 维人格参数推导)
- 关系强度 + 信任 + 话题敏感度 联合决策
- 时机选择 (冷却时间, 情境匹配)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory.social_graph import SocialGraph
    from ..memory.topic_privacy import TopicPrivacy
    from ..memory.memory_pool import MemoryPool
    from .surface_consumer import SurfaceConsumer


from ..core.registry import register



__all__ = [
    "BotDecisionMaker",
]

@register(
    name="bot_decision",
    provides=["BotDecisionMaker"],
    depends_on=["social_graph", "topic_privacy"],
    config_keys={"gossip_tendency"},
)
class BotDecisionMaker:
    """bot 自主决策 (Phase 2.0 stub)。

    默认配置: 保守 (gossip_tendency=0.0), 不主动提及他人/话题。
    Phase 4: 接通 gossip_tendency, 启用主动决策。
    """

    def __init__(
        self,
        social_graph: "SocialGraph | None" = None,
        topic_privacy: "TopicPrivacy | None" = None,
        gossip_tendency: float = 0.0,  # Phase 2.0: 保守, Phase 4 接通人格参数
    ) -> None:
        self._social_graph = social_graph
        self._topic_privacy = topic_privacy
        self._gossip_tendency = max(0.0, min(1.0, gossip_tendency))
        # 决策日志 (for 审计/调试)
        self._decisions: list[dict[str, Any]] = []

    # ═══ 决策接口 ═══

    def can_mention_person(
        self,
        src_user: str,
        dst_user: str,
        person: str,
    ) -> bool:
        """bot 能否在 src_user 视角下, 对 dst_user 提及 person?

        Phase 2.0 stub: 默认 False (保守)。
        Phase 4: 综合 gossip_tendency + 关系强度 + 信任。
        """
        # 永远不允许 bot 提及自己 (退化为不可)
        if person == dst_user:
            return False

        # Phase 2.0 决策: gossip_tendency < 0.5 → False
        # 真实公式 (Phase 4) 应综合: gossip_tendency × social_distance × trust
        decision = self._gossip_tendency >= 0.5
        self._log_decision("can_mention_person", src_user, dst_user, person, decision)
        return decision

    def can_mention_topic(
        self,
        src_user: str,
        dst_user: str,
        topic: str,
    ) -> bool:
        """bot 能否在 src_user 视角下, 对 dst_user 提及 topic?

        Phase 2.0 stub: 委托 TopicPrivacy.can_mention, 不加 bot 倾向。
        Phase 4: 可选地叠加 gossip_tendency 作为额外约束。
        """
        if self._topic_privacy is None:
            # 无 TopicPrivacy, 保守拒绝
            self._log_decision("can_mention_topic", src_user, dst_user, topic, False)
            return False
        decision = self._topic_privacy.can_mention(
            src_user, dst_user, topic, social_graph=self._social_graph,
        )
        self._log_decision("can_mention_topic", src_user, dst_user, topic, decision)
        return decision

    def should_initiate_proactive(self) -> bool:
        """bot 是否应主动发起对话?

        Phase 2.0 stub: 永远 False (等用户先说话)。
        Phase 4: 综合 bot 的人格外向性 + 最近的沉默时长 + 关系亲密度。
        """
        return False

    def get_gossip_tendency(self) -> float:
        """当前 gossip_tendency 值 (0-1)。"""
        return self._gossip_tendency

    def set_gossip_tendency(self, value: float) -> None:
        """Phase 4 接入点: 设置 gossip_tendency (从 13 维人格参数推导)。"""
        self._gossip_tendency = max(0.0, min(1.0, value))

    # ═══ 内部 ═══

    def _log_decision(
        self,
        decision_type: str,
        src_user: str,
        dst_user: str,
        subject: str,
        result: bool,
    ) -> None:
        """记录决策 (供 Phase 2.1 审计)。"""
        import time
        self._decisions.append({
            "type": decision_type,
            "src": src_user,
            "dst": dst_user,
            "subject": subject,
            "result": result,
            "gossip_tendency": self._gossip_tendency,
            "ts": time.time(),
        })
        # 限制日志大小
        if len(self._decisions) > 200:
            self._decisions = self._decisions[-200:]

    def get_recent_decisions(self, n: int = 20) -> list[dict[str, Any]]:
        """获取最近 N 条决策日志。"""
        return self._decisions[-n:]

    # ═══ proactive_chat 适配接口 ═══
    # emotion_spirit 不直接发消息, 只提供上下文。
    # proactive_chat 在生成主动消息时调用这些方法获取情绪上下文。

    def configure_proactive_deps(
        self,
        memory_pool: "MemoryPool | None" = None,
        surface_consumer: SurfaceConsumer | None = None,
    ) -> None:
        """注入 proactive 上下文所需的依赖。"""
        self._memory_pool = memory_pool
        self._surface_consumer = surface_consumer

    def get_proactive_context(self, session_id: str) -> str:
        """返回 emotion_spirit 的内部状态作为 proactive_chat 的上下文。

        proactive_chat 在生成主动消息时, 将此上下文注入到 system prompt,
        让 LLM 知道 bot 当前的情绪状态, 从而生成更自然的主动消息。

        Args:
            session_id: 会话标识。

        Returns:
            上下文字符串, 可直接注入 prompt。无数据时返回空字符串。
        """
        parts: list[str] = []

        # 1. 记忆温度状态
        memory = getattr(self, "_memory_pool", None)
        if memory is not None:
            try:
                mean_temp = memory.mean_temperature()
                hot_count = memory.count_hot(threshold=0.7)
                ghost_count = len(memory.get_layer("ghost"))
                cascade_active = memory.cascade_active()

                if mean_temp > 0.7:
                    parts.append("你现在内心很不平静，很多情绪在翻涌")
                elif mean_temp > 0.4:
                    parts.append("你现在有些心绪不宁")
                else:
                    parts.append("你现在相对平静")

                if cascade_active:
                    parts.append("一个念头牵出另一个念头，思绪在连锁反应")
                if ghost_count > 0:
                    parts.append(f"有 {ghost_count} 个很久以前的画面一直在脑海里挥不去")
            except Exception:
                pass

        # 2. 情绪状态
        consumer = getattr(self, "_surface_consumer", None)
        if consumer is not None:
            try:
                signals = consumer.consume_for_session(session_id)
                if signals is not None:
                    if signals.pad_primary and signals.pad_primary != "neutral":
                        parts.append(f"当前情绪: {signals.pad_primary}")
                    if signals.pad_intensity > 0.6:
                        parts.append("情绪强度较高")
            except Exception:
                pass

        if not parts:
            return ""
        return "[emotion_spirit 内在状态]\n" + "，".join(parts) + "。"

    def get_life_event_context(self, session_id: str) -> str:
        """返回最近的生活事件作为 proactive_chat 的上下文。

        Args:
            session_id: 会话标识。

        Returns:
            生活事件上下文字符串。无数据时返回空字符串。
        """
        memory = getattr(self, "_memory_pool", None)
        if memory is None:
            return ""

        try:
            # 从 buffer 层取最近的记忆作为"生活事件"
            buffer_entries = memory.get_layer("buffer")
            if not buffer_entries:
                return ""

            # 按创建时间倒序, 取最近 3 条
            recent = sorted(buffer_entries, key=lambda e: e.created_at, reverse=True)[:3]
            if not recent:
                return ""

            lines = ["[最近的记忆片段]"]
            for entry in recent:
                text = entry.text[:100] if len(entry.text) > 100 else entry.text
                lines.append(f"- {text}")
            return "\n".join(lines)
        except Exception:
            return ""

    def should_suppress_proactive(self, session_id: str) -> tuple[bool, str]:
        """检查 bot 是否应该保持沉默 (不主动发言)。

        基于 Sylanne 的 DeliberateSilence 逻辑:
          - 受伤 (tension 高 + valence 负) → 沉默
          - 在消化 (cascade 活跃) → 沉默
          - 崩溃中 → 沉默

        Args:
            session_id: 会话标识。

        Returns:
            (是否应沉默, 原因) 元组。
        """
        consumer = getattr(self, "_surface_consumer", None)
        if consumer is None:
            return False, ""

        try:
            signals = consumer.consume_for_session(session_id)
            if signals is None:
                return False, ""

            # 受伤
            if signals.pad_valence < -0.3 and signals.pad_arousal > 0.7:
                return True, "hurt"

            # 在消化 (cascade 活跃)
            if signals.cascade_active and signals.pad_valence > 0:
                return True, "digesting"

            # 崩溃中
            if signals.collapse_count > 0:
                return True, "collapsed"

            # 恢复中
            if signals.in_recovery:
                return True, "recovering"

            return False, ""
        except Exception:
            return False, ""
