#!/bin/bash
# Install the agent-chat terminal UI and the model host tools for this checkout.
#
# Creates a repo-local virtual environment, installs the pinned tool
# dependencies (Anthropic SDK, Textual), installs this package into it, and
# links `agent-chat` into ~/.local/bin so one command opens the roster.
# Run from a long-lived checkout, not a worktree. Re-running is safe.
#
# Usage: deploy/install-agent-chat.sh [--python /path/to/python3] [--bin-dir DIR]
set -euo pipefail

fail() { printf 'error: %s\n' "$*" >&2; exit 2; }

PYTHON="" BIN_DIR="$HOME/.local/bin"
while [ $# -gt 0 ]; do
  case "$1" in
    --python) PYTHON="${2:-}"; shift 2 ;;
    --bin-dir) BIN_DIR="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$ROOT/pyproject.toml" ] || fail "no pyproject.toml under $ROOT"
[ -f "$ROOT/requirements-tui.lock" ] || fail "requirements-tui.lock missing"
[ -z "$PYTHON" ] && PYTHON="$(command -v python3 || true)"
[ -x "$PYTHON" ] || fail "python3 not found; pass --python"

cd "$ROOT"
[ -x .venv/bin/python ] || "$PYTHON" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements-tui.lock
.venv/bin/pip install -q -e . --no-deps
[ -x .venv/bin/agent-chat ] || fail "agent-chat entry point was not installed"

mkdir -p "$BIN_DIR"
ln -sf "$ROOT/.venv/bin/agent-chat" "$BIN_DIR/agent-chat"
printf 'installed agent-chat -> %s/agent-chat\n' "$BIN_DIR"
printf 'python for host profiles: %s/.venv/bin/python\n' "$ROOT"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) printf 'add %s to your PATH, e.g. in ~/.zshrc:  export PATH="%s:$PATH"\n' "$BIN_DIR" "$BIN_DIR" ;;
esac
printf 'open the roster with: agent-chat   (or agent-chat --agent lumen)\n'
