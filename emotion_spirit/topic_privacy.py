"""TopicPrivacy — 话题隐私边界管理 (Phase 2.0 Step 6, CPM 理论)。

设计依据 (支柱 3: Communication Privacy Management):
- Petronio 1991, 2002: 隐私 = 边界管理, 边界协调, 边界侵犯
- 3 级隐私: private / circle / public
- 用户"明确禁止" (forbid_mention) 覆盖所有默认 (边界协调后的硬约束)

数据模型:
- _privacy: dict[user_id, dict[topic, PrivacyLevel]]
- _forbidden: dict[user_id, set[topic]]  # 用户明确禁止的硬约束
"""

from __future__ import annotations

import time
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .social_graph import SocialGraph


class PrivacyLevel(str, Enum):
    """话题隐私级别 (CPM 边界)。"""
    PRIVATE = "private"   # 只对自己, 永不提及
    CIRCLE = "circle"     # in_circle 成员可提及
    PUBLIC = "public"     # 可对任何人提及


# 默认隐私级别: 未知话题视为 private (保守)
_DEFAULT_PRIVACY = PrivacyLevel.PRIVATE


class TopicPrivacy:
    """话题隐私边界管理。"""

    def __init__(self) -> None:
        # _privacy: src_user → {topic → PrivacyLevel}
        self._privacy: dict[str, dict[str, PrivacyLevel]] = {}
        # _forbidden: src_user → {forbidden topics} (硬约束)
        self._forbidden: dict[str, set[str]] = {}
        # 边界协调日志 (for Phase 2.1 审计)
        self._coordination_log: list[dict[str, Any]] = []

    def set_privacy(
        self,
        user_id: str,
        topic: str,
        level: PrivacyLevel,
        by_explicit_declaration: bool = False,
    ) -> None:
        """设置 user 的 topic 隐私级别。

        Args:
            by_explicit_declaration: True 表示用户主动声明, False 表示 bot 推断
        """
        self._privacy.setdefault(user_id, {})[topic] = level
        self._coordination_log.append({
            "user_id": user_id,
            "topic": topic,
            "level": level.value,
            "by_user": by_explicit_declaration,
            "ts": time.time(),
        })

    def forbid_mention(self, user_id: str, topic: str) -> None:
        """用户"明确禁止"提及某话题 (硬约束, 覆盖任何级别)。"""
        self._forbidden.setdefault(user_id, set()).add(topic)
        self._coordination_log.append({
            "user_id": user_id,
            "topic": topic,
            "action": "forbid",
            "ts": time.time(),
        })

    def can_mention(
        self,
        src_user: str,
        dst_user: str,
        topic: str,
        social_graph: "SocialGraph | None" = None,
    ) -> bool:
        """检查 bot 能否在 src_user 视角下, 对 dst_user 提及 topic。

        决策规则 (按优先级):
        1. 用户"明确禁止" (forbid) → False (硬约束)
        2. private 级别 → False (只对自己)
        3. circle 级别 → 需 in_circle 检查 (无 social_graph 视为 False)
        4. public 级别 → True

        Args:
            src_user: 话题所属 user (whose pool 里有这个 topic)
            dst_user: bot 正在对谁说话 (target)
            topic: 话题标识
            social_graph: 用于 circle 级别判断 in_circle 关系
        """
        # 1. 明确禁止: 硬约束
        if topic in self._forbidden.get(src_user, set()):
            return False

        # 2-4. 按隐私级别判断
        level = self.get_privacy(src_user, topic)
        if level == PrivacyLevel.PRIVATE:
            return False
        if level == PrivacyLevel.PUBLIC:
            return True
        if level == PrivacyLevel.CIRCLE:
            # circle: 需 in_circle 检查
            if social_graph is None:
                return False  # 无 social_graph, 保守拒绝
            in_circle = social_graph.get_in_circle(src_user)
            return dst_user in in_circle

        return False  # 未知级别: 保守拒绝

    def get_privacy(self, user_id: str, topic: str) -> PrivacyLevel:
        """获取 user 的 topic 隐私级别 (未设置返回默认 private)。"""
        return self._privacy.get(user_id, {}).get(topic, _DEFAULT_PRIVACY)

    def list_topics(self, user_id: str) -> list[str]:
        """列出 user 设置过的所有话题。"""
        return list(self._privacy.get(user_id, {}).keys())

    def to_dict(self) -> dict[str, Any]:
        """序列化为 SpiritStore topics 格式。"""
        return {
            "privacy": {
                user_id: {topic: level.value for topic, level in topics.items()}
                for user_id, topics in self._privacy.items()
            },
            "forbidden": {
                user_id: list(topics) for user_id, topics in self._forbidden.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TopicPrivacy":
        """从 SpiritStore 格式反序列化。"""
        tp = cls()
        privacy_data = data.get("privacy", {})
        for user_id, topics in privacy_data.items():
            for topic, level in topics.items():
                tp._privacy.setdefault(user_id, {})[topic] = PrivacyLevel(level)
        forbidden_data = data.get("forbidden", {})
        for user_id, topics in forbidden_data.items():
            tp._forbidden[user_id] = set(topics)
        return tp
