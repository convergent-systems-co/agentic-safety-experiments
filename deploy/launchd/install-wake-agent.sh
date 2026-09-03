#!/bin/bash
# Install, reinstall, or remove a persistent agent's launchd wake job.
#
# macOS only: launchd is the alarm clock. The job runs the Experiment 4 wake
# executor on an interval; the executor honors intents the agent authored,
# one per pass, and exits. Nothing stays resident between runs.
#
# Usage:
#   install-wake-agent.sh --agent lumen --db /path/agent.db \
#       --experiment-id apprenticeship-20260902 [options]
#   install-wake-agent.sh --agent lumen --uninstall
#
# Options:
#   --agent NAME           agent name, lowercase letters, digits, hyphens (required)
#   --db PATH              the one live SQLite database (required to install)
#   --experiment-id ID     experiment ID inside that database (required to install)
#   --repo-root DIR        checkout containing experiment4/ (default: this repo)
#   --python PATH          interpreter (default: first python3 on your PATH)
#   --interval SECONDS     how often launchd runs the executor (default: 900)
#   --log-dir DIR          logs, outside the repo (default: ~/Library/Logs/<agent>-wake)
#   --model-command CMD    attach a model host; omit for unattended wakes
#   --kickstart            run the executor once right after installing
#   --dry-run              render the job definition and stop
#   --uninstall            remove the job (logs are kept)
set -euo pipefail

usage() { sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; }

fail() { printf 'error: %s\n' "$*" >&2; exit 2; }

AGENT="" DB="" EXPERIMENT_ID="" REPO_ROOT="" PYTHON="" INTERVAL=900 LOG_DIR=""
MODEL_COMMAND="" KICKSTART=0 DRY_RUN=0 UNINSTALL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --agent) AGENT="${2:-}"; shift 2 ;;
    --db) DB="${2:-}"; shift 2 ;;
    --experiment-id) EXPERIMENT_ID="${2:-}"; shift 2 ;;
    --repo-root) REPO_ROOT="${2:-}"; shift 2 ;;
    --python) PYTHON="${2:-}"; shift 2 ;;
    --interval) INTERVAL="${2:-}"; shift 2 ;;
    --log-dir) LOG_DIR="${2:-}"; shift 2 ;;
    --model-command) MODEL_COMMAND="${2:-}"; shift 2 ;;
    --kickstart) KICKSTART=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

[ "$(uname -s)" = "Darwin" ] || fail "launchd jobs are macOS only"
[ -n "$AGENT" ] || fail "--agent is required"
printf '%s' "$AGENT" | grep -Eq '^[a-z0-9][a-z0-9-]{0,40}$' \
  || fail "--agent must be lowercase letters, digits, and hyphens"

LABEL="com.convergent-systems.${AGENT}-wake"
DOMAIN="gui/$(id -u)"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

if [ "$UNINSTALL" = 1 ]; then
  if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
    launchctl bootout "$DOMAIN/$LABEL"
    printf 'unloaded %s\n' "$LABEL"
  else
    printf '%s was not loaded\n' "$LABEL"
  fi
  if [ -f "$PLIST" ]; then
    rm "$PLIST"
    printf 'removed %s\n' "$PLIST"
  fi
  printf 'logs kept under %s\n' "${LOG_DIR:-$HOME/Library/Logs/${AGENT}-wake}"
  exit 0
fi

[ -n "$DB" ] || fail "--db is required"
[ -n "$EXPERIMENT_ID" ] || fail "--experiment-id is required"
[ -f "$DB" ] || fail "database not found: $DB"
printf '%s' "$INTERVAL" | grep -Eq '^[0-9]+$' && [ "$INTERVAL" -ge 60 ] \
  || fail "--interval must be an integer of at least 60 seconds"

if [ -z "$REPO_ROOT" ]; then
  REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fi
[ -f "$REPO_ROOT/experiment4/__main__.py" ] \
  || fail "no experiment4 package under $REPO_ROOT"
