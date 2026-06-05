"""JSON 持久化 — 跨会话数据存储 (dirty flag + 原子写入)。

数据存储在 AstrBot 的 data/plugin_data/emotion_spirit/ 目录下，
而非插件自身目录，遵循 AstrBot 插件开发规范。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from astrbot.api import logger


_STORE_FILE = "spirit_data.json"


class SpiritStore:
    """JSON 持久化存储。

    和 SylannEngine 的 AlphaRuntime 一致:
    - 原子写入 (先写 .tmp 再 os.replace)
    - dirty flag 避免不必要写入
    """

    def __init__(self, data_dir: str | Path) -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {}
        self._path = self._dir / _STORE_FILE
        self._dirty = False

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return
        try:
            tmp = self._path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
            self._dirty = False
        except OSError:
            logger.warning("emotion_spirit: Failed to save spirit data", exc_info=True)

    def load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            self._dirty = False
        except (json.JSONDecodeError, OSError):
            logger.warning("emotion_spirit: Failed to load spirit data", exc_info=True)
            self._data = {}

    @property
    def is_dirty(self) -> bool:
        return self._dirty
