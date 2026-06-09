"""JSON 持久化 — 跨会话数据存储 (v2 schema + 4 NS typed accessor)。

Phase C (P3-5): 4 个 typed NS class + per-namespace dirty 跟踪。
向后兼容: 旧 store.get(key) / store.set(key, val) 通用 API 仍可用。
        旧 update_pad_history / get_pad_history / periodic_save 也保留。

数据存储在 AstrBot 的 data/plugin_data/emotion_spirit/ 目录下，
而非插件自身目录，遵循 AstrBot 插件开发规范。

v1.2 schema v2: +pad_history / +pad_trajectory 命名空间。
v2.0 schema v3: +memory_pools (per-user) + social_graph 命名空间。
Phase C: 4 个 NS 提升为 typed accessor, per-NS dirty 跟踪。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from astrbot.api import logger

from .registry import register


_STORE_FILE = "spirit_data.json"
_CURRENT_SCHEMA_VERSION = 3

# 4 个 NS 的 key 集合 (跟 _data 顶层其他 legacy key 区分)
_NS_KEYS = ("pad_history", "pad_trajectory", "memory_pools", "social_graph")


# ═══ 4 个 typed NS class ═══



__all__ = [
    "PadHistoryNS",
    "PadTrajectoryNS",
    "MemoryPoolsNS",
    "SocialGraphNS",
    "SpiritStore",
]

class PadHistoryNS:
    """per-session PAD 历史 (v1.2 引入)。

    内部存储: {session_id: [v, a, d, t]}
    """

    def __init__(self, data: dict):
        self._data = data
        self._dirty = False

    def update(self, session_id: str, last: list | tuple) -> None:
        """更新 session 的 last PAD。"""
        self._data[session_id] = list(last)
        self._dirty = True

    def get(self, session_id: str) -> list | None:
        return self._data.get(session_id)

    def is_dirty(self) -> bool:
        return self._dirty

    def clear_dirty(self) -> None:
        self._dirty = False

    def to_dict(self) -> dict:
        return dict(self._data)


class PadTrajectoryNS:
    """per-session PAD 轨迹 (v1.2 引入, v1.7 trajectory 高级 API)。

    内部存储: {session_id: [[v, a, d, t], ...]}
    """

    def __init__(self, data: dict):
        self._data = data
        self._dirty = False

    def append(self, session_id: str, point: list | tuple) -> None:
        if session_id not in self._data:
            self._data[session_id] = []
        self._data[session_id].append(list(point))
        self._dirty = True

    def set(self, session_id: str, trajectory: list) -> None:
        """整体替换 trajectory (deque → list of lists)。"""
        self._data[session_id] = [list(p) for p in trajectory]
        self._dirty = True

    def get(self, session_id: str) -> list:
        return self._data.get(session_id, [])

    def is_dirty(self) -> bool:
        return self._dirty

    def clear_dirty(self) -> None:
        self._dirty = False

    def to_dict(self) -> dict:
        return dict(self._data)


class MemoryPoolsNS:
    """per-user 记忆池 (v2.0 引入)。

    内部存储: {"pools": {user_id: {buffer, warm, cold, ghosts, next_id}}}
    """

    def __init__(self, data: dict):
        self._data = data
        self._dirty = False

    def get(self, user_id: str) -> dict:
        """返回 per-user dict, 不存在时返回新空 dict (不创建)。"""
        pools = self._data.get("pools", {})
        return pools.get(user_id, {})

    def set(self, user_id: str, pool_data: dict) -> None:
        if "pools" not in self._data:
            self._data["pools"] = {}
        self._data["pools"][user_id] = pool_data
        self._dirty = True

    def is_dirty(self) -> bool:
        return self._dirty

    def clear_dirty(self) -> None:
        self._dirty = False

    def to_dict(self) -> dict:
        return dict(self._data)


class SocialGraphNS:
    """社交图 (有向边) (v2.0 引入)。

    内部存储: {"edges": {key: edge_dict}, "user_index": ..., "topics": ...}
    """

    def __init__(self, data: dict):
        self._data = data
        self._dirty = False

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        relation_type: str = "friend",
        trust: float = 0.5,
    ) -> None:
        if "edges" not in self._data:
            self._data["edges"] = {}
        key = f"{from_id}->{to_id}"
        self._data["edges"][key] = {"relation_type": relation_type, "trust": trust}
        self._dirty = True

    def get_edge(self, from_id: str, to_id: str) -> dict | None:
        edges = self._data.get("edges", {})
        key = f"{from_id}->{to_id}"
        return edges.get(key)

    def is_dirty(self) -> bool:
        return self._dirty

    def clear_dirty(self) -> None:
        self._dirty = False

    def to_dict(self) -> dict:
        return dict(self._data)


# ═══ SpiritStore 主类 ═══


@register(name="store", provides=["SpiritStore"], depends_on=[], config_keys={"data_dir"})
class SpiritStore:
    """JSON 持久化存储 — 4 NS typed accessor + 旧通用 API (向后兼容)。

    数据布局 (Phase C):
    - self._data: 顶层 flat dict, 包含 legacy keys (memory_pool, intimacy, ...)
      + 4 NS sub-keys (pad_history, pad_trajectory, memory_pools, social_graph)
    - self.pad_history / pad_trajectory / memory_pools / social_graph:
      4 NS typed accessor, 共享 self._data 中对应 sub-dict 的引用

    文件布局 (save/load):
    {
      "schema_version": 3,
      "saved_at": <float>,
      "data": {legacy keys},
      "pad_history": {...},
      "pad_trajectory": {...},
      "memory_pools": {...},
      "social_graph": {...}
    }

    跟 SylannEngine 的 AlphaRuntime 一致:
    - 原子写入 (先写 .tmp 再 os.replace)
    - dirty flag 避免不必要写入
    """

    def __init__(self, data_dir: str | Path) -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _STORE_FILE
        self._data: dict[str, Any] = {}
        self._dirty = False
        self._last_save_time: float = time.time()

        # 创建 4 NS typed accessor (共享 sub-dict 引用, _rebind_ns 内 setdefault)
        self._rebind_ns()

        # 自动迁移老数据
        self.load()

    def _rebind_ns(self) -> None:
        """把 4 NS wrapper 重新绑定到 self._data 的 sub-dict (共享引用)。

        用于:
        1. __init__ 初次创建
        2. load() 加载老 flat dict 后, 重新指向 self._data 中的 NS sub-dict
        """
        # 确保 4 NS sub-dict 存在 (用于老数据没有这些 key 的情况)
        self._data.setdefault("pad_history", {})
        self._data.setdefault("pad_trajectory", {})
        self._data.setdefault("memory_pools", {"pools": {}})
        self._data.setdefault(
            "social_graph",
            {"edges": {}, "user_index": {}, "topics": {}},
        )
        self.pad_history = PadHistoryNS(self._data["pad_history"])
        self.pad_trajectory = PadTrajectoryNS(self._data["pad_trajectory"])
        self.memory_pools = MemoryPoolsNS(self._data["memory_pools"])
        self.social_graph = SocialGraphNS(self._data["social_graph"])

    # ═══ 旧通用 API (向后兼容) ═══

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._dirty = True

    # ═══ 旧命名空间 API (向后兼容, 委托给 NS) ═══

    def update_pad_history(
        self, session_id: str, last: tuple[float, float, float, float]
    ) -> None:
        """更新 session 的 last PAD (v, a, d, t) — 委托给 PadHistoryNS。"""
        self.pad_history.update(session_id, last)

    def update_pad_trajectory(self, session_id: str, trajectory: list) -> None:
        """更新 session 的 trajectory — 委托给 PadTrajectoryNS。"""
        self.pad_trajectory.set(session_id, trajectory)

    def get_pad_history(self, session_id: str) -> list | None:
        """获取 session 的 last PAD — 委托给 PadHistoryNS。"""
        return self.pad_history.get(session_id)

    def get_pad_trajectory(self, session_id: str) -> list:
        """获取 session 的 trajectory — 委托给 PadTrajectoryNS。"""
        return self.pad_trajectory.get(session_id)

    # ═══ 持久化 ═══

    @property
    def is_dirty(self) -> bool:
        """整体 dirty: 通用 set 或 4 NS 任一 dirty 都算脏。"""
        return (
            self._dirty
            or self.pad_history.is_dirty()
            or self.pad_trajectory.is_dirty()
            or self.memory_pools.is_dirty()
            or self.social_graph.is_dirty()
        )

    def save(self) -> None:
        if not self.is_dirty:
            return
        self._atomic_write()

    def _atomic_write(self) -> None:
        """原子写入（拆出来供 periodic_save 复用）。

        文件结构: {schema_version, saved_at, data: {legacy}, pad_history, pad_trajectory, memory_pools, social_graph}
        """
        try:
            # 拆分 legacy keys vs 4 NS keys
            legacy_data = {
                k: v for k, v in self._data.items() if k not in _NS_KEYS
            }
            payload = {
                "schema_version": _CURRENT_SCHEMA_VERSION,
                "saved_at": time.time(),
                "data": legacy_data,
                "pad_history": self.pad_history.to_dict(),
                "pad_trajectory": self.pad_trajectory.to_dict(),
                "memory_pools": self.memory_pools.to_dict(),
                "social_graph": self.social_graph.to_dict(),
            }
            tmp = self._path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
            self._dirty = False
            self._last_save_time = time.time()
            # 清空 4 NS dirty
            self.pad_history.clear_dirty()
            self.pad_trajectory.clear_dirty()
            self.memory_pools.clear_dirty()
            self.social_graph.clear_dirty()
        except OSError:
            logger.warning("emotion_spirit: Failed to save spirit data", exc_info=True)

    def periodic_save(self) -> None:
        """5 min 定时写。仅在 dirty 时写。"""
        if self.is_dirty:
            self._atomic_write()

    def load(self) -> None:
        """从 JSON 加载 (兼容 v3 schema, 老数据自动迁移)。

        文件结构: {data: {legacy}, pad_history, pad_trajectory, memory_pools, social_graph}
        在内存中扁平化为 self._data 顶层 dict (4 NS sub-key 也在内)。
        """
        if not self._path.exists():
            self._migrate_to_v2()
            self._migrate_to_v3()
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            # 区分 v3 结构化 (data + 4 NS) vs 老 flat dict
            if isinstance(payload, dict) and ("pad_history" in payload or "data" in payload):
                # v3 结构化: 拆 legacy + 4 NS
                legacy = payload.get("data", {})
                # 更新 legacy keys (in-place, 保留 NS 引用)
                for k, v in legacy.items():
                    self._data[k] = v
                # 删除 _data 中属于 legacy 但文件里没有的 key
                for k in list(self._data.keys()):
                    if k in _NS_KEYS:
                        continue
                    if k not in legacy:
                        del self._data[k]
                # 更新 4 NS sub-dict (in-place, NS wrapper 引用不变)
                for ns_key in _NS_KEYS:
                    if ns_key in payload:
                        ns_dict = self._data[ns_key]
                        ns_dict.clear()
                        ns_dict.update(payload[ns_key])
            else:
                # 老 flat dict (v2 schema 之前) — 整体替换, NS 重新链接
                self._data = dict(payload)
                # 重新建立 NS 引用
                self._rebind_ns()
            self._dirty = False
            # 清空 4 NS dirty
            self.pad_history.clear_dirty()
            self.pad_trajectory.clear_dirty()
            self.memory_pools.clear_dirty()
            self.social_graph.clear_dirty()
            # 老数据补字段
            self._migrate_to_v2()
            self._migrate_to_v3()
        except (json.JSONDecodeError, OSError):
            logger.warning("emotion_spirit: Failed to load spirit data", exc_info=True)
            self._data = {}
            self._migrate_to_v2()
            self._migrate_to_v3()

    def _migrate_to_v2(self) -> None:
        """v1.2: 老数据补 pad_history / pad_trajectory 字段。

        只在键确实缺失时补，且不强制写盘（避免空 store 被标 dirty）。
        """
        if "pad_history" not in self._data:
            self._data["pad_history"] = {}
        if "pad_trajectory" not in self._data:
            self._data["pad_trajectory"] = {}

    def _migrate_to_v3(self) -> None:
        """v2.0 (Step 5): 迁移到 v3 schema。

        主要变化:
        1. memory_pool (单 key) → memory_pools (per-user dict)
        2. 初始化 social_graph 命名空间 (Step 6 完整实现)
        """
        # 1. 迁移 memory_pool → memory_pools
        if "memory_pool" in self._data and (
            "memory_pools" not in self._data
            or not self._data.get("memory_pools")
        ):
            old_pool = self._data.pop("memory_pool")
            # 旧 v2 格式: 顶层 buffer/warm/cold/ghosts → 视为 <global> 池
            if "buffer" in old_pool or "warm" in old_pool:
                memory_pools = {
                    "pools": {
                        "<global>": {
                            "buffer": old_pool.get("buffer", []),
                            "warm": old_pool.get("warm", []),
                            "cold": old_pool.get("cold", []),
                            "ghosts": old_pool.get("ghosts", []),
                            "next_id": old_pool.get("next_id", 0),
                        }
                    }
                }
            else:
                # 已经是 v2 嵌套格式 (有 pools 键)
                memory_pools = old_pool
            self._data["memory_pools"] = memory_pools
            self._dirty = True
            logger.info("emotion_spirit: schema v2→v3, memory_pool → memory_pools migrated")

        if "memory_pools" not in self._data:
            self._data["memory_pools"] = {"pools": {}}

        # 2. 初始化 social_graph 命名空间
        if "social_graph" not in self._data:
            self._data["social_graph"] = {
                "edges": {},       # {src: {dst: edge_dict}}
                "user_index": {},  # {user_id: {trust, last_active}}
                "topics": {},      # 未来: 话题-隐私映射
            }
            logger.info("emotion_spirit: schema v2→v3, social_graph namespace initialized")
