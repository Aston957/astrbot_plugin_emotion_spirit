"""Migration state — persists applied/error records to data/migrations.json."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MigrationState:
    """Persistent state for applied migrations and errors.

    Stored as JSON at {data_dir}/migrations.json.
    """

    def __init__(self, data_dir: Path | str):
        self._path = Path(data_dir) / "migrations.json"
        self._data: dict[str, Any] = {
            "current_version": 0,
            "applied": [],
            "errors": [],
        }

    def load_or_init(self) -> "MigrationState":
        """Load state from disk. If file missing, return fresh state with current_version=0.

        Returns self for chaining.
        """
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self._data = {
                    "current_version": loaded.get("current_version", 0),
                    "applied": loaded.get("applied", []),
                    "errors": loaded.get("errors", []),
                }
            except (json.JSONDecodeError, OSError):
                # Corrupted file → start fresh, keep corrupted as backup
                pass
        return self

    def record_applied(self, from_v: int, to_v: int, rule: str) -> None:
        """Append a successful migration to applied list."""
        self._data["applied"].append({
            "from": from_v,
            "to": to_v,
            "rule": rule,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def record_error(self, rule: str, error: str) -> None:
        """Append a failed migration to errors list."""
        self._data["errors"].append({
            "rule": rule,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def save(self) -> None:
        """Atomic write to disk (tmp + rename)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    @property
    def current_version(self) -> int:
        return self._data["current_version"]

    @current_version.setter
    def current_version(self, v: int) -> None:
        self._data["current_version"] = v

    @property
    def applied(self) -> list[dict]:
        return self._data["applied"]

    @property
    def errors(self) -> list[dict]:
        return self._data["errors"]

    def to_dict(self) -> dict:
        """Return a copy of the underlying data."""
        return {
            "current_version": self._data["current_version"],
            "applied": list(self._data["applied"]),
            "errors": list(self._data["errors"]),
        }
