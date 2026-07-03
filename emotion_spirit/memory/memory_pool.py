"""四层记忆池管理器 (flat 存储 + participant 过滤)。

缓冲池: 待确认的事件记忆 (温度自然衰减)
温池: 已确认的有意义事件
冷池: 模式沉淀 (标签化、可检索)
幽灵: 永久情感痕迹

Phase D: UnifiedEntry 统一, Φ 门控移除, flat 存储 + participant 过滤。
Phase D+: 记忆崩溃系统集成 (CollapseArchetype 驱动)。
"""

from __future__ import annotations

import math
import time
from typing import Any

from astrbot.api import logger
from ..core.config import BUFFER_POOL_CONFIG, MEMORY_POOL_CONFIG
from ..core.utils import clamp
from .unified_entry import UnifiedEntry
from ..utils import DecayModel
from .cascade_engine import CascadeEngine


GLOBAL_USER_ID = "<global>"

__all__ = [
    "GLOBAL_USER_ID",
    "UnifiedEntry",
    "MemoryPool",
    "_tokenize",
]


def _tokenize(text: str) -> list[str]:
    """Tokenize text: whitespace tokens + sliding 2-gram for CJK / dense text."""
    tokens = text.split()
    for i in range(len(text) - 1):
        gram = text[i : i + 2]
        if not gram.isspace():
            tokens.append(gram)
    return tokens


from ..core.registry import register


