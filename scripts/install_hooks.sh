#!/usr/bin/env bash
# install_hooks.sh - Install git hooks from scripts/ into .git/hooks/
#
# Usage: ./scripts/install_hooks.sh
#   - Copies scripts/pre-commit (if exists) to .git/hooks/pre-commit
#   - Sets executable bit
#   - Verifies Python availability
#
# Idempotent: re-running is safe (overwrites existing hook).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOKS_SRC="$SCRIPT_DIR/hooks"
HOOKS_DST="$REPO_ROOT/.git/hooks"

if [ ! -d "$HOOKS_SRC" ]; then
    echo "ERROR: hooks source directory not found: $HOOKS_SRC" >&2
    echo "       Did you delete scripts/hooks/?" >&2
    exit 1
fi

if [ ! -d "$HOOKS_DST" ]; then
    echo "ERROR: .git/hooks/ not found. Is this a git repo?" >&2
    exit 1
fi

# Check Python availability
# Prefer the same Python interpreter that ran this script (more reliable than PATH lookup,
# especially on Windows where `python3` may resolve to a Microsoft Store stub).
PYTHON_CMD=""
if [ -n "${PYTHON:-}" ]; then
    PYTHON_CMD="$PYTHON"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=$(command -v python3)
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD=$(command -v python)
else
    echo "ERROR: Python not found in PATH. Pre-commit hook requires Python." >&2
    exit 1
fi

# Verify the Python actually works (the WindowsApps stub for python3 will fail this)
if ! "$PYTHON_CMD" -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
    echo "ERROR: Python interpreter at $PYTHON_CMD is not functional." >&2
    echo "       (On Windows, 'python3' may resolve to a Microsoft Store stub.)" >&2
    echo "       Try setting PYTHON env var to a working interpreter, e.g.:" >&2
    echo "         PYTHON=/c/Python311/python.exe $0" >&2
    exit 1
fi

echo "Using Python: $PYTHON_CMD"

# Install each hook
installed=0
for hook_file in "$HOOKS_SRC"/*; do
    [ -f "$hook_file" ] || continue
    hook_name="$(basename "$hook_file")"
    # Skip README, .sample, .swp, etc.
    case "$hook_name" in
        *.sample|*.swp|*.bak|README*) continue ;;
    esac
    dst="$HOOKS_DST/$hook_name"
    cp "$hook_file" "$dst"
    chmod +x "$dst"
    echo "  installed: $hook_name"
    installed=$((installed + 1))
done

if [ "$installed" -eq 0 ]; then
    echo "No hook files found in $HOOKS_SRC"
    exit 0
fi

echo ""
echo "✓ Installed $installed git hook(s) into .git/hooks/"
echo ""
# Test instructions (in a comment block so the pre-commit hook's own secret
# scanner doesn't flag the example token pattern as a real secret).
cat <<'TEST_INSTRUCTIONS'
Test the hook:
  1. Create a file with a fake GitHub-style token
     echo '{"k": "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}' > /tmp/test.json
  2. Stage and try to commit
     git add /tmp/test.json
     git commit -m "test"   # should be BLOCKED with "GitHub personal access token" error
  3. Clean up: rm /tmp/test.json && git restore --staged /tmp/test.json

To uninstall, simply delete the hook file:
  rm .git/hooks/pre-commit
TEST_INSTRUCTIONS
