#!/usr/bin/env bash
# One command sets up the whole hive on the owner's Mac. Safe to run again at any time (idempotent).
#
#   cd ~/code/lakhidas168-ship-it && bash awesome-indian-exams/ops/mac-bootstrap.sh [--loop]
#
# --loop also starts continuous mode (ops/hive-loop.sh): many workers per lane, back-to-back, Mac kept awake.
#
# What it does:
#   1. checks the basics (git, Python 3.11+, perl, gh) and opens the GitHub login in the browser if needed
#   2. detects the agents on this Mac (OpenCode + OpenCode Go, Hermes, Gemini CLI, Antigravity CLI, JEVX, Ollama)
#      and writes ~/.hive/agents.env (your edits there are kept; the detected version goes to agents.env.detected)
#   3. installs the hourly schedule in crontab (a managed block; the rest of your crontab is untouched)
#   4. starts a first scan of your past work (private, stays on this Mac) and runs the health check
# Compatible with macOS bash 3.2.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(git -C "$HERE" rev-parse --show-toplevel)"
HIVE_HOME="${HIVE_HOME:-$HOME/.hive}"
mkdir -p "$HIVE_HOME"
say() { printf '\n==> %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

say "1/4 basics"
have git || { echo "git missing: run  xcode-select --install  and re-run this script"; exit 1; }
have perl || { echo "perl missing: run  xcode-select --install  and re-run this script"; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null \
  || { echo "Python 3.11+ needed: brew install python@3.12, then re-run"; exit 1; }
if ! have gh; then
  if have brew; then brew install gh; else echo "install GitHub CLI: https://cli.github.com then re-run"; exit 1; fi
fi
gh auth status >/dev/null 2>&1 || gh auth login --web --git-protocol https --hostname github.com
git -C "$REPO" fetch --quiet origin

say "2/4 agents on this Mac"
DET="$HIVE_HOME/agents.env.detected"
{
  echo "# Detected by mac-bootstrap.sh on $(date). Copy lines into agents.env to change what runs."
  echo "export HIVE_WHERE=mac"
  echo "export HIVE_FALLBACK=free-agent      # a failing or logged-out agent retries once on the free agent"
  if have opencode; then
    echo 'export HIVE_CMD_OPENCODE="opencode run -m opencode-go/deepseek-v4.1-flash"   # OpenCode Go plan'
  else
    echo 'export HIVE_CMD_OPENCODE=free-agent'
  fi
  if have hermes; then echo 'export HIVE_CMD_HERMES="hermes -z"'; else echo 'export HIVE_CMD_HERMES=free-agent'; fi
  if have gemini; then echo 'export HIVE_CMD_GEMINI="gemini --yolo -p"          # extra hermes-lane worker'; fi
  # agy hangs without a terminal (known issue); `script` gives it a pseudo-terminal.
  if have agy; then echo 'export HIVE_CMD_ANTIGRAVITY="script -q /dev/null agy --dangerously-skip-permissions -p"'; fi
  if have jevx; then
    echo 'export HIVE_CMD_JEVX="jevx"   # adjust to your JEVX one-shot form; the prompt is appended as the last argument'
  elif have opencode; then
    echo 'export HIVE_CMD_JEVX="opencode run -m opencode-go/deepseek-v4.1-flash"   # set your JEVX command here'
  else
    echo 'export HIVE_CMD_JEVX=free-agent'
  fi
  if have ollama; then echo 'export OLLAMA_BASE_URL=http://localhost:11434/v1   # free local model for free-agent'; fi
  echo 'export HIVE_LOOP_HERMES=6      # continuous mode (ops/hive-loop.sh): parallel Hermes-lane workers'
  echo 'export HIVE_LOOP_OPENCODE=6    # continuous mode: parallel OpenCode-lane workers'
} > "$DET"
[ -f "$HIVE_HOME/agents.env" ] || cp "$DET" "$HIVE_HOME/agents.env"
cat "$HIVE_HOME/agents.env"

say "3/4 hourly schedule"
CRON="/bin/bash $HERE/hive-cron.sh"
BLOCK="$HIVE_HOME/cron.block"
{
  echo "# >>> hive >>> managed by awesome-indian-exams/ops/mac-bootstrap.sh (edit ~/.hive/agents.env instead)"
  echo "5 * * * * $CRON hermes"
  echo "5 * * * * $CRON opencode"
  have gemini && echo "7 * * * * $CRON hermes gemini"
  have agy && echo "9 * * * * $CRON hermes antigravity"
  echo "40 * * * * $CRON jevx"
  echo "15 */6 * * * $CRON harvest"
  echo "50 * * * * $CRON doctor"
  echo "# <<< hive <<<"
} > "$BLOCK"
crontab -l > "$HIVE_HOME/crontab.backup.$(date +%Y%m%d%H%M%S)" 2>/dev/null || true   # keep a copy of the old one
# Build the new crontab in a file first, then install it: never read and write the crontab in one pipe.
NEWTAB="$HIVE_HOME/crontab.new"
{ crontab -l 2>/dev/null | sed '/# >>> hive >>>/,/# <<< hive <<</d' || true; cat "$BLOCK"; } > "$NEWTAB"
crontab "$NEWTAB"
crontab -l | sed -n '/# >>> hive >>>/,/# <<< hive <<</p'

say "4/4 first harvest scan (background) and health check"
nohup /bin/bash "$HERE/hive-cron.sh" harvest >/dev/null 2>&1 &
HIVE_WHERE=mac python3 "$HERE/doctor.py" --mac || true

if [ "${1:-}" = "--loop" ]; then
  say "continuous mode: 6 Hermes + 6 OpenCode workers (and Gemini/Antigravity if present), Mac kept awake"
  /bin/bash "$HERE/hive-loop.sh" start
fi

cat <<'EOF'

Done. The hive now runs every hour on this Mac and in the cloud, sharing one backlog.
Two one-time clicks keep it working 24/7 (details in awesome-indian-exams/docs/OWNER-CLICKS.md):
  • System Settings → Privacy & Security → Full Disk Access → add /usr/sbin/cron   (lets the scan read your folders)
  • System Settings → Battery/Energy → prevent automatic sleep when plugged in       (cron can't run while asleep)
Logs: ~/.hive/*.log     Health: python3 awesome-indian-exams/ops/doctor.py --mac
EOF
