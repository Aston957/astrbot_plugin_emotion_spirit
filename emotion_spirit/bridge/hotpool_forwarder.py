"""HotPoolForwarder — SylannEngine inject() 信号 → MemoryPool 转发。

策略 B+C:
  - B: 影响该 session 最近的 N 条记忆 (按创建时间排序)
  - C: 通过 source_text 做关键词匹配, 只影响相关记忆 (用 CascadeEngine 倒排索引)

两种策略取并集, 然后对每条命中的记忆调用 entry.on_inject()。
最后触发 cascade 传播。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..core.registry import register

if TYPE_CHECKING:
    from ..memory.memory_pool import MemoryPool
    from ..memory.unified_entry import UnifiedEntry

logger = logging.getLogger(__name__)

__all__ = ["HotPoolForwarder"]

# 策略 B: 最近 N 条记忆
_RECENT_N = 10

# 信号类型 → 效果强度映射 (与 UnifiedEntry.on_inject 一致)
_VALID_SIGNALS = frozenset({
    "contradiction",
    "reinforcement",
    "revelation",
    "betrayal",
    "validation",
})


@register(
    name="hotpool_forwarder",
    provides=["HotPoolForwarder"],
    depends_on=["memory_pool"],
)
class HotPoolForwarder:
    """将 SylannEngine 的 inject() 信号转发到 MemoryPool。

    使用 B+C 策略确定影响范围:
      B: 最近 N 条记忆 (按创建时间倒序)
      C: source_text 关键词匹配 (通过 CascadeEngine 倒排索引)

    两种策略取并集, 然后:
      1. 对每条命中的记忆调用 entry.on_inject(signal_type, intensity)
      2. 触发 cascade 传播
    """

    def __init__(self, memory_pool: "MemoryPool | None" = None) -> None:
        self._memory = memory_pool

    def set_memory_pool(self, memory: "MemoryPool") -> None:
        """注入 MemoryPool 实例。"""
        self._memory = memory

    def forward(
        self,
        session_id: str,
        signal_type: str,
        intensity: float,
        source_text: str = "",
    ) -> int:
        """将 inject 信号转发到 MemoryPool。

        Args:
            session_id: 会话标识 (用于过滤该用户的记忆)。
            signal_type: 信号类型 (contradiction/reinforcement/revelation/betrayal/validation)。
            intensity: 信号强度 [0, 1]。
            source_text: 源文本, 用于关键词匹配。

        Returns:
            受影响的记忆条数。
        """
        if self._memory is None:
            return 0

        if signal_type not in _VALID_SIGNALS:
            logger.debug("HotPoolForwarder: 未知信号类型 '%s', 跳过", signal_type)
            return 0

        # 收集候选记忆 (B+C 并集)
        candidates = self._find_candidates(session_id, source_text)

        if not candidates:
            return 0

        # 对每条候选记忆施加信号
        affected = 0
        for entry in candidates:
            try:
                entry.on_inject(signal_type, intensity)
                affected += 1
            except Exception as e:
                logger.warning(
                    "HotPoolForwarder: entry.on_inject() 失败 (id=%s): %s",
                    entry.id, e,
                )

        # 触发 cascade
        if affected > 0:
            self._trigger_cascade(candidates)

        logger.debug(
            "HotPoolForwarder: forward(session=%s, signal=%s, intensity=%.2f) → %d/%d affected",
            session_id[:8], signal_type, intensity, affected, len(candidates),
        )
        return affected

    def _find_candidates(
        self,
        session_id: str,
        source_text: str,
    ) -> list[UnifiedEntry]:
        """B+C 策略: 找到候选记忆列表。"""
        seen_ids: set[str] = set()
        candidates: list[UnifiedEntry] = []

        # 策略 B: 最近 N 条 (按创建时间倒序)
        recent = self._find_recent(session_id, _RECENT_N)
        for entry in recent:
            if entry.id not in seen_ids:
                seen_ids.add(entry.id)
                candidates.append(entry)

        # 策略 C: 关键词匹配
        if source_text:
            matched = self._find_by_keywords(source_text)
            for entry in matched:
                if entry.id not in seen_ids:
                    seen_ids.add(entry.id)
                    candidates.append(entry)

        return candidates

    def _find_recent(
        self,
        session_id: str,
        n: int,
    ) -> list[UnifiedEntry]:
        """策略 B: 找到该 session 最近的 N 条记忆。"""
        all_entries = list(self._memory._entries.values())

        # 过滤该 session 的记忆 (source_user 匹配)
        session_entries = [
            e for e in all_entries
            if e.source_user == session_id
        ]

        # 按创建时间倒序, 取前 N
        session_entries.sort(key=lambda e: e.created_at, reverse=True)
        return session_entries[:n]

    def _find_by_keywords(self, source_text: str) -> list[UnifiedEntry]:
        """策略 C: 通过 CascadeEngine 倒排索引做关键词匹配。"""
        cascade_engine = self._memory._cascade_engine
        if cascade_engine is None:
            return []

        # 从 source_text 提取关键词 (简单分词: 按空格和标点)
        keywords = self._extract_keywords(source_text)
        if not keywords:
            return []

        # 通过倒排索引查找包含这些关键词的记忆
        matched_ids: set[str] = set()
        for kw in keywords:
            # 查 tag 索引
            if kw in cascade_engine._tag_index:
                matched_ids.update(cascade_engine._tag_index[kw])
            # 查 entity 索引
            if kw in cascade_engine._entity_index:
                matched_ids.update(cascade_engine._entity_index[kw])

        # 返回对应的 UnifiedEntry 对象
        return [
            self._memory._entries[entry_id]
            for entry_id in matched_ids
            if entry_id in self._memory._entries
        ]

    def _trigger_cascade(self, sources: list[UnifiedEntry]) -> None:
        """对受影响的记忆触发 cascade 传播。"""
        cascade_engine = self._memory._cascade_engine
        if cascade_engine is None:
            return

        # 使用默认 sensitivity
        sensitivity = 0.5

        for source in sources:
            try:
                related_ids = cascade_engine.find_related(source)
                for entry_id in related_ids:
                    entry = self._memory._entries.get(entry_id)
                    if entry is None:
                        continue
                    # 计算相关度并传播热量
                    r = self._relevance(source, entry)
                    if r > 0.2:
                        heat_transfer = source.temperature * r * sensitivity
                        entry.temperature = min(1.0, entry.temperature + heat_transfer)
            except Exception as e:
                logger.debug("HotPoolForwarder: cascade 传播失败: %s", e)

    @staticmethod
    def _relevance(a: UnifiedEntry, b: UnifiedEntry) -> float:
        """计算两条记忆的相关度 (tag + entity + text 混合)。"""
        # Tag overlap (Jaccard)
        tags_a = set(a.tags)
        tags_b = set(b.tags)
        tag_union = tags_a | tags_b
        tag_overlap = len(tags_a & tags_b) / max(len(tag_union), 1)

        # Entity overlap
        entities_a = set()
        for elist in a.entities.values():
            entities_a.update(elist)
        entities_b = set()
        for elist in b.entities.values():
            entities_b.update(elist)
        entity_union = entities_a | entities_b
        entity_overlap = len(entities_a & entities_b) / max(len(entity_union), 1)

        # Text keyword overlap
        kw_a = set(HotPoolForwarder._extract_keywords(a.text))
        kw_b = set(HotPoolForwarder._extract_keywords(b.text))
        kw_union = kw_a | kw_b
        text_overlap = len(kw_a & kw_b) / max(len(kw_union), 1)

        return 0.4 * tag_overlap + 0.3 * entity_overlap + 0.3 * text_overlap

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """从文本中提取关键词 (简单分词)。"""
        import re
        # 中文: 取连续中文字符片段 (2字以上)
        cn = re.findall(r'[一-鿿]{2,}', text)
        # 英文: 取连续字母片段 (3字母以上, 小写)
        en = [w.lower() for w in re.findall(r'[a-zA-Z]{3,}', text)]
        return cn + en
