"""缓冲池信号 — 从 memory_pool 的缓冲池计算 6 维信号。

供 sentinel / diary / drift / mode_b 消费。
纯计算，不修改缓冲池状态。

Phase 2.0 (Step 2): per-user 读路径
- 构造接受 user_id (默认 "<global>"), 实例方法只读该 user 的 buffer
- 聚合类方法 BufferSignals.aggregate_* 跨用户读 (供跨用户场景)
- confirmation_history / recent_expired 仍为实例级 (per-instance)
"""

from __future__ import annotations

import math
import time
from typing import Any, TYPE_CHECKING

from .memory_pool import GLOBAL_USER_ID

from .registry import register

if TYPE_CHECKING:
    from .memory_pool import MemoryPool, BufferEntry


@register(name="buffer_signals", provides=["BufferSignals"], depends_on=["memory_pool"])
class BufferSignals:
    """缓冲池信号计算器 (Phase 2.0: per-user 读路径)。"""

    def __init__(self, pool: MemoryPool, user_id: str = GLOBAL_USER_ID) -> None:
        self._pool = pool
        self._user_id = user_id  # Phase 2.0: 该实例绑定到哪个 user
        self._confirmation_history: list[dict[str, Any]] = []
        self._recent_expired: list[dict[str, Any]] = []
        self._timeout_count_7d = 0
        self._total_entries_7d = 0

    def _buffer(self) -> list:
        """Phase 2.0: 返回 user_id 对应池的 buffer 引用。"""
        return self._pool.buffer_for(self._user_id)

    def record_confirmation(self, entry_id: str, dwell_seconds: float, confirmed: bool, tags: list[str]) -> None:
        """记录确认/超时事件。"""
        self._confirmation_history.append({
            "entry_id": entry_id,
            "dwell_seconds": dwell_seconds,
            "confirmed": confirmed,
            "tags": tags,
            "confirmed_at": time.time(),
        })
        self._total_entries_7d += 1
        if not confirmed:
            self._timeout_count_7d += 1
        # 保留最近 200 条
        if len(self._confirmation_history) > 200:
            self._confirmation_history = self._confirmation_history[-200:]

    def record_expired(self, entry_id: str, tags: list[str]) -> None:
        """记录超时条目。"""
        self._recent_expired.append({
            "entry_id": entry_id,
            "tags": tags,
            "expired_at": time.time(),
        })
        if len(self._recent_expired) > 50:
            self._recent_expired = self._recent_expired[-50:]

    def emotional_momentum(self) -> dict[str, Any]:
        """情感动量: 方向 + 强度。"""
        buffer = self._buffer()
        if len(buffer) < 3:
            return {"direction": "stable", "strength": 0.0, "avg_weight": 0.0}

        sorted_entries = sorted(buffer, key=lambda e: e.created_at)
        mid = len(sorted_entries) // 2
        early_avg = sum(e.raw_weight for e in sorted_entries[:mid]) / mid
        late_avg = sum(e.raw_weight for e in sorted_entries[mid:]) / (len(sorted_entries) - mid)

        if early_avg < 0.01:
            direction = "stable"
            strength = 0.0
        elif late_avg > early_avg * 1.2:
            direction = "escalating"
            strength = min(1.0, (late_avg - early_avg) / early_avg)
        elif late_avg < early_avg * 0.8:
            direction = "cooling"
            strength = min(1.0, (early_avg - late_avg) / early_avg)
        else:
            direction = "stable"
            strength = abs(late_avg - early_avg) / max(early_avg, 0.01)

        return {
            "direction": direction,
            "strength": round(strength, 4),
            "avg_weight": round(sum(e.raw_weight for e in sorted_entries) / len(sorted_entries), 4),
        }

    def confirmation_velocity(self) -> float:
        """确认速度: [0, 1], 高=快速消化, 低=消化困难。"""
        recent = [h for h in self._confirmation_history if h["confirmed_at"] > time.time() - 7 * 86400]
        if not recent:
            return 0.5  # 默认中等

        confirmed = [h for h in recent if h["confirmed"]]
        if not confirmed:
            return 0.0

        avg_dwell = sum(h["dwell_seconds"] for h in confirmed) / len(confirmed)
        velocity = max(0.0, 1.0 - avg_dwell / 86400)

        timeout_rate = self._timeout_count_7d / max(1, self._total_entries_7d)
        velocity *= (1 - timeout_rate)

        return round(max(0.0, velocity), 4)

    def buffer_temperature(self) -> float:
        """缓冲池温度: [0, 1], 高=大量未处理情感堆积。"""
        buffer = self._buffer()
        if not buffer:
            return 0.0

        total_intensity = sum(e.raw_weight for e in buffer)
        capacity_pressure = len(buffer) / max(1, 30)  # max=30

        return round(min(1.0, total_intensity * 0.5 + capacity_pressure * 0.5), 4)

    def echo_patterns(self) -> list[dict[str, Any]]:
        """回声模式: 同一标签反复出现但未确认。"""
        tag_counts: dict[str, int] = {}
        tag_buffer: dict[str, int] = {}
        tag_expired: dict[str, int] = {}

        for entry in self._buffer():
            for tag in entry.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                tag_buffer[tag] = tag_buffer.get(tag, 0) + 1

        for entry in self._recent_expired:
            for tag in entry["tags"]:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                tag_expired[tag] = tag_expired.get(tag, 0) + 1

        echoes = []
        for tag, count in tag_counts.items():
            if count >= 3:
                echoes.append({
                    "tag": tag,
                    "count": count,
                    "in_buffer": tag_buffer.get(tag, 0),
                    "expired": tag_expired.get(tag, 0),
                })

        return echoes

    def confirmation_bias(self) -> dict[str, float]:
        """确认偏差: 每个标签的确认率。"""
        confirmed_tags: dict[str, int] = {}
        dropped_tags: dict[str, int] = {}

        for entry in self._confirmation_history[-100:]:
            for tag in entry["tags"]:
                if entry["confirmed"]:
                    confirmed_tags[tag] = confirmed_tags.get(tag, 0) + 1
                else:
                    dropped_tags[tag] = dropped_tags.get(tag, 0) + 1

        all_tags = set(confirmed_tags) | set(dropped_tags)
        bias = {}
        for tag in all_tags:
            c = confirmed_tags.get(tag, 0)
            d = dropped_tags.get(tag, 0)
            total = c + d
            if total >= 3:
                bias[tag] = round(c / total, 4)

        return bias

    def mode_b_strategy(self) -> str:
        """Mode B 采样策略。"""
        temp = self.buffer_temperature()
        momentum = self.emotional_momentum()
        velocity = self.confirmation_velocity()

        if temp > 0.7:
            return "cathartic"
        elif momentum["direction"] == "escalating":
            return "narrative"
        elif velocity < 0.3:
            return "integrative"
        elif len(self._buffer()) < 5:
            return "exploratory"
        else:
            return "balanced"

    # ═══ 聚合类方法 (Phase 2.0: 跨用户读, 供跨用户场景) ═══

    @classmethod
    def aggregate_temperature(cls, pool: MemoryPool) -> float:
        """跨用户聚合温度: 统计所有 user 的 buffer 总量。

        容量压力用绝对阈值 30 (而非 per-user * user_count), 反映"全局未处理堆积"。
        """
        all_buffer = pool.all_buffer()
        if not all_buffer:
            return 0.0
        total_intensity = sum(e.raw_weight for e in all_buffer)
        capacity_pressure = len(all_buffer) / max(1, 30)  # 全局容量 30
        return round(min(1.0, total_intensity * 0.5 + capacity_pressure * 0.5), 4)

    @classmethod
    def aggregate_echo_patterns(cls, pool: MemoryPool) -> list[dict[str, Any]]:
        """跨用户聚合回声模式: 所有 user 的 buffer + 合并 echo。"""
        tag_counts: dict[str, int] = {}
        tag_buffer: dict[str, int] = {}

        for entry in pool.all_buffer():
            for tag in entry.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                tag_buffer[tag] = tag_buffer.get(tag, 0) + 1

        echoes = []
        for tag, count in tag_counts.items():
            if count >= 3:
                echoes.append({
                    "tag": tag,
                    "count": count,
                    "in_buffer": tag_buffer.get(tag, 0),
                    "expired": 0,  # 聚合视图不含 expired (需实例 history)
                })
        return echoes

    def to_dict(self) -> dict[str, Any]:
        return {
            "confirmation_history": self._confirmation_history[-100:],
            "recent_expired": self._recent_expired[-30:],
            "timeout_count_7d": self._timeout_count_7d,
            "total_entries_7d": self._total_entries_7d,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        self._confirmation_history = data.get("confirmation_history", [])
        self._recent_expired = data.get("recent_expired", [])
        self._timeout_count_7d = data.get("timeout_count_7d", 0)
        self._total_entries_7d = data.get("total_entries_7d", 0)
