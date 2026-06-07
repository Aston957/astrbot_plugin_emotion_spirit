"""JSON 持久化 — 跨会话数据存储 (dirty flag + 原子写入)。

数据存储在 AstrBot 的 data/plugin_data/emotion_spirit/ 目录下，
而非插件自身目录，遵循 AstrBot 插件开发规范。

v1.2 schema v2: +pad_history / +pad_trajectory 命名空间。
v2.0 schema v3: +memory_pools (per-user) + social_graph 命名空间。
老数据自动迁移（schema_version 2 → 3）。
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


@register(name="store", provides=["SpiritStore"], depends_on=[])
class SpiritStore:
    """JSON 持久化存储。

    和 SylannEngine 的 AlphaRuntime 一致:
    - 原子写入 (先写 .tmp 再 os.replace)
    - dirty flag 避免不必要写入

    v1.2: 加 pad_history / pad_trajectory 命名空间 + periodic_save()
    v2.0 (Step 5): +memory_pools (per-user) + social_graph 命名空间
    """

    def __init__(self, data_dir: str | Path) -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {}
        self._path = self._dir / _STORE_FILE
        self._dirty = False
        self._last_save_time: float = time.time()
        self.load()  # 自动迁移老数据

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return
        self._atomic_write()

    def _atomic_write(self) -> None:
        """v1.2: 原子写入（拆出来供 periodic_save 复用）。"""
        try:
            tmp = self._path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
            self._dirty = False
            self._last_save_time = time.time()
        except OSError:
            logger.warning("emotion_spirit: Failed to save spirit data", exc_info=True)

    def periodic_save(self) -> None:
        """v1.2: 5 min 定时写。仅在 dirty 时写。

        由 caller (main.py) 控制调用频率（例如每 5 min 调一次）。
        """
        if self._dirty:
            self._atomic_write()

    def load(self) -> None:
        if not self._path.exists():
            self._migrate_to_v2()
            self._migrate_to_v3()
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            self._dirty = False
            self._migrate_to_v2()  # 老数据补 v2 字段
            self._migrate_to_v3()  # 老数据补 v3 字段
        except (json.JSONDecodeError, OSError):
            logger.warning("emotion_spirit: Failed to load spirit data", exc_info=True)
            self._data = {}
            self._migrate_to_v2()
            self._migrate_to_v3()

    def _migrate_to_v2(self) -> None:
        """v1.2: 老数据补 pad_history / pad_trajectory 字段。

        只在键确实缺失时补，且不强制写盘（避免空 store 被标 dirty）。
        真正需要写盘的场景（老数据迁移）由调用方 save() 触发。
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
        3. schema_version → 3
        """
        # 1. 迁移 memory_pool → memory_pools
        if "memory_pool" in self._data and "memory_pools" not in self._data:
            old_pool = self._data.pop("memory_pool")
            # 旧 v2 格式: 顶层 buffer/warm/cold/ghosts → 视为 <global> 池
            if "buffer" in old_pool or "warm" in old_pool:
                # 旧 v2 格式 (顶层) → 包装为 <global> 池
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
            # 注意: 补默认值不算"脏", 避免空 store 被标 dirty
            logger.info("emotion_spirit: schema v2→v3, social_graph namespace initialized")

        # 3. schema_version
        self._data["schema_version"] = 3

    # === v1.2: pad_history / pad_trajectory 命名空间 API ===

    def update_pad_history(
        self, session_id: str, last: tuple[float, float, float, float]
    ) -> None:
        """更新 session 的 last PAD (v, a, d, t)。"""
        self._data.setdefault("pad_history", {})
        self._data["pad_history"][session_id] = list(last)
        self._dirty = True

    def update_pad_trajectory(self, session_id: str, trajectory: list) -> None:
        """更新 session 的 trajectory（deque → list of lists）。"""
        self._data.setdefault("pad_trajectory", {})
        self._data["pad_trajectory"][session_id] = [list(p) for p in trajectory]
        self._dirty = True

    def get_pad_history(self, session_id: str) -> list | None:
        """获取 session 的 last PAD，缺失返回 None。"""
        return self._data.get("pad_history", {}).get(session_id)

    def get_pad_trajectory(self, session_id: str) -> list:
        """获取 session 的 trajectory，缺失返回 []。"""
        return self._data.get("pad_trajectory", {}).get(session_id, [])

    @property
    def is_dirty(self) -> bool:
        return self._dirty
