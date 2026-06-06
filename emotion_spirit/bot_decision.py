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

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .social_graph import SocialGraph
    from .topic_privacy import TopicPrivacy


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