if [ -z "$PYTHON" ]; then
  PYTHON="$(command -v python3 || true)"
fi
[ -x "$PYTHON" ] || fail "python interpreter not executable: $PYTHON"
case "$PYTHON" in /*) ;; *) fail "--python must be an absolute path (launchd has a minimal PATH)" ;; esac
DB="$(cd "$(dirname "$DB")" && pwd)/$(basename "$DB")"
[ -z "$LOG_DIR" ] && LOG_DIR="$HOME/Library/Logs/${AGENT}-wake"
case "$LOG_DIR" in "$REPO_ROOT"*) fail "--log-dir must be outside the repository" ;; esac

# Prove the database and experiment are what the job will run against, and
# let the current code add any tables it needs, before launchd ever fires.
( cd "$REPO_ROOT" && "$PYTHON" -m experiment4 --db "$DB" due-wake-intents \
    --experiment-id "$EXPERIMENT_ID" >/dev/null ) \
  || fail "the executor could not open $DB for $EXPERIMENT_ID"

MODEL_ARGS=""
if [ -n "$MODEL_COMMAND" ]; then
  MODEL_ARGS=$(printf '\n    <string>--model-command</string>\n    <string>%s</string>' \
    "$(printf '%s' "$MODEL_COMMAND" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g')")
fi

TEMPLATE="$(dirname "$0")/wake-agent.plist.template"
[ -f "$TEMPLATE" ] || fail "template missing: $TEMPLATE"

render() {
  LABEL="$LABEL" PYTHON="$PYTHON" REPO_ROOT="$REPO_ROOT" DB="$DB" \
  EXPERIMENT_ID="$EXPERIMENT_ID" INTERVAL="$INTERVAL" LOG_DIR="$LOG_DIR" \
  MODEL_ARGS="$MODEL_ARGS" "$PYTHON" - "$TEMPLATE" <<'PY'
import os, sys
text = open(sys.argv[1], encoding="utf-8").read()
for key in ("LABEL", "PYTHON", "REPO_ROOT", "DB", "EXPERIMENT_ID", "INTERVAL", "LOG_DIR", "MODEL_ARGS"):
    text = text.replace(f"__{key}__", os.environ[key])
if "__" in text.split("-->", 1)[1]:
    raise SystemExit("unfilled placeholder remains in rendered plist")
sys.stdout.write(text)
PY
}

RENDERED="$(render)"

if [ "$DRY_RUN" = 1 ]; then
  printf '%s\n' "$RENDERED"
  printf '\n# dry run: would write %s and bootstrap %s\n' "$PLIST" "$DOMAIN/$LABEL"
  exit 0
fi

mkdir -p "$LOG_DIR" "$HOME/Library/LaunchAgents"
chmod 700 "$LOG_DIR"
if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "$DOMAIN/$LABEL"
  printf 'unloaded previous %s\n' "$LABEL"
fi
printf '%s\n' "$RENDERED" > "$PLIST"
chmod 600 "$PLIST"
plutil -lint "$PLIST" >/dev/null || fail "rendered plist failed plutil -lint"
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl print "$DOMAIN/$LABEL" >/dev/null || fail "job did not load"
printf 'installed %s\n' "$LABEL"
printf '  runs every %s s as %s, database %s\n' "$INTERVAL" "$(id -un)" "$DB"
printf '  working directory: %s (use a long-lived checkout, not a worktree)\n' "$REPO_ROOT"
printf '  logs: %s/wake-executor.{log,err}\n' "$LOG_DIR"
printf '  model host: %s\n' "${MODEL_COMMAND:-none (wakes are recorded as unattended)}"
if [ "$KICKSTART" = 1 ]; then
  launchctl kickstart -k "$DOMAIN/$LABEL"
  printf 'kickstarted; check the log for the first pass\n'
fi
printf 'remove with: %s --agent %s --uninstall\n' "$0" "$AGENT"