@register(name="memory_pool", provides=["MemoryPool"], depends_on=[])
class MemoryPool:
    """四层记忆池管理器 — flat 存储 + participant 过滤。"""

    def __init__(self) -> None:
        # flat 四层列表
        self.buffer: list[UnifiedEntry] = []
        self.warm: list[UnifiedEntry] = []
        self.cold: list[UnifiedEntry] = []
        self.ghosts: list[UnifiedEntry] = []
        # 全局索引
        self._tag_index: dict[str, list[UnifiedEntry]] = {}
        self._text_index: dict[str, list[UnifiedEntry]] = {}
        self._next_id: int = 0
        # CompositeIndex: O(1) entry lookup by ID
        self._entries: dict[str, UnifiedEntry] = {}
        # all_entries cache
        self._all_entries_cache: list[UnifiedEntry] | None = None
        self._dirty: bool = True
        # 向量 + 级联
        self._vector_index: dict[str, tuple[float, float, float]] = {}
        self._cascade_engine = CascadeEngine()
        self._decay = DecayModel()
        self._cascade_active: bool = False
        self._last_tick: float = time.time()
        # 崩溃系统
        self._collapse_active: bool = False
        self._collapse_archetype: str | None = None
        # 语义嵌入 (optional, external embedding function)
        self._embedding = None

    # ═══ 写入 API ═══

    def add(
        self,
        text: str,
        raw_weight: float,
        phi: float,
        tags: list,
        source_user: str,
        participants: set[str] | None = None,
        privacy: str = "private",
        entities: dict | None = None,
    ) -> UnifiedEntry:
        """添加到缓冲池。自动设置 participants = {source_user, <global>} (如未指定)。"""
        if participants is None:
            participants = {source_user, GLOBAL_USER_ID}
        entry = UnifiedEntry(
            id=f"buf_{self._next_id}",
            text=text,
            tags=list(tags),
            entities=entities or {},
            source_user=source_user,
            privacy=privacy,
            created_at=time.time(),
            temperature=min(1.0, raw_weight),
            emotional_weight=raw_weight,
            mass=0.5,
            tier="buffer",
            is_ghost=False,
            recall_count=0,
            last_recalled=0.0,
            peak_temperature=min(1.0, raw_weight),
            participants=participants,
        )
        self._next_id += 1
        self.buffer.append(entry)
        self._build_index(entry)
        self._dirty = True

        # 直通幽灵
        bypass_ghost_w = BUFFER_POOL_CONFIG["bypass_ghost_weight"]
        if raw_weight > bypass_ghost_w and any(t in tags for t in ["betrayal", "collapse"]):
            self._form_ghost(entry)
            return entry

        # 直通冷池
        bypass_cold_w = BUFFER_POOL_CONFIG["bypass_cold_weight"]
        if raw_weight > bypass_cold_w:
            self._promote_to_cold(entry)
            return entry

        # 缓冲池容量限制
        max_buf = int(BUFFER_POOL_CONFIG["max"])
        if len(self.buffer) > max_buf:
            self.buffer.sort(key=lambda e: e.created_at)
            overflow = self.buffer.pop(0)
            if overflow.emotional_weight > MEMORY_POOL_CONFIG.get("recall_boost", 0.05):
                self._promote_to_warm(overflow)

        return entry

    # 兼容旧签名 (surface_handler 调用)
    def add_for_user(self, user_id: str, text: str, raw_weight: float, phi: float,
                     tags: list, source_user: str, privacy: str = "private",
                     entities: dict | None = None) -> UnifiedEntry:
        return self.add(text, raw_weight, phi, tags, source_user,
                        participants={user_id}, privacy=privacy, entities=entities)

    def confirm_check(self) -> list:
        """全局温度门控确认。崩溃期间暂停。"""
        if self._collapse_active:
            return []  # 崩溃期间不确认
        noise_threshold = BUFFER_POOL_CONFIG["noise_threshold"]
        ttl_seconds = BUFFER_POOL_CONFIG["ttl_hours"] * 3600
        now = time.time()
        still_buffer: list = []
        promoted: list = []
        for entry in self.buffer:
            age = now - entry.created_at
            if entry.temperature < noise_threshold or age > ttl_seconds:
                self._entries.pop(entry.id, None)  # clean O(1) index
            elif entry.temperature >= 0.5:
                promoted.append(self._promote_to_warm(entry))
            else:
                still_buffer.append(entry)
        self.buffer = still_buffer
        self._dirty = True
        return promoted

    # 兼容旧签名
    def confirm_check_for_user(self, user_id: str) -> list:
        return self.confirm_check()

    def consolidate(self) -> list:
        """全局 warm → cold 流转。"""
        now = time.time()
        warm_ttl = MEMORY_POOL_CONFIG["warm_to_cold_ttl_hours"] * 3600
        consolidated: list = []
        still_warm: list = []
        for entry in self.warm:
            if now - entry.created_at > warm_ttl:
                entry.tier = "cold"
                self.cold.append(entry)
                self._build_index(entry)
                consolidated.append(entry)
            else:
                still_warm.append(entry)
        self.warm = still_warm
        self._dirty = True
        cold_max = int(MEMORY_POOL_CONFIG["cold_max"])
        if len(self.cold) > cold_max:
            self.cold.sort(key=lambda e: e.emotional_weight * (1 + e.recall_count * 0.05))
            self.cold = self.cold[-cold_max:]
        return consolidated

    # 兼容旧签名
    def consolidate_for_user(self, user_id: str) -> list:
        return self.consolidate()

    def recall(
        self,
        keyword: str,
        current_user: str | None = None,
        max_results: int = 5,
        privacy_filter: list | None = None,
    ) -> list:
        """倒排索引召回。按 participant 过滤 (如指定 current_user)。"""
        seen_ids: set = set()
        candidates: list = []
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
        # participant 过滤
        if current_user is not None:
            candidates = [e for e in candidates if current_user in e.participants]
        # privacy 过滤
        if privacy_filter:
            candidates = [e for e in candidates if e.privacy in privacy_filter]
        results = sorted(candidates, key=lambda e: e.emotional_weight, reverse=True)
        boost = MEMORY_POOL_CONFIG["recall_boost"]
        for entry in results[:max_results]:
            entry.last_recalled = time.time()
            entry.recall_count += 1
            entry.emotional_weight = min(1.0, entry.emotional_weight + boost)
        return results[:max_results]

    # 兼容旧签名
    def recall_for_user(self, user_id: str, keyword: str, max_results: int = 5,
                        privacy_filter: list | None = None) -> list:
        return self.recall(keyword, current_user=user_id, max_results=max_results,
                           privacy_filter=privacy_filter)

    # ═══ 语义召回 + 重巩固 ═══

    def configure_embedding(self, embedding_fn) -> None:
        """Configure external embedding function for semantic recall.

        Args:
            embedding_fn: async callable(text: str) -> list[float]
        """
        self._embedding = embedding_fn

    async def recall_semantic(
        self,
        query_text: str,
        k: int = 5,
        current_user: str | None = None,
    ) -> list:
        """Semantic recall via embedding vector search.

        Falls back to keyword recall if no embedding function configured.
        Returns list of UnifiedEntry objects (not tuples).
        """
        if self._embedding is None:
            return self.recall(query_text, current_user=current_user, max_results=k)

        query_vec = await self._embedding(query_text)
        # search_by_vector returns [(entry_id, distance), ...]
        id_dist_pairs = self.search_by_vector(
            tuple(query_vec), top_k=k, user_id=current_user,
        )
        results = []
        for entry_id, _dist in id_dist_pairs:
            entry = self._find_entry_by_id(entry_id)
            if entry is not None:
                results.append(entry)
        # Apply recall boost to returned entries
        boost = MEMORY_POOL_CONFIG["recall_boost"]
        for entry in results:
            entry.last_recalled = time.time()
            entry.recall_count += 1
            entry.emotional_weight = min(1.0, entry.emotional_weight + boost)
        return results

    def reconsolidate(
        self,
        entry: UnifiedEntry,
        current_mood: dict,
        personality: dict,
    ) -> None:
        """Rewrite memory based on current mood (Bower 1981 mood-congruency).

        Same-valence mood → reinforce memory (mood-congruent strengthening).
        Opposite mood + high boundary_permeability → twist memory (false memory effect).
        """
        mood_valence = current_mood.get("valence", 0.0)
        permeability = personality.get("boundary_permeability", 0.5)

        # Mood-congruent: reinforce when mood and memory share valence sign
        if (mood_valence > 0 and entry.emotional_weight > 0) or \
           (mood_valence < 0 and entry.emotional_weight < 0):
            entry.emotional_weight = min(1.0, entry.emotional_weight + 0.05)
        # False memory: twist when opposite mood + high permeability
        elif permeability > 0.7 and abs(mood_valence) > 0.3:
            twist = permeability * abs(mood_valence) * 0.3
            entry.emotional_weight += twist * (-1 if entry.emotional_weight > 0 else 1)
            entry.emotional_weight = max(-1.0, min(1.0, entry.emotional_weight))

        entry.recall_count += 1
        entry.last_recalled = time.time()

    # ═══ Participant 过滤视图 ═══

    def buffer_in(self, user_id: str) -> list[UnifiedEntry]:
        return [e for e in self.buffer if user_id in e.participants]

    def warm_in(self, user_id: str) -> list[UnifiedEntry]:
        return [e for e in self.warm if user_id in e.participants]

    def cold_in(self, user_id: str) -> list[UnifiedEntry]:
        return [e for e in self.cold if user_id in e.participants]

    def ghosts_in(self, user_id: str) -> list[UnifiedEntry]:
        return [e for e in self.ghosts if user_id in e.participants]

    # 兼容旧签名
    def buffer_for(self, user_id: str) -> list[UnifiedEntry]:
        return self.buffer_in(user_id)

    def warm_for(self, user_id: str) -> list[UnifiedEntry]:
        return self.warm_in(user_id)

    def cold_for(self, user_id: str) -> list[UnifiedEntry]:
        return self.cold_in(user_id)

    def ghosts_for(self, user_id: str) -> list[UnifiedEntry]:
        return self.ghosts_in(user_id)

    # ═══ 聚合视图 (直接返回) ═══

    def all_buffer(self) -> list[UnifiedEntry]:
        return self.buffer

    def all_warm(self) -> list[UnifiedEntry]:
        return self.warm

    def all_cold(self) -> list[UnifiedEntry]:
        return self.cold

    def all_ghosts(self) -> list[UnifiedEntry]:
        return self.ghosts

    def all_entries(self) -> list[UnifiedEntry]:
        if self._dirty or self._all_entries_cache is None:
            self._all_entries_cache = self.buffer + self.warm + self.cold + self.ghosts
            self._dirty = False
        return self._all_entries_cache

    def get_layer(self, tier: str) -> list[UnifiedEntry]:
        return getattr(self, tier, [])

    def user_ids(self) -> list[str]:
        ids: set[str] = set()
        for e in self.all_entries():
            ids.update(e.participants)
        return list(ids)

    # ═══ 旧 API 兼容 ═══

    def sample_for_mode_a(self, minutes: int = 60) -> list:
        cutoff = time.time() - minutes * 60
        return [e for e in self.buffer if e.created_at > cutoff]

    def sample_for_mode_b(self, k: int = 3) -> list:
        if not self.buffer:
            return []
        now = time.time()
        scored = [(e, e.emotional_weight * math.exp(-(now - e.created_at) / 3600))
                  for e in self.buffer]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [e for e, _ in scored[:k]]

    # ═══ 崩溃系统 ═══

    def check_collapse(self, personality: dict[str, float] | None = None) -> bool:
        """检测记忆崩溃状态。返回是否处于崩溃中。

        触发条件:
        - buffer 中 emotional_weight > 0.8 的条目 ≥ 3
        - 或 cascade_active 且 hot entries ≥ 5

        解除条件: buffer 温度均值 < 0.3
        """
        if self._collapse_active:
            # 检查解除
            buf_temps = [e.temperature for e in self.buffer]
            avg_temp = sum(buf_temps) / len(buf_temps) if buf_temps else 0.0
            if avg_temp < 0.3:
                self._collapse_active = False
                self._collapse_archetype = None
                logger.info("emotion_spirit: 记忆崩溃解除 (avg_temp=%.2f)", avg_temp)
            return self._collapse_active

        # 检查触发
        heavy_count = sum(1 for e in self.buffer if e.emotional_weight > 0.8)
        hot_count = sum(1 for e in self.all_entries() if e.temperature > 0.9)

        triggered = heavy_count >= 3 or (self._cascade_active and hot_count >= 5)
        if triggered:
            self._collapse_active = True
            if personality is not None:
                from .collapse_archetype import CollapseArchetypeSelector
                selector = CollapseArchetypeSelector()
                archetype = selector.select(personality)
                self._collapse_archetype = archetype.value
            logger.warning(
                "emotion_spirit: 记忆崩溃触发 (heavy=%d, hot=%d, archetype=%s)",
                heavy_count, hot_count, self._collapse_archetype,
            )
        return self._collapse_active

    # ═══ 向量搜索 ═══

    def search_by_vector(
        self,
        query_vec: tuple[float, float, float],
        top_k: int = 5,
        tier: str | None = None,
        user_id: str | None = None,
    ) -> list[tuple[str, float]]:
        results: list[tuple[str, float]] = []
        for entry_id, vec in self._vector_index.items():
            if tier is not None or user_id is not None:
                entry = self._find_entry_by_id(entry_id)
                if entry is None:
                    continue
                if tier is not None and entry.tier != tier:
                    continue
                if user_id is not None and user_id not in entry.participants:
                    continue
            dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(vec, query_vec)))
            results.append((entry_id, dist))
        results.sort(key=lambda x: x[1])
        return results[:top_k]

    def update_vector(self, entry_id: str, new_vec: tuple[float, float, float]) -> None:
        entry = self._find_entry_by_id(entry_id)
        if entry is not None:
            entry.vector = new_vec
            self._vector_index[entry_id] = new_vec

    def _find_entry_by_id(self, entry_id: str) -> UnifiedEntry | None:
        return self._entries.get(entry_id)

    # ═══ Tick / Decay ═══

    def tick(self, personality: dict[str, float] | None = None,
            partner_intimacy: float = 0.0) -> None:
        """推进一个 tick: 情境衰减 + 层流转 + 幽灵形成 + 级联检查。"""
        now = time.time()
        elapsed = now - self._last_tick
        for entry in self.buffer + self.warm + self.cold:
            if entry.is_ghost:
                continue
            # 情境衰减因子 (人格 + 关系 + 情感权重)
            ctx_factor = entry.compute_decay_factor(partner_intimacy, personality)
            # 崩溃期间额外加速
            collapse_mult = 1.5 if self._collapse_active else 1.0
            entry.temperature = self._decay.thermal_decay(
                elapsed_seconds=elapsed * ctx_factor * collapse_mult,
                initial_temp=entry.temperature,
                mass=entry.mass,
                is_ghost=entry.is_ghost,
            )
            age_hours = (now - entry.created_at) / 3600.0
            old_weight = entry.emotional_weight
            entry.emotional_weight = self._decay.memory_retention(
                elapsed_hours=age_hours * ctx_factor,
                initial_weight=entry.emotional_weight,
            )
            if entry.emotional_weight != old_weight:
                entry.recompute_vector()
                self._vector_index[entry.id] = entry.vector
        self._check_transitions()
        self._check_ghost_formation()
        self._update_cascade_state()
        self._last_tick = now

    # ═══ 层流转 ═══

    def _check_transitions(self) -> None:
        now = time.time()
        # buffer → warm
        still_buffer: list = []
        for entry in self.buffer:
            result = self._check_buffer_to_warm(entry, now)
            if result == "keep":
                still_buffer.append(entry)
        self.buffer = still_buffer
        # warm → cold
        still_warm: list = []
        for entry in self.warm:
            if not self._check_warm_to_cold(entry, now):
                still_warm.append(entry)
        self.warm = still_warm
        # cold 淘汰
        still_cold: list = []
        for entry in self.cold:
            if not self._check_cold_evict(entry):
                still_cold.append(entry)
        self.cold = still_cold
        self._dirty = True
        cold_max = 500
        if len(self.cold) > cold_max:
            self.cold.sort(key=lambda e: e.emotional_weight)
            for victim in self.cold[:len(self.cold) - cold_max]:
                self._remove_entry(victim)
            self.cold = self.cold[-cold_max:]

    def _check_buffer_to_warm(self, entry: UnifiedEntry, now: float) -> str:
        age_hours = (now - entry.created_at) / 3600.0
        if age_hours >= 48:
            self._remove_entry(entry)
            return "removed"
        if entry.temperature < 0.5 and entry.emotional_weight > 0.05:
            self._promote_to_warm(entry)
            return "promoted"
        return "keep"

    def _check_warm_to_cold(self, entry: UnifiedEntry, now: float) -> bool:
        age_hours = (now - entry.created_at) / 3600.0
        if (entry.temperature < 0.2 and entry.emotional_weight < 0.2) or age_hours > 72:
            self._promote_to_cold(entry)
            return True
        return False

    def _check_cold_evict(self, entry: UnifiedEntry) -> bool:
        if entry.emotional_weight < 0.05:
            self._remove_entry(entry)
            return True
        return False

    def _check_ghost_formation(self) -> None:
        # 崩溃期间降低幽灵形成阈值
        temp_th = 0.7 if self._collapse_active else 0.9
        weight_th = 0.6 if self._collapse_active else 0.8
        for entry in self.all_entries():
            if entry.is_ghost:
                continue
            if entry.temperature > temp_th and entry.emotional_weight > weight_th:
                entry._ticks_above_ghost_threshold += 1
            else:
                entry._ticks_above_ghost_threshold = 0
            if entry._ticks_above_ghost_threshold >= 10:
                self._form_ghost(entry)

    def _update_cascade_state(self) -> None:
        hot_entries = [e for e in self.all_entries() if e.temperature > 0.9]
        if hot_entries and not self._cascade_active:
            self._cascade_active = True
            hot_entries.sort(key=lambda e: e.temperature, reverse=True)
            self._cascade_engine.propagate_cascade(
                source=hot_entries[0], sensitivity=0.5,
                entries_lookup={e.id: e for e in self.all_entries()},
            )
        elif not hot_entries:
            self._cascade_active = False

    # ═══ 内部 helper ═══

    def _promote_to_warm(self, entry: UnifiedEntry) -> UnifiedEntry:
        old_id = entry.id
        old_tags, old_text = list(entry.tags), entry.text
        entry.id = entry.id.replace("buf_", "mem_")
        if old_id != entry.id:
            self._clean_entry_index(old_id, old_tags, old_text)
        entry.tier = "warm"
        self.warm.append(entry)
        self._dirty = True
        self._build_index(entry)
        return entry

    def _promote_to_cold(self, entry: UnifiedEntry) -> UnifiedEntry:
        old_id = entry.id
        old_tags, old_text = list(entry.tags), entry.text
        entry.id = entry.id.replace("buf_", "cold_")
        if old_id != entry.id:
            self._clean_entry_index(old_id, old_tags, old_text)
        entry.tier = "cold"
        self.cold.append(entry)
        self._dirty = True
        self._build_index(entry)
        return entry

    def _form_ghost(self, entry: UnifiedEntry) -> UnifiedEntry:
        old_id = entry.id
        old_tags, old_text = list(entry.tags), entry.text
        entry.id = entry.id.replace("buf_", "ghost_")
        if old_id != entry.id:
            self._clean_entry_index(old_id, old_tags, old_text)
        entry.tier = "ghost"
        entry.is_ghost = True
        self.ghosts.append(entry)
        self._dirty = True
        self._build_index(entry)
        ghost_max = int(MEMORY_POOL_CONFIG["ghost_max"])
        if len(self.ghosts) > ghost_max:
            evicted = self.ghosts[:-ghost_max]
            self.ghosts = self.ghosts[-ghost_max:]
            for victim in evicted:
                self._remove_entry(victim)
        return entry

    def _clean_entry_index(self, entry_id: str, tags: list, text: str) -> None:
        """Remove stale index entries for a given ID (before re-indexing with a new ID)."""
        self._entries.pop(entry_id, None)
        self._vector_index.pop(entry_id, None)
        for tag in tags:
            if tag in self._tag_index:
                self._tag_index[tag] = [e for e in self._tag_index[tag] if e.id != entry_id]
                if not self._tag_index[tag]:
                    del self._tag_index[tag]
        for word in _tokenize(text):
            if word in self._text_index:
                self._text_index[word] = [e for e in self._text_index[word] if e.id != entry_id]
                if not self._text_index[word]:
                    del self._text_index[word]

    def _build_index(self, entry: UnifiedEntry) -> None:
        for tag in entry.tags:
            self._tag_index.setdefault(tag, []).append(entry)
        for word in _tokenize(entry.text):
            self._text_index.setdefault(word, []).append(entry)
        self._entries[entry.id] = entry
        self._vector_index[entry.id] = entry.vector
        self._cascade_engine.index_entry(entry)

    def _remove_entry(self, entry: UnifiedEntry) -> None:
        self._entries.pop(entry.id, None)
        self._dirty = True
        for tier_list in (self.buffer, self.warm, self.cold, self.ghosts):
            if entry in tier_list:
                tier_list.remove(entry)
        for tag in entry.tags:
            if tag in self._tag_index:
                self._tag_index[tag] = [e for e in self._tag_index[tag] if e.id != entry.id]
                if not self._tag_index[tag]:
                    del self._tag_index[tag]
        for word in _tokenize(entry.text):
            if word in self._text_index:
                self._text_index[word] = [e for e in self._text_index[word] if e.id != entry.id]
                if not self._text_index[word]:
                    del self._text_index[word]
        self._vector_index.pop(entry.id, None)
        self._cascade_engine.remove_entry(entry)

    # ═══ 信号注入 ═══

    def inject_signal(self, entry_id: str, signal_type: str, intensity: float) -> None:
        entry = self._find_entry_by_id(entry_id)
        if entry is not None:
            entry.on_inject(signal_type, intensity)

    def recall_entry(self, entry_id: str, personality: dict[str, float]) -> None:
        entry = self._find_entry_by_id(entry_id)
        if entry is not None:
            entry.on_recall(personality)

    def feed_body(self, body_state: dict[str, float]) -> None:
        entries = self.all_entries()
        if not entries:
            return
        arousal = body_state.get("arousal", 0.5)
        shift = (arousal - 0.5) * 0.1
        for entry in entries:
            entry.temperature = clamp(entry.temperature + shift, 0.0, 1.0)

    def mean_temperature(self) -> float:
        entries = self.all_entries()
        if not entries:
            return 0.0
        return sum(e.temperature for e in entries) / len(entries)

    def count_hot(self, threshold: float) -> int:
        return sum(1 for e in self.all_entries() if e.temperature > threshold)

    def cascade_active(self) -> bool:
        return self._cascade_active

    # ═══ 序列化 ═══

    def get_collapse_archetype(self) -> str | None:
        """当前 collapse archetype (公开访问, 替代直接读 _collapse_archetype 私有, v1.2.8)."""
        return self._collapse_archetype

    def to_dict(self) -> dict:
        return {
            "buffer": [e.to_dict() for e in self.buffer],
            "warm": [e.to_dict() for e in self.warm],
            "cold": [e.to_dict() for e in self.cold],
            "ghosts": [e.to_dict() for e in self.ghosts],
            "next_id": self._next_id,
            "cascade_active": self._cascade_active,
            "last_tick": self._last_tick,
            "collapse_active": self._collapse_active,
            "collapse_archetype": self._collapse_archetype,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryPool":
        pool = cls()
        pool._next_id = data.get("next_id", 0)
        pool._cascade_active = data.get("cascade_active", False)
        pool._last_tick = data.get("last_tick", time.time())
        pool._collapse_active = data.get("collapse_active", False)
        pool._collapse_archetype = data.get("collapse_archetype", None)

        # 兼容旧 per-user 格式 {"pools": {uid: {...}}}
        if "pools" in data:
            for uid, pdata in data["pools"].items():
                pool._next_id = max(pool._next_id, pdata.get("next_id", 0))
                for tier_name in ("buffer", "warm", "cold", "ghosts"):
                    for e in pdata.get(tier_name, []):
                        entry = UnifiedEntry.from_dict(e)
                        # 迁移: 确保 participants 非空
                        if not entry.participants:
                            entry.participants = {uid}
                        getattr(pool, tier_name).append(entry)
        else:
            for tier_name in ("buffer", "warm", "cold", "ghosts"):
                for e in data.get(tier_name, []):
                    entry = UnifiedEntry.from_dict(e)
                    if not entry.participants:
                        entry.participants = {entry.source_user} if entry.source_user else set()
                    getattr(pool, tier_name).append(entry)

        for entry in pool.all_entries():
            pool._build_index(entry)
        return pool
