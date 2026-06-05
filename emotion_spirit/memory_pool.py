"""缓冲池 + 温池 + 冷池 + 幽灵 — 四层记忆管理。

缓冲池: 待确认的事件记忆 (Φ 门控等待区 + Mode B 原料)
温池: 已确认的有意义事件
冷池: 模式沉淀 (标签化、可检索)
幽灵: 永久情感痕迹
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from astrbot.api import logger
from .config import BUFFER_POOL_CONFIG, MEMORY_POOL_CONFIG


@dataclass
class BufferEntry:
    """缓冲池条目 — 待确认的记忆。"""
    id: str
    text: str
    raw_weight: float
    phi_at_creation: float
    phi_history: list[float] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_user: str = ""
    created_at: float = field(default_factory=time.time)

    @property
    def phi_avg(self) -> float:
        """近期 Φ 平均值 (EMA)。"""
        if not self.phi_history:
            return self.phi_at_creation
        alpha = 0.3
        ema = self.phi_history[0]
        for phi in self.phi_history[1:]:
            ema = ema * (1 - alpha) + phi * alpha
        return ema

    @property
    def confirmed_weight(self) -> float:
        """确认后的最终权重。"""
        base = BUFFER_POOL_CONFIG["meaning_gate_base"]
        phi_w = BUFFER_POOL_CONFIG["meaning_gate_phi_weight"]
        meaning_gate = base + phi_w * self.phi_avg
        return self.raw_weight * meaning_gate

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "text": self.text,
            "raw_weight": round(self.raw_weight, 6),
            "phi_at_creation": round(self.phi_at_creation, 6),
            "phi_history": [round(p, 6) for p in self.phi_history[-20:]],
            "tags": self.tags, "source_user": self.source_user,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BufferEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MemoryEntry:
    """已确认的记忆条目。"""
    id: str
    text: str
    emotional_weight: float
    phi_at_creation: float
    tags: list[str] = field(default_factory=list)
    source_user: str = ""
    tier: str = "warm"
    created_at: float = field(default_factory=time.time)
    last_recalled: float = 0.0
    recall_count: int = 0
    is_ghost: bool = False
    ghost_sensitivity_shift: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "text": self.text,
            "emotional_weight": round(self.emotional_weight, 6),
            "phi_at_creation": round(self.phi_at_creation, 6),
            "tags": self.tags, "source_user": self.source_user,
            "tier": self.tier, "created_at": self.created_at,
            "last_recalled": self.last_recalled,
            "recall_count": self.recall_count,
            "is_ghost": self.is_ghost,
            "ghost_sensitivity_shift": round(self.ghost_sensitivity_shift, 6),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class MemoryPool:
    """四层记忆池管理器。"""

    def __init__(self) -> None:
        self.buffer: list[BufferEntry] = []
        self.warm: list[MemoryEntry] = []
        self.cold: list[MemoryEntry] = []
        self.ghosts: list[MemoryEntry] = []
        self._next_id = 0
        # 倒排索引
        self._tag_index: dict[str, list[MemoryEntry]] = {}
        self._text_index: dict[str, list[MemoryEntry]] = {}

    def add(
        self,
        text: str,
        raw_weight: float,
        phi: float,
        tags: list[str],
        source_user: str,
    ) -> BufferEntry | None:
        """每条消息先进缓冲池。"""
        entry = BufferEntry(
            id=f"buf_{self._next_id}",
            text=text,
            raw_weight=raw_weight,
            phi_at_creation=phi,
            phi_history=[phi],
            tags=list(tags),
            source_user=source_user,
        )
        self._next_id += 1
        self.buffer.append(entry)

        # 检查直通幽灵
        bypass_ghost_w = BUFFER_POOL_CONFIG["bypass_ghost_weight"]
        if raw_weight > bypass_ghost_w and any(t in tags for t in ["betrayal", "collapse"]):
            self._form_ghost_from_buffer(entry)
            return entry

        # 检查直通冷池
        bypass_phi = BUFFER_POOL_CONFIG["bypass_cold_phi"]
        bypass_cold_w = BUFFER_POOL_CONFIG["bypass_cold_weight"]
        if phi > bypass_phi and raw_weight > bypass_cold_w:
            self._promote_to_cold(entry)
            return entry

        # 缓冲池容量限制
        max_buf = int(BUFFER_POOL_CONFIG["max"])
        if len(self.buffer) > max_buf:
            self.buffer.sort(key=lambda e: e.created_at)
            overflow = self.buffer.pop(0)
            if overflow.confirmed_weight > MEMORY_POOL_CONFIG.get("recall_boost", 0.05):
                self._promote_to_warm(overflow)

        return entry

    def update_phi(self, current_phi: float) -> None:
        """每次 Surface 更新时，更新缓冲池中条目的 Φ 历史。"""
        for entry in self.buffer:
            entry.phi_history.append(current_phi)
            if len(entry.phi_history) > 20:
                entry.phi_history = entry.phi_history[-20:]

    def confirm_check(self) -> list[MemoryEntry]:
        """检查缓冲池中哪些条目可以确认。返回新确认的条目。"""
        from .buffer_signals import BufferSignals
        now = time.time()
        still_buffer: list[BufferEntry] = []
        confirmed: list[MemoryEntry] = []
        phi_threshold = BUFFER_POOL_CONFIG["confirm_phi_threshold"]
        noise_threshold = BUFFER_POOL_CONFIG["noise_threshold"]
        ttl_seconds = BUFFER_POOL_CONFIG["ttl_hours"] * 3600

        for entry in self.buffer:
            age = now - entry.created_at
            cw = entry.confirmed_weight

            if entry.phi_avg > phi_threshold and cw > noise_threshold:
                warm_entry = self._promote_to_warm(entry)
                confirmed.append(warm_entry)
            elif age > ttl_seconds:
                # 超时丢弃 (噪声)
                pass
            else:
                still_buffer.append(entry)

        self.buffer = still_buffer
        return confirmed

    def consolidate(self) -> list[MemoryEntry]:
        """温池 → 冷池流转。"""
        now = time.time()
        warm_ttl = MEMORY_POOL_CONFIG["warm_to_cold_ttl_hours"] * 3600
        consolidated: list[MemoryEntry] = []

        still_warm: list[MemoryEntry] = []
        for entry in self.warm:
            if now - entry.created_at > warm_ttl:
                entry.tier = "cold"
                self.cold.append(entry)
                self._build_index(entry)
                consolidated.append(entry)
            else:
                still_warm.append(entry)
        self.warm = still_warm

        # 冷池容量限制
        cold_max = int(MEMORY_POOL_CONFIG["cold_max"])
        if len(self.cold) > cold_max:
            self.cold.sort(key=lambda e: e.emotional_weight * (1 + e.recall_count * 0.05))
            self.cold = self.cold[-cold_max:]

        return consolidated

    def recall(self, keyword: str, max_results: int = 5) -> list[MemoryEntry]:
        """O(k) 倒排索引召回。"""
        seen_ids: set[str] = set()
        candidates: list[MemoryEntry] = []
        for tag, entries in self._tag_index.items():
            if keyword in tag:
                for e in entries:
                    if e.id not in seen_ids:
                        seen_ids.add(e.id)
                        candidates.append(e)
        for word, entries in self._text_index.items():
            if keyword in word:
                for e in entries:
                    if e.id not in seen_ids:
                        seen_ids.add(e.id)
                        candidates.append(e)

        results = sorted(candidates, key=lambda e: e.emotional_weight, reverse=True)
        boost = MEMORY_POOL_CONFIG["recall_boost"]
        for entry in results[:max_results]:
            entry.last_recalled = time.time()
            entry.recall_count += 1
            entry.emotional_weight = min(1.0, entry.emotional_weight + boost)
        return results[:max_results]

    def sample_for_mode_a(self, minutes: int = 60) -> list[BufferEntry]:
        """Mode A 采样: 缓冲池中最近 N 分钟的条目。"""
        cutoff = time.time() - minutes * 60
        return [e for e in self.buffer if e.created_at > cutoff]

    def sample_for_mode_b(self, k: int = 3) -> list[BufferEntry]:
        """Mode B 采样: 按情感权重 × 时间衰减加权。"""
        if not self.buffer:
            return []
        now = time.time()
        scored = [
            (e, e.raw_weight * math.exp(-(now - e.created_at) / 3600))
            for e in self.buffer
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [e for e, _ in scored[:k]]

    def _promote_to_warm(self, entry: BufferEntry) -> MemoryEntry:
        """从缓冲池提升到温池。"""
        warm_entry = MemoryEntry(
            id=entry.id.replace("buf_", "mem_"),
            text=entry.text,
            emotional_weight=entry.confirmed_weight,
            phi_at_creation=entry.phi_at_creation,
            tags=list(entry.tags),
            source_user=entry.source_user,
        )
        self.warm.append(warm_entry)
        self._build_index(warm_entry)
        return warm_entry

    def _promote_to_cold(self, entry: BufferEntry) -> MemoryEntry:
        """从缓冲池直通冷池。"""
        cold_entry = MemoryEntry(
            id=entry.id.replace("buf_", "cold_"),
            text=entry.text,
            emotional_weight=entry.confirmed_weight,
            phi_at_creation=entry.phi_at_creation,
            tags=list(entry.tags),
            source_user=entry.source_user,
            tier="cold",
        )
        self.cold.append(cold_entry)
        self._build_index(cold_entry)
        return cold_entry

    def _form_ghost_from_buffer(self, entry: BufferEntry) -> MemoryEntry:
        """从缓冲池直通幽灵。"""
        ghost = MemoryEntry(
            id=entry.id.replace("buf_", "ghost_"),
            text=entry.text,
            emotional_weight=entry.raw_weight,
            phi_at_creation=entry.phi_at_creation,
            tags=list(entry.tags),
            source_user=entry.source_user,
            tier="ghost",
            is_ghost=True,
        )
        self.ghosts.append(ghost)
        ghost_max = int(MEMORY_POOL_CONFIG["ghost_max"])
        if len(self.ghosts) > ghost_max:
            self.ghosts = self.ghosts[-ghost_max:]
        return ghost

    def _build_index(self, entry: MemoryEntry) -> None:
        """添加条目时同步更新倒排索引。"""
        for tag in entry.tags:
            self._tag_index.setdefault(tag, []).append(entry)
        for word in entry.text.split():
            self._text_index.setdefault(word, []).append(entry)

    def to_dict(self) -> dict[str, Any]:
        return {
            "buffer": [e.to_dict() for e in self.buffer],
            "warm": [e.to_dict() for e in self.warm],
            "cold": [e.to_dict() for e in self.cold],
            "ghosts": [e.to_dict() for e in self.ghosts],
            "next_id": self._next_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryPool:
        pool = cls()
        pool._next_id = data.get("next_id", 0)
        for e in data.get("buffer", []):
            pool.buffer.append(BufferEntry.from_dict(e))
        for e in data.get("warm", []):
            pool.warm.append(MemoryEntry.from_dict(e))
        for e in data.get("cold", []):
            pool.cold.append(MemoryEntry.from_dict(e))
        for e in data.get("ghosts", []):
            pool.ghosts.append(MemoryEntry.from_dict(e))
        # 重建索引
        for entry in pool.warm + pool.cold + pool.ghosts:
            pool._build_index(entry)
        return pool
