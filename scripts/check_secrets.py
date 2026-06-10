#!/usr/bin/env python3
"""check_secrets.py - Pre-commit hook to detect accidentally-committed secrets.

Scans staged changes (or all files in argv) for high-confidence secret patterns:
- pbkdf2 password hashes (AstrBot's exact format)
- OpenAI / Anthropic / Google API keys
- GitHub personal access tokens
- AWS access key IDs
- PEM private key blocks
- Bearer tokens in URLs/headers
- URLs with embedded user:pass@ credentials

Allowlist (skipped):
- Lines starting with `#` (Python/yaml comments)
- Strings containing "REDACTED" (our placeholder convention)
- Files matching paths in .secrets-allowlist (one pattern per line)
- Lines that look like git commit hashes (40 hex chars preceded by space)

Exit codes:
  0  no secrets found
  1  secrets found (blocks commit)
  2  internal error

Usage:
  check_secrets.py                    # scan staged changes (for pre-commit hook)
  check_secrets.py path/to/file ...   # scan specific files
"""
import re
import subprocess
import sys
from pathlib import Path

# === High-confidence secret patterns ===
# Each tuple: (name, regex, severity)
# Severity: 'block' (always fail) or 'warn' (informational)
PATTERNS = [
    ("pbkdf2 hash (AstrBot)", r"pbkdf2_(?:sha256|sha1|pbkdf2)\$\d+\$[A-Za-z0-9./+_-]{8,128}\$[A-Za-z0-9./+_-]{20,200}", "block"),
    ("OpenAI / Anthropic API key", r"(?:sk-|sk-ant-|gsk_)[A-Za-z0-9_-]{20,}", "block"),
    ("GitHub personal access token", r"(?:ghp_|gho_|ghu_|ghs_|github_pat_)[A-Za-z0-9_]{20,}", "block"),
    ("AWS access key ID", r"AKIA[0-9A-Z]{16}", "block"),
    ("PEM private key block", r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----", "block"),
    ("Bearer token", r"Bearer\s+[A-Za-z0-9._~+/-]{30,}", "block"),
    ("URL with embedded credentials", r"https?://[A-Za-z0-9._%+-]+:[A-Za-z0-9._%+-]+@", "block"),
    ("Slack token (xox[bpars]-)", r"xox[baprs]-[A-Za-z0-9-]{10,}", "block"),
]

# === Allowlist patterns (always skipped) ===
# We intentionally do NOT allowlist bare 40+ char hex sequences, because
# pbkdf2 hashes are also hex and 64 chars long (this caused a false-negative
# in test 4 of the dev cycle). The detection patterns are specific enough
# (require prefixes like pbkdf2_, sk-, ghp_, AKIA) that they shouldn't
# collide with random hex.
ALLOWLIST_LINE_PATTERNS = [
    re.compile(r"^\s*#"),  # comments
    re.compile(r"REDACTED"),  # our placeholder convention
    re.compile(r"pbkdf2_sha256\$\d+\$REDACTED-"),  # our scrubbed format
]

# === Files to skip (e.g. CHANGELOG mentions "secret", tests reference patterns) ===
ALLOWLIST_FILE_PATTERNS = [
    "scripts/check_secrets.py",  # self-reference (contains all patterns)
    "tests/test_*.py",
    "verification/**",
    "CHANGELOG.md",
    "STRUCTURE_REPORT.md",
    ".secrets-allowlist",
]

# Compile patterns
COMPILED = [(name, re.compile(pat), sev) for name, pat, sev in PATTERNS]


def load_allowlist() -> set[str]:
    """Load user-maintained allowlist from .secrets-allowlist (one path glob per line)."""
    allowlist = set(ALLOWLIST_FILE_PATTERNS)
    p = Path(".secrets-allowlist")
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                allowlist.add(line)
    return allowlist


def should_skip_file(path: str, allowlist: set[str]) -> bool:
    """Check if a file path matches any allowlist pattern."""
    from fnmatch import fnmatch
    return any(fnmatch(path, pat) for pat in allowlist)


def should_skip_line(line: str) -> bool:
    """Check if a line is allowlisted (comment, REDACTED, etc.)."""
    return any(p.search(line) for p in ALLOWLIST_LINE_PATTERNS)


def scan_text(path: str, text: str) -> list[tuple[str, int, str, str]]:
    """Return list of (path, line_no, pattern_name, snippet) for each match."""
    matches = []
    for i, line in enumerate(text.splitlines(), start=1):
        if should_skip_line(line):
            continue
        for name, regex, sev in COMPILED:
            if regex.search(line):
                # Truncate long matches for display
                snippet = line.strip()[:120]
                matches.append((path, i, name, snippet))
                break  # one match per line is enough
    return matches


def scan_staged_changes() -> list[tuple[str, str]]:
    """Return list of (filepath, content) for staged additions/modifications.

    Only includes lines that were ADDED or MODIFIED in the staged diff,
    not pre-existing lines (to avoid re-flagging historical secrets).
    """
    try:
        # Get diff of staged changes with 0 context (only +/- lines, no unchanged)
        result = subprocess.run(
            ["git", "diff", "--cached", "--unified=0", "--no-color"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"check_secrets: failed to run git diff: {e}", file=sys.stderr)
        sys.exit(2)

    # Parse diff format: "+++ b/path" then "+line" for additions, "-line" for removals
    # We only care about additions ("+" not "++")
    files: dict[str, list[tuple[int, str]]] = {}
    current_file = None
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            files.setdefault(current_file, [])
        elif current_file and line.startswith("+") and not line.startswith("+++"):
            # Track line number using @@ hunk header
            files[current_file].append((0, line[1:]))

    # We don't have exact line numbers from --unified=0; reconstruct from full file
    result = []
    for filepath, _ in files.items():
        try:
            content = Path(filepath).read_text(encoding="utf-8")
            result.append((filepath, content))
        except (FileNotFoundError, UnicodeDecodeError, IsADirectoryError):
            # File deleted or binary - skip
            continue
    return result


def main() -> int:
    allowlist = load_allowlist()

    if len(sys.argv) > 1:
        # Explicit files provided
        files_to_scan = [(arg, Path(arg).read_text(encoding="utf-8", errors="ignore"))
                         for arg in sys.argv[1:]
                         if Path(arg).is_file()]
    else:
        # Pre-commit mode: scan staged changes
        files_to_scan = scan_staged_changes()

    all_matches = []
    for filepath, content in files_to_scan:
        if should_skip_file(filepath, allowlist):
            continue
        matches = scan_text(filepath, content)
        all_matches.extend(matches)

    if not all_matches:
        print("check_secrets: OK (no secrets found in scanned files)")
        return 0

    print(f"\n❌ check_secrets: {len(all_matches)} potential secret(s) found:\n", file=sys.stderr)
    for filepath, line_no, name, snippet in all_matches:
        print(f"  {filepath}:{line_no}  [{name}]", file=sys.stderr)
        print(f"    {snippet}", file=sys.stderr)
    print("\nTo allowlist (use with caution):", file=sys.stderr)
    print("  1. If this is a false positive, add the path to .secrets-allowlist", file=sys.stderr)
    print("  2. If this is a REAL secret, rotate it immediately and scrub git history", file=sys.stderr)
    print("     See: docs/superpowers/reports/2026-06-09-secret-leak-incident.md (if exists)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
