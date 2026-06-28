"""Sync two repository copies (plugin runtime vs source) to detect drift.

The plugin lives in two physical locations:
  - PLUGIN_DIR: D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit/
    runtime copy, no git, loaded by the live AstrBot process.
  - SOURCE_DIR: this directory (with .git/), the source of truth, where
    commits land.

Both must stay byte-identical on the WHITELIST files, otherwise the
runtime bot runs stale code relative to what's committed (or vice versa).

Two directions supported:
  --direction=plugin-to-source  (default)
      Compare PLUGIN_DIR against SOURCE_DIR. Drift = something was edited
      in the runtime copy and never propagated to git. --apply copies
      PLUGIN_DIR → SOURCE_DIR.

  --direction=source-to-plugin
      Compare SOURCE_DIR against PLUGIN_DIR. Drift = code was committed
      here but the live bot hasn't been refreshed. --apply copies
      SOURCE_DIR → PLUGIN_DIR.

Default mode is dry-run — prints drift and exits non-zero if any.
With --apply, copies drifted files and reports what was synced.

Whitelist lives in WHITELIST below — add new files there as the project
grows to keep both copies aligned on exactly the same set of artifacts.
Tests that are ONLY in source end (not loaded at runtime) stay out.
"""

import argparse
import difflib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Hardcoded paths per plan §T5 — adapt if you move either copy.
PLUGIN_DIR = Path("D:/astrbot/data/plugins/astrbot_plugin_emotion_spirit")
SOURCE_DIR = ROOT

# Runtime-affecting files that must stay byte-identical between both copies.
# Add new entries here as the surface area grows; tests stay out unless they
# affect runtime (e.g. tests/migrations/ follows the migration rule it tests).
WHITELIST = [
    "main.py",
    "README.md",
    "_conf_schema.json",
    "emotion_spirit/output/commands.py",
    "emotion_spirit/output/diary_writer.py",
    "emotion_spirit/migrations/rules/v3_0_to_v3_1.py",
    "tests/migrations/__init__.py",
    "tests/migrations/test_split_llm_tier.py",
]


def _diff_lines(from_path: Path, to_path: Path) -> list[str]:
    """Return unified-diff lines between two files. Empty list = identical.

    Missing files on either side are reported as drift via a sentinel line.
    """
    if not from_path.exists():
        return [f"<<< MISSING: {from_path}\n"]
    if not to_path.exists():
        return [f">>> MISSING: {to_path}\n"]
    from_lines = from_path.read_text(encoding="utf-8").splitlines(keepends=True)
    to_lines = to_path.read_text(encoding="utf-8").splitlines(keepends=True)
    if from_lines == to_lines:
        return []
    return list(difflib.unified_diff(
        from_lines, to_lines,
        fromfile=str(from_path), tofile=str(to_path),
    ))


def check_drift(direction: str) -> tuple[int, list[tuple[str, Path, Path, list[str]]]]:
    """Return (drift_count, [(relpath, from_path, to_path, diff_lines), ...])."""
    if direction == "plugin-to-source":
        from_dir, to_dir = PLUGIN_DIR, SOURCE_DIR
    elif direction == "source-to-plugin":
        from_dir, to_dir = SOURCE_DIR, PLUGIN_DIR
    else:
        raise ValueError(f"unknown direction: {direction}")

    drifted: list[tuple[str, Path, Path, list[str]]] = []
    for relpath in WHITELIST:
        from_path = from_dir / relpath
        to_path = to_dir / relpath
        diff = _diff_lines(from_path, to_path)
        if diff:
            drifted.append((relpath, from_path, to_path, diff))
    return len(drifted), drifted


def apply_sync(direction: str) -> int:
    """Copy drifted files in the given direction. Returns number synced."""
    drift_count, drifted = check_drift(direction)
    if drift_count == 0:
        print(f"All files in sync ({direction})")
        return 0

    for relpath, from_path, to_path, _diff in drifted:
        shutil.copy2(from_path, to_path)
        print(f"  ✓ copied {relpath}  ({from_path} -> {to_path})")
    return drift_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect (and optionally fix) drift between plugin runtime and source.",
    )
    parser.add_argument(
        "--direction",
        choices=["plugin-to-source", "source-to-plugin"],
        default="plugin-to-source",
        help="sync direction (default: plugin-to-source)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually copy drifted files (default: dry-run, exit non-zero on drift)",
    )
    args = parser.parse_args()

    from_dir = PLUGIN_DIR if args.direction == "plugin-to-source" else SOURCE_DIR
    to_dir = SOURCE_DIR if args.direction == "plugin-to-source" else PLUGIN_DIR

    print(f"Direction: {args.direction}")
    print(f"From:      {from_dir}")
    print(f"To:        {to_dir}")
    print(f"Whitelist: {len(WHITELIST)} files")
    print()

    if args.apply:
        count = apply_sync(args.direction)
        if count == 0:
            return 0
        print(f"\nSynced {count} files.")
        return 0

    drift_count, drifted = check_drift(args.direction)
    if drift_count == 0:
        print("All files in sync.")
        return 0

    print(f"DRIFT DETECTED on {drift_count} files:")
    for relpath, from_path, to_path, diff in drifted:
        print(f"\n--- {relpath} ---")
        print(f"  from: {from_path}")
        print(f"  to:   {to_path}")
        print(f"  diff lines: {len(diff)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())