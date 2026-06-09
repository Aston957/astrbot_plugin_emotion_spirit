"""缓冲池 + 温池 + 冷池 + 幽灵 — 四层记忆管理 (Phase 2.0 per-user)。

缓冲池: 待确认的事件记忆 (Φ 门控等待区 + Mode B 原料)
温池: 已确认的有意义事件
冷池: 模式沉淀 (标签化、可检索)
幽灵: 永久情感痕迹

v2.0: per-user 隔离 (CPM 边界 + Bowlby 工作模型)
- 内部 dict[user_id, _UserPool]
- 旧 API (buffer/warm/cold/ghosts 全局) 保留为 shim, 代理到 <global> 用户池
- 新 API: add_for_user, recall_for_user, buffer_for, warm_for, cold_for, ghosts_for
- 聚合 API: all_warm, all_cold, all_buffer, all_ghosts (供下游模块)
- 隐私字段: privacy (private/circle/public) + entities (dict, e.g. {person: [bob]})
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from astrbot.api import logger
from .config import BUFFER_POOL_CONFIG, MEMORY_POOL_CONFIG


# Phase 2.0: 全局 fallback 用户 ID (旧 API 代理目标)
GLOBAL_USER_ID = "<global>"



__all__ = [
    "GLOBAL_USER_ID",
    "BufferEntry",
    "MemoryEntry",
    "MemoryPool",
]

@dataclass
class _UserPool:
    """单用户的四层记忆池状态 (Phase 2.0)。"""
    buffer: list = field(default_factory=list)
    warm: list = field(default_factory=list)
    cold: list = field(default_factory=list)
    ghosts: list = field(default_factory=list)
    _tag_index: dict = field(default_factory=dict)
    _text_index: dict = field(default_factory=dict)
    _next_id: int = 0


@dataclass
class BufferEntry:
    """缓冲池条目 — 待确认的记忆。"""
    id: str
    text: str
    raw_weight: float
    phi_at_creation: float
    phi_history: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    source_user: str = ""
    created_at: float = field(default_factory=time.time)
    # v2.0: 隐私边界 (CPM)
    privacy: str = "private"
    entities: dict = field(default_factory=dict)  # e.g. {"person": ["bob"], "place": [...]}

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

    def to_dict(self) -> dict:
        return {
            "id": self.id, "text": self.text,
            "raw_weight": round(self.raw_weight, 6),
            "phi_at_creation": round(self.phi_at_creation, 6),
            "phi_history": [round(p, 6) for p in self.phi_history[-20:]],
            "tags": self.tags, "source_user": self.source_user,
            "created_at": self.created_at,
            "privacy": self.privacy,
            "entities": self.entities,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BufferEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MemoryEntry:
    """已确认的记忆条目。"""
    id: str
    text: str
    emotional_weight: float
    phi_at_creation: float
    tags: list = field(default_factory=list)
    source_user: str = ""
    tier: str = "warm"
    created_at: float = field(default_factory=time.time)
    last_recalled: float = 0.0
    recall_count: int = 0
    is_ghost: bool = False
    ghost_sensitivity_shift: float = 0.0
    # v2.0: 隐私边界 (CPM)
    privacy: str = "private"
    entities: dict = field(default_factory=dict)  # e.g. {"person": ["bob"], "place": [...]}

    def to_dict(self) -> dict:
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
            "privacy": self.privacy,
            "entities": self.entities,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


from .registry import register


@register(name="memory_pool", provides=["MemoryPool"], depends_on=[])
class MemoryPool:
    """四层记忆池管理器 (Phase 2.0: per-user 隔离)。"""

    def __init__(self) -> None:
        # v2.0: per-user 池子字典
        self._pools: dict = {}
        # v2.0: 旧 API shim — 代理到 <global> 用户池
        self._legacy = self._get_pool(GLOBAL_USER_ID)
        # 暴露 _next_id (旧 API 兼容)
        self._next_id = self._legacy._next_id

    # ═══ 旧 API 兼容属性 (property, 动态返回 <global> 池状态) ═══

    @property
    def buffer(self) -> list:
        """旧 API: <global> 池的 buffer (动态引用)。"""
        return self._legacy.buffer

    @property
    def warm(self) -> list:
        """旧 API: <global> 池的 warm (动态引用)。"""
        return self._legacy.warm

    @property
    def cold(self) -> list:
        """旧 API: <global> 池的 cold (动态引用)。"""
        return self._legacy.cold

    @property
    def ghosts(self) -> list:
        """旧 API: <global> 池的 ghosts (动态引用)。"""
        return self._legacy.ghosts

    def _get_pool(self, user_id: str) -> _UserPool:
        """获取或创建 user 的记忆池。"""
        if user_id not in self._pools:
            self._pools[user_id] = _UserPool()
        return self._pools[user_id]

    # ═══ Per-user API (v2.0) ═══

    def add_for_user(
        self,
        user_id: str,
        text: str,
        raw_weight: float,
        phi: float,
        tags: list,
        source_user: str,
        privacy: str = "private",
        entities: dict | None = None,
    ):
        """Phase 2.0: per-user 添加到缓冲池。"""
        pool = self._get_pool(user_id)
        entry = BufferEntry(
            id=f"buf_{pool._next_id}",
            text=text,
            raw_weight=raw_weight,
            phi_at_creation=phi,
            phi_history=[phi],
            tags=list(tags),
            source_user=source_user,
            privacy=privacy,
            entities=entities or {},
        )
        pool._next_id += 1
        pool.buffer.append(entry)

        # 检查直通幽灵
        bypass_ghost_w = BUFFER_POOL_CONFIG["bypass_ghost_weight"]
        if raw_weight > bypass_ghost_w and any(t in tags for t in ["betrayal", "collapse"]):
            self._form_ghost_for_user(user_id, entry)
            return entry

        # 检查直通冷池
        bypass_phi = BUFFER_POOL_CONFIG["bypass_cold_phi"]
        bypass_cold_w = BUFFER_POOL_CONFIG["bypass_cold_weight"]
        if phi > bypass_phi and raw_weight > bypass_cold_w:
            self._promote_to_cold_for_user(user_id, entry)
            return entry

        # 缓冲池容量限制
        max_buf = int(BUFFER_POOL_CONFIG["max"])
        if len(pool.buffer) > max_buf:
            pool.buffer.sort(key=lambda e: e.created_at)
            overflow = pool.buffer.pop(0)
            if overflow.confirmed_weight > MEMORY_POOL_CONFIG.get("recall_boost", 0.05):
                self._promote_to_warm_for_user(user_id, overflow)

        return entry

    def update_phi_for_user(self, user_id: str, current_phi: float) -> None:
        """Phase 2.0: per-user 更新缓冲池 Φ 历史。"""
        pool = self._get_pool(user_id)
        for entry in pool.buffer:
            entry.phi_history.append(current_phi)
            if len(entry.phi_history) > 20:
                entry.phi_history = entry.phi_history[-20:]

    def confirm_check_for_user(self, user_id: str) -> list:
        """Phase 2.0: per-user 检查缓冲池中可确认的条目。"""
        pool = self._get_pool(user_id)
        now = time.time()
        still_buffer: list = []
        confirmed: list = []
        phi_threshold = BUFFER_POOL_CONFIG["confirm_phi_threshold"]
        noise_threshold = BUFFER_POOL_CONFIG["noise_threshold"]
        ttl_seconds = BUFFER_POOL_CONFIG["ttl_hours"] * 3600

        for entry in pool.buffer:
            age = now - entry.created_at
            cw = entry.confirmed_weight

            if entry.phi_avg > phi_threshold and cw > noise_threshold:
                warm_entry = self._promote_to_warm_for_user(user_id, entry)
                confirmed.append(warm_entry)
            elif age > ttl_seconds:
                pass  # 超时丢弃
            else:
                still_buffer.append(entry)

        pool.buffer = still_buffer
        return confirmed

    def consolidate_for_user(self, user_id: str) -> list:
        """Phase 2.0: per-user 温池 → 冷池流转。"""
        pool = self._get_pool(user_id)
        now = time.time()
        warm_ttl = MEMORY_POOL_CONFIG["warm_to_cold_ttl_hours"] * 3600
        consolidated: list = []

        still_warm: list = []
        for entry in pool.warm:
            if now - entry.created_at > warm_ttl:
                entry.tier = "cold"
                pool.cold.append(entry)
                self._build_index_for_user(user_id, entry)
                consolidated.append(entry)
            else:
                still_warm.append(entry)
        pool.warm = still_warm

        # 冷池容量限制
        cold_max = int(MEMORY_POOL_CONFIG["cold_max"])
        if len(pool.cold) > cold_max:
            pool.cold.sort(key=lambda e: e.emotional_weight * (1 + e.recall_count * 0.05))
            pool.cold = pool.cold[-cold_max:]

        return consolidated

    def recall_for_user(
        self,
        user_id: str,
        keyword: str,
        max_results: int = 5,
        privacy_filter: list | None = None,
    ) -> list:
        """Phase 2.0: per-user 倒排索引召回 (支持 privacy_filter)。"""
        pool = self._get_pool(user_id)
        seen_ids: set = set()
        candidates: list = []
        for tag, entries in pool._tag_index.items():
            if keyword in tag:
                for e in entries:
                    if e.id not in seen_ids:
                        seen_ids.add(e.id)
                        candidates.append(e)
        for word, entries in pool._text_index.items():
            if keyword in word:
                for e in entries:
                    if e.id not in seen_ids:
                        seen_ids.add(e.id)
                        candidates.append(e)

        # Phase 2.0: privacy 过滤
        if privacy_filter:
            candidates = [e for e in candidates if e.privacy in privacy_filter]

        results = sorted(candidates, key=lambda e: e.emotional_weight, reverse=True)
        boost = MEMORY_POOL_CONFIG["recall_boost"]
        for entry in results[:max_results]:
            entry.last_recalled = time.time()
            entry.recall_count += 1
            entry.emotional_weight = min(1.0, entry.emotional_weight + boost)
        return results[:max_results]

    # ═══ Per-user 视图 (无 copy, 返回引用供只读) ═══

    def buffer_for(self, user_id: str) -> list:
        """Phase 2.0: 获取 user 的缓冲池引用。"""
        return self._get_pool(user_id).buffer

    def warm_for(self, user_id: str) -> list:
        """Phase 2.0: 获取 user 的温池引用。"""
        return self._get_pool(user_id).warm

    def cold_for(self, user_id: str) -> list:
        """Phase 2.0: 获取 user 的冷池引用。"""
        return self._get_pool(user_id).cold

    def ghosts_for(self, user_id: str) -> list:
        """Phase 2.0: 获取 user 的幽灵池引用。"""
        return self._get_pool(user_id).ghosts

    # ═══ 聚合视图 (v2.0: 供下游模块读全量) ═══

    def all_buffer(self) -> list:
        """Phase 2.0: 聚合所有 user 的缓冲池。"""
        out: list = []
        for pool in self._pools.values():
            out.extend(pool.buffer)
        return out

    def all_warm(self) -> list:
        """Phase 2.0: 聚合所有 user 的温池。"""
        out: list = []
        for pool in self._pools.values():
            out.extend(pool.warm)
        return out

    def all_cold(self) -> list:
        """Phase 2.0: 聚合所有 user 的冷池。"""
        out: list = []
        for pool in self._pools.values():
            out.extend(pool.cold)
        return out

    def all_ghosts(self) -> list:
        """Phase 2.0: 聚合所有 user 的幽灵池。"""
        out: list = []
        for pool in self._pools.values():
            out.extend(pool.ghosts)
        return out

    def user_ids(self) -> list:
        """Phase 2.0: 列出所有有数据的 user_id。"""
        return [uid for uid, pool in self._pools.items()
                if pool.buffer or pool.warm or pool.cold or pool.ghosts]

    # ═══ 旧 API (shim → <global> 池, 保持向后兼容) ═══

    def add(
        self,
        text: str,
        raw_weight: float,
        phi: float,
        tags: list,
        source_user: str,
    ):
        """旧 API: shim 到 <global> 池。"""
        return self.add_for_user(
            GLOBAL_USER_ID, text, raw_weight, phi, tags, source_user,
        )

    def update_phi(self, current_phi: float) -> None:
        """旧 API: shim 到 <global> 池。"""
        self.update_phi_for_user(GLOBAL_USER_ID, current_phi)

    def confirm_check(self) -> list:
        """旧 API: shim 到 <global> 池。"""
        return self.confirm_check_for_user(GLOBAL_USER_ID)

    def consolidate(self) -> list:
        """旧 API: shim 到 <global> 池。"""
        return self.consolidate_for_user(GLOBAL_USER_ID)

    def recall(self, keyword: str, max_results: int = 5) -> list:
        """旧 API: shim 到 <global> 池。"""
        return self.recall_for_user(GLOBAL_USER_ID, keyword, max_results)

    def sample_for_mode_a(self, minutes: int = 60) -> list:
        """旧 API: shim 到 <global> 池。"""
        pool = self._get_pool(GLOBAL_USER_ID)
        cutoff = time.time() - minutes * 60
        return [e for e in pool.buffer if e.created_at > cutoff]

    def sample_for_mode_b(self, k: int = 3) -> list:
        """旧 API: shim 到 <global> 池。"""
        pool = self._get_pool(GLOBAL_USER_ID)
        if not pool.buffer:
            return []
        now = time.time()
        scored = [
            (e, e.raw_weight * math.exp(-(now - e.created_at) / 3600))
            for e in pool.buffer
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [e for e, _ in scored[:k]]

    # ═══ 内部 helper (per-user) ═══

    def _promote_to_warm_for_user(self, user_id: str, entry) -> MemoryEntry:
        pool = self._get_pool(user_id)
        warm_entry = MemoryEntry(
            id=entry.id.replace("buf_", "mem_"),
            text=entry.text,
            emotional_weight=entry.confirmed_weight,
            phi_at_creation=entry.phi_at_creation,
            tags=list(entry.tags),
            source_user=entry.source_user,
            privacy=entry.privacy,
            entities=dict(entry.entities),
        )
        pool.warm.append(warm_entry)
        self._build_index_for_user(user_id, warm_entry)
        return warm_entry

    def _promote_to_cold_for_user(self, user_id: str, entry) -> MemoryEntry:
        pool = self._get_pool(user_id)
        cold_entry = MemoryEntry(
            id=entry.id.replace("buf_", "cold_"),
            text=entry.text,
            emotional_weight=entry.confirmed_weight,
            phi_at_creation=entry.phi_at_creation,
            tags=list(entry.tags),
            source_user=entry.source_user,
            tier="cold",
            privacy=entry.privacy,
            entities=dict(entry.entities),
        )
        pool.cold.append(cold_entry)
        self._build_index_for_user(user_id, cold_entry)
        return cold_entry

    def _form_ghost_for_user(self, user_id: str, entry) -> MemoryEntry:
        pool = self._get_pool(user_id)
        ghost = MemoryEntry(
            id=entry.id.replace("buf_", "ghost_"),
            text=entry.text,
            emotional_weight=entry.raw_weight,
            phi_at_creation=entry.phi_at_creation,
            tags=list(entry.tags),
            source_user=entry.source_user,
            tier="ghost",
            is_ghost=True,
            privacy=entry.privacy,
            entities=dict(entry.entities),
        )
        pool.ghosts.append(ghost)
        ghost_max = int(MEMORY_POOL_CONFIG["ghost_max"])
        if len(pool.ghosts) > ghost_max:
            pool.ghosts = pool.ghosts[-ghost_max:]
        return ghost

    def _build_index_for_user(self, user_id: str, entry: MemoryEntry) -> None:
        pool = self._get_pool(user_id)
        for tag in entry.tags:
            pool._tag_index.setdefault(tag, []).append(entry)
        for word in entry.text.split():
            pool._text_index.setdefault(word, []).append(entry)

    # ═══ 序列化 (Phase 2.0: per-user) ═══

    def to_dict(self) -> dict:
        """Phase 2.0: 序列化所有 per-user 池子。
        旧数据 (无 user_id 字段) 视为 <global> 用户。
        """
        pools_data: dict = {}
        for user_id, pool in self._pools.items():
            pools_data[user_id] = {
                "buffer": [e.to_dict() for e in pool.buffer],
                "warm": [e.to_dict() for e in pool.warm],
                "cold": [e.to_dict() for e in pool.cold],
                "ghosts": [e.to_dict() for e in pool.ghosts],
                "next_id": pool._next_id,
            }
        return {"pools": pools_data}

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryPool":
        """Phase 2.0: 反序列化支持新旧两种格式。"""
        pool = cls()
        # 新格式: pools dict
        if "pools" in data:
            for user_id, pdata in data["pools"].items():
                user_pool = pool._get_pool(user_id)
                user_pool._next_id = pdata.get("next_id", 0)
                for e in pdata.get("buffer", []):
                    user_pool.buffer.append(BufferEntry.from_dict(e))
                for e in pdata.get("warm", []):
                    user_pool.warm.append(MemoryEntry.from_dict(e))
                for e in pdata.get("cold", []):
                    user_pool.cold.append(MemoryEntry.from_dict(e))
                for e in pdata.get("ghosts", []):
                    user_pool.ghosts.append(MemoryEntry.from_dict(e))
                for entry in user_pool.warm + user_pool.cold + user_pool.ghosts:
                    pool._build_index_for_user(user_id, entry)
        else:
            # 旧格式: buffer/warm/cold/ghosts 顶层 → 视为 <global> 池
            global_pool = pool._get_pool(GLOBAL_USER_ID)
            global_pool._next_id = data.get("next_id", 0)
            for e in data.get("buffer", []):
                global_pool.buffer.append(BufferEntry.from_dict(e))
            for e in data.get("warm", []):
                global_pool.warm.append(MemoryEntry.from_dict(e))
            for e in data.get("cold", []):
                global_pool.cold.append(MemoryEntry.from_dict(e))
            for e in data.get("ghosts", []):
                global_pool.ghosts.append(MemoryEntry.from_dict(e))
            for entry in global_pool.warm + global_pool.cold + global_pool.ghosts:
                pool._build_index_for_user(GLOBAL_USER_ID, entry)
        return pool
