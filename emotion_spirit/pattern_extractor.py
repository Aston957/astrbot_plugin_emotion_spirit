"""冷池模式提取 — 从温池记忆中提取行为模式。

模式类型:
  循环: 同一标签对反复出现 (hurt→repair→hurt→repair)
  趋势: 某标签频率单调增加/减少
  触发: 特定条件 → 特定情感
  回避: 预期出现但未出现的标签
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .memory_pool import MemoryPool


@dataclass
class Pattern:
    """行为模式。"""
    id: str
    pattern_type: str           # "循环" | "趋势" | "触发" | "回避"
    tags: list[str]
    count: int
    first_seen: float
    last_seen: float
    avg_phi: float
    avg_emotional_weight: float
    examples: list[str] = field(default_factory=list)  # 原始记忆 ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pattern_type": self.pattern_type,
            "tags": self.tags,
            "count": self.count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "avg_phi": round(self.avg_phi, 6),
            "avg_emotional_weight": round(self.avg_emotional_weight, 6),
            "examples": self.examples[:5],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pattern:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class PatternExtractor:
    """从温池提取行为模式。"""

    def __init__(self, pool: MemoryPool) -> None:
        self._pool = pool
        self._patterns: list[Pattern] = []
        self._next_id = 0

    def extract(self, window_days: int = 10) -> list[Pattern]:
        """从温池提取模式。"""
        cutoff = time.time() - window_days * 86400
        entries = [e for e in self._pool.warm if e.created_at > cutoff]

        if len(entries) < 3:
            return []

        patterns = []
        patterns.extend(self._detect_cycles(entries))
        patterns.extend(self._detect_trends(entries, window_days))
        patterns.extend(self._detect_triggers(entries))
        patterns.extend(self._detect_avoidances(entries))

        self._patterns.extend(patterns)
        return patterns

    def store_patterns(self, patterns: list[Pattern]) -> None:
        """存入模式库。"""
        self._patterns.extend(patterns)

    def get_patterns(
        self,
        pattern_type: str | None = None,
        tag: str | None = None,
    ) -> list[Pattern]:
        """检索模式。"""
        results = self._patterns
        if pattern_type:
            results = [p for p in results if p.pattern_type == pattern_type]
        if tag:
            results = [p for p in results if tag in p.tags]
        return results

    def _detect_cycles(self, entries) -> list[Pattern]:
        """检测循环: 标签序列 A→B→A→B。"""
        patterns = []
        sorted_entries = sorted(entries, key=lambda e: e.created_at)

        # 提取标签序列
        tag_seq = []
        for entry in sorted_entries:
            for tag in entry.tags:
                tag_seq.append((tag, entry))

        # 滑动窗口找重复对 (AB → AB)
        pair_counts: dict[tuple[str, str], list] = {}
        for i in range(len(tag_seq) - 1):
            pair = (tag_seq[i][0], tag_seq[i + 1][0])
            if pair[0] != pair[1]:  # 忽略自循环
                if pair not in pair_counts:
                    pair_counts[pair] = []
                pair_counts[pair].append(tag_seq[i][1])

        for pair, entries_list in pair_counts.items():
            if len(entries_list) >= 2:
                all_entries = entries_list
                patterns.append(Pattern(
                    id=f"cycle_{self._next_id}",
                    pattern_type="循环",
                    tags=list(pair),
                    count=len(entries_list),
                    first_seen=min(e.created_at for e in all_entries),
                    last_seen=max(e.created_at for e in all_entries),
                    avg_phi=sum(e.phi_at_creation for e in all_entries) / len(all_entries),
                    avg_emotional_weight=sum(e.emotional_weight for e in all_entries) / len(all_entries),
                    examples=[e.id for e in all_entries[:5]],
                ))
                self._next_id += 1

        return patterns

    def _detect_trends(self, entries, window_days: int) -> list[Pattern]:
        """检测趋势: 某标签频率单调变化。"""
        patterns = []
        tag_by_day: dict[str, dict[int, int]] = {}

        for entry in entries:
            day = int((entry.created_at - entries[0].created_at) / 86400)
            for tag in entry.tags:
                if tag not in tag_by_day:
                    tag_by_day[tag] = {}
                tag_by_day[tag][day] = tag_by_day[tag].get(day, 0) + 1

        for tag, daily_counts in tag_by_day.items():
            if len(daily_counts) < 3:
                continue
            days = sorted(daily_counts.keys())
            counts = [daily_counts[d] for d in days]

            # 简单调性检测: 前半 vs 后半
            mid = len(counts) // 2
            early_avg = sum(counts[:mid]) / max(1, mid)
            late_avg = sum(counts[mid:]) / max(1, len(counts) - mid)

            if late_avg > early_avg * 1.5:
                trend_dir = "increasing"
            elif late_avg < early_avg * 0.5:
                trend_dir = "decreasing"
            else:
                continue

            tag_entries = [e for e in entries if tag in e.tags]
            patterns.append(Pattern(
                id=f"trend_{self._next_id}",
                pattern_type="趋势",
                tags=[tag],
                count=len(tag_entries),
                first_seen=min(e.created_at for e in tag_entries),
                last_seen=max(e.created_at for e in tag_entries),
                avg_phi=sum(e.phi_at_creation for e in tag_entries) / len(tag_entries),
                avg_emotional_weight=sum(e.emotional_weight for e in tag_entries) / len(tag_entries),
                examples=[e.id for e in tag_entries[:5]],
            ))
            self._next_id += 1

        return patterns

    def _detect_triggers(self, entries) -> list[Pattern]:
        """检测触发: 条件 A → 情感 B。"""
        patterns = []
        sorted_entries = sorted(entries, key=lambda e: e.created_at)

        # 找连续条目标签对的条件概率
        pair_counts: dict[tuple[str, str], int] = {}
        tag_counts: dict[str, int] = {}

        for entry in sorted_entries:
            for tag in entry.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        for i in range(len(sorted_entries) - 1):
            tags_a = sorted_entries[i].tags
            tags_b = sorted_entries[i + 1].tags
            for a in tags_a:
                for b in tags_b:
                    if a != b:
                        pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1

        for (a, b), count in pair_counts.items():
            if count >= 3 and tag_counts.get(a, 0) > 0:
                prob = count / tag_counts[a]
                if prob > 0.5:  # 高条件概率
                    trigger_entries = [e for e in sorted_entries if a in e.tags or b in e.tags]
                    patterns.append(Pattern(
                        id=f"trigger_{self._next_id}",
                        pattern_type="触发",
                        tags=[a, b],
                        count=count,
                        first_seen=min(e.created_at for e in trigger_entries),
                        last_seen=max(e.created_at for e in trigger_entries),
                        avg_phi=sum(e.phi_at_creation for e in trigger_entries) / max(1, len(trigger_entries)),
                        avg_emotional_weight=sum(e.emotional_weight for e in trigger_entries) / max(1, len(trigger_entries)),
                        examples=[e.id for e in trigger_entries[:5]],
                    ))
                    self._next_id += 1

        return patterns

    def _detect_avoidances(self, entries) -> list[Pattern]:
        """检测回避: 预期但未出现的标签。"""
        patterns = []

        # 常见情感标签 (预期应该出现的)
        expected_tags = {"repair", "express", "explore", "reach_out", "hold", "withdraw", "observe"}
        present_tags = set()
        for entry in entries:
            present_tags.update(entry.tags)

        missing = expected_tags - present_tags
        for tag in missing:
            # 只有在有足够数据时才算回避
            if len(entries) >= 10:
                patterns.append(Pattern(
                    id=f"avoid_{self._next_id}",
                    pattern_type="回避",
                    tags=[tag],
                    count=0,
                    first_seen=entries[0].created_at,
                    last_seen=entries[-1].created_at,
                    avg_phi=0.0,
                    avg_emotional_weight=0.0,
                    examples=[],
                ))
                self._next_id += 1

        return patterns

    def to_dict(self) -> dict[str, Any]:
        return {
            "patterns": [p.to_dict() for p in self._patterns],
            "next_id": self._next_id,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self._patterns = [Pattern.from_dict(p) for p in data.get("patterns", [])]
        self._next_id = data.get("next_id", 0)
