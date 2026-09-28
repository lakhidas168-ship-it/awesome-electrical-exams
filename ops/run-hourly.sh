#!/usr/bin/env bash
# Hourly hive runner: one lane, one task, one PR (or one judged branch in the cloud).
# The agent only edits files. This script does the git work and writes the receipt,
# so every claim about "what changed", "what was fetched" and "checks passed" comes from code, not from the agent.
#
#   ops/run-hourly.sh <lane> [worker]      lane: hermes|opencode|jevx; worker: any name, default = lane
#
# Several workers can serve one lane in parallel (e.g. hermes, gemini and antigravity all in the hermes lane);
# each gets its own worktree, lock and logs, and task claims keep them from ever taking the same task.
#
# Env:
#   HIVE_CMD_<WORKER> or HIVE_CMD_<LANE>   agent command; the prompt is appended as the last argument.
#                 "free-agent" = the built-in zero-cost agent (ops/free_agent.py). HIVE_CMD_OPENCODE defaults to
#                 "opencode run".
#   HIVE_FALLBACK command to retry once with when the agent fails without changing anything (e.g. free-agent)
#   HIVE_WHERE    "mac" on the owner's machine, "cloud" in Actions: tasks marked where="mac" run only on the Mac
#   HIVE_OPEN_PR  1 (default): open a PR, JEVX reviews it. 0 (cloud): push the branch for ops/judge.py instead.
#   HIVE_HOME     per-lane worktrees and logs (default ~/.hive)
#   HIVE_TIMEOUT  seconds per agent run (default 2700)
#   HIVE_REMOTE / HIVE_BASE   default origin / main
# Compatible with macOS bash 3.2.
set -euo pipefail

LANE="${1:?usage: run-hourly.sh hermes|opencode|jevx [worker]}"
WORKER="${2:-$LANE}"
HERE="$(cd "$(dirname "$0")" && pwd -P)"
REPO="$(git -C "$HERE" rev-parse --show-toplevel)"
REPO="$(cd "$REPO" && pwd -P)"
HERE_DIR="$(dirname "$HERE")"
HERE_DIR="$(cd "$HERE_DIR" && pwd -P)"
PREFIX="$(python3 -c 'import os,sys;print(os.path.relpath(sys.argv[1],sys.argv[2]))' "$HERE_DIR" "$REPO")"
REMOTE="${HIVE_REMOTE:-origin}"
BASE="${HIVE_BASE:-main}"
HIVE_HOME="${HIVE_HOME:-$HOME/.hive}"
TIMEOUT="${HIVE_TIMEOUT:-2700}"
OPEN_PR="${HIVE_OPEN_PR:-1}"

case "$LANE" in
  hermes)   CMD="${HIVE_CMD_HERMES:-}" ;;
  opencode) CMD="${HIVE_CMD_OPENCODE:-opencode run}" ;;
  jevx)     CMD="${HIVE_CMD_JEVX:-}" ;;
  *) echo "unknown lane: $LANE" >&2; exit 2 ;;
esac
WVAR="HIVE_CMD_$(echo "$WORKER" | tr 'a-z-' 'A-Z_')"
if [ -n "${!WVAR:-}" ]; then CMD="${!WVAR}"; fi   # a named worker's own command wins over the lane's
if [ -z "$CMD" ]; then
  echo "set $WVAR (or HIVE_CMD_$(echo "$LANE" | tr a-z A-Z)) to the command that runs $WORKER with a prompt argument" >&2
  exit 2
fi

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $WORKER($LANE): $*"; }

# One run per worker at a time; a lock older than 3h is from a crashed run.
mkdir -p "$HIVE_HOME"
LOCK="$HIVE_HOME/$WORKER.lock"
if [ -d "$LOCK" ] && [ -n "$(find "$LOCK" -maxdepth 0 -mmin +180 2>/dev/null)" ]; then rmdir "$LOCK"; fi
if ! mkdir "$LOCK" 2>/dev/null; then log "previous run still active, skipping"; exit 0; fi
TASK_ID=""
PR_OPENED=0
cleanup() {
  # A run that dies after claiming must not keep the task locked for 6 hours.
  if [ -n "$TASK_ID" ] && [ "$PR_OPENED" = 0 ]; then
    python3 "$C/ops/agentctl.py" release "$TASK_ID" >/dev/null 2>&1 || true
  fi
  rmdir "$LOCK" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 143' INT TERM   # a stopped worker still releases its claim and lock through the EXIT trap

# Each lane works in its own worktree, so lanes run in parallel without touching each other's files.
WT="$HIVE_HOME/worktrees/$WORKER"
git -C "$REPO" fetch --quiet "$REMOTE" "$BASE"
if [ ! -d "$WT" ]; then
  git -C "$REPO" worktree add --quiet --detach "$WT" "$REMOTE/$BASE"
fi
sync_to_base() {
  git fetch --quiet "$REMOTE" "$BASE"
  git checkout --quiet --detach -f "$REMOTE/$BASE"
  git clean -fdq
}
cd "$WT"
sync_to_base
C="$WT/$PREFIX"
NOTES="$C/ops/.notes.md"   # gitignored scratch file the agent writes; copied into the receipt
FETCH_LOG="$HIVE_HOME/$WORKER.fetch.jsonl"   # written by code (free_agent / MCP fetch tool), outside the worktree
rm -f "$NOTES" "$FETCH_LOG"
resolve_cmd() { if [ "$1" = "free-agent" ]; then echo "python3 $C/ops/free_agent.py --lane $LANE"; else echo "$1"; fi; }
CMD="$(resolve_cmd "$CMD")"
export HIVE_NOTES="$NOTES" HIVE_FETCH_LOG="$FETCH_LOG"

AGENT_RC=0
run_agent() {  # $1 = prompt file
  local prompt sb
  prompt="$(cat "$1")"
  # Agents start in the content folder, so OpenCode finds opencode.json (MCP) and .agents/skills there.
  # perl alarm = portable timeout (macOS has no coreutils timeout by default)
  if [ "${HIVE_SANDBOX:-0}" = 1 ] && [ "$CMD" != "$(resolve_cmd free-agent)" ]; then
    # Cloud: agents with a shell work on a copy with no .git and no GitHub token, so they can only change files;
    # pushing stays with this runner and the judge.
    sb="$HIVE_HOME/sandbox/$WORKER"
    rm -rf "$sb" && mkdir -p "$sb" && cp -R "$C/." "$sb/"
    # shellcheck disable=SC2086  # CMD is intentionally word-split into command + args
    (cd "$sb" && env -u GITHUB_TOKEN -u GH_TOKEN -u GITHUB_MODELS_TOKEN HIVE_NOTES="$sb/ops/.notes.md" \
       perl -e 'alarm shift; exec @ARGV' "$TIMEOUT" $CMD "$prompt") && AGENT_RC=0 || AGENT_RC=$?
    [ -f "$sb/ops/.notes.md" ] && cp "$sb/ops/.notes.md" "$NOTES"
    python3 - "$sb" "$C" <<'PY'
import shutil, sys
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
skip = lambda rel: rel.parts[:1] == ("__pycache__",) or "__pycache__" in rel.parts or rel.as_posix() == "ops/.notes.md"
for p in sorted(dst.rglob("*"), reverse=True):  # files the agent deleted in the sandbox
    rel = p.relative_to(dst)
    if (p.exists() or p.is_symlink()) and not skip(rel) and not (src / rel).exists():
        shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()
for p in src.rglob("*"):  # files the agent created or changed
    rel = p.relative_to(src)
    if p.is_file() and not skip(rel):
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst / rel)
PY
  else
    # shellcheck disable=SC2086
    (cd "$C" && perl -e 'alarm shift; exec @ARGV' "$TIMEOUT" $CMD "$prompt") && AGENT_RC=0 || AGENT_RC=$?
  fi
  if [ "$AGENT_RC" = 75 ]; then
    log "no free LLM capacity right now (exit 75); task goes back to the queue"
    exit "${HIVE_NO_TASK_EXIT:-0}"   # continuous mode backs off instead of hammering a rate limit
  fi
  [ "$AGENT_RC" = 0 ] || log "agent exited with $AGENT_RC"
}

run_agent_with_fallback() {  # a broken or logged-out agent must not stall the lane: retry once on the fallback
  run_agent "$1"
  if [ "$AGENT_RC" != 0 ] && [ -z "$(git status --porcelain)" ] && [ -n "${HIVE_FALLBACK:-}" ] \
     && [ "$(resolve_cmd "$HIVE_FALLBACK")" != "$CMD" ]; then
    log "agent failed without changes; retrying once with $HIVE_FALLBACK"
    CMD="$(resolve_cmd "$HIVE_FALLBACK")"
    run_agent "$1"
  fi
}

skill_for() {  # lane skill injected into the prompt (agents that load .agents/skills natively see it anyway)
  case "$LANE:$1" in
    hermes:Harvest*) echo harvest-import ;;
    hermes:*modules/*) echo module-page ;;
    hermes:*) echo exam-page ;;
    opencode:*) echo hive-tooling ;;
    *) echo review-agent-work ;;
  esac
}

open_pr() {  # $1 = branch, $2 = title, $3 = body file
  git push --quiet -u "$REMOTE" "HEAD:refs/heads/$1"
  gh pr create --base "$BASE" --head "$1" --title "$2" --body-file "$3"
}

if [ "$LANE" = "jevx" ]; then
  # Planner + judge. On the Mac (HIVE_OPEN_PR=0), the cloud judge (ops/judge.py --publish) handles merging.
  # This lane only produces a plan branch with the Hive-Publish: judge trailer.
  if [ "$OPEN_PR" = 1 ]; then
    # Cloud mode: merge_ready.sh and gh PR operations are available.
    "$C/ops/merge_ready.sh" || log "merge_ready failed"
  fi
  sync_to_base
  python3 "$C/ops/agentctl.py" reap --hours 6 || true
  P="$HIVE_HOME/$WORKER.prompt.md"
  {
    cat "$C/ops/prompts/jevx.md"
    printf '\n## Context gathered by the runner (code)\n\n### Backlog status\n```\n'
    python3 "$C/ops/agentctl.py" status || true
    printf '```\n\n### Content gate on %s\n```\n' "$BASE"
    python3 "$C/scripts/validate.py" || true
    printf '```\n\n### Hive doctor (health check; turn every problem into a fix task or an H- owner task)\n```\n'
    python3 "$C/ops/doctor.py" || true
    if [ "${HIVE_WHERE:-}" = mac ]; then
      printf '```\n\n### Harvest of the owner'"'"'s earlier work (append new entries to ops/tasks.toml; they are where = "mac")\n```toml\n'
      python3 "$C/ops/harvest.py" tasks --top 10 2>&1 || true
    fi
    if [ "$OPEN_PR" = 1 ]; then
      printf '```\n\n### Open agent PRs\n```\n'
      gh pr list --state open --json number,title,headRefName,url \
        --jq '.[] | select(.headRefName | startswith("agent/")) | "#\(.number) \(.headRefName) \(.title) \(.url)"' || true
      printf '```\n'
    fi
  } > "$P"
  run_agent_with_fallback "$P"
  python3 "$C/scripts/validate.py" --write > /dev/null || true
  if [ -n "$(git status --porcelain)" ]; then
    BR="agent/jevx/plan-$(date -u +%Y%m%d-%H%M)"
    git add -A
    if [ "$OPEN_PR" = 1 ]; then
      # Cloud mode: create a PR for JEVX to review.
      git commit --quiet -m "hive(jevx): plan and backlog update $(date -u +%Y-%m-%dT%H:%MZ)"
      printf 'Planner update from the JEVX lane. Touches only ops/tasks.toml, ops/plan/, README index and UPDATES.md.\n' > "$HIVE_HOME/jevx.body.md"
      # An older planner PR still open (CI red or slow) would conflict with this one; this run supersedes it.
      gh pr list --state open --json number,headRefName \
        --jq '.[] | select(.headRefName | startswith("agent/jevx/")) | .number' | while read -r n; do
        gh pr close "$n" --delete-branch --comment "Superseded by the next JEVX run." || true
      done
      open_pr "$BR" "hive(jevx): plan $(date -u +%Y-%m-%d\ %H:%M) UTC" "$HIVE_HOME/jevx.body.md" || log "PR creation failed"
    else
      # Mac mode (HIVE_OPEN_PR=0): push a branch for the local judge (ops/judge.py --publish).
      git commit --quiet -m "hive(jevx): plan and backlog update $(date -u +%Y-%m-%dT%H:%MZ)" -m "Hive-Publish: judge"
      git push --quiet -u "$REMOTE" "HEAD:refs/heads/$BR" || log "push failed"
      log "pushed $BR for the local judge"
    fi
  fi
  if [ "$OPEN_PR" = 1 ]; then
    "$C/ops/merge_ready.sh" || log "merge_ready failed"
  fi
  exit 0
fi

# Worker lanes: claim one task, let the agent edit files, gate, receipt, PR.
python3 "$C/ops/agentctl.py" reap --hours 6 || true
set +e
TASK_JSON="$(python3 "$C/ops/agentctl.py" next "$LANE" --claim --agent "$WORKER")"
rc=$?
set -e
if [ $rc -eq 3 ]; then log "no ready task"; exit "${HIVE_NO_TASK_EXIT:-0}"; fi
if [ $rc -ne 0 ]; then log "agentctl failed ($rc)"; exit $rc; fi
TASK_ID="$(printf '%s' "$TASK_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')"
TITLE="$(printf '%s' "$TASK_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin)["title"])')"
BRANCH="agent/$LANE/$TASK_ID"
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export HIVE_TASK_ID="$TASK_ID"
log "claimed $TASK_ID: $TITLE"
git checkout --quiet -B "$BRANCH"   # -B: a retried task may have a stale local branch

P="$HIVE_HOME/$WORKER.prompt.md"
{
  cat "$C/ops/prompts/$LANE.md"
  printf '\n## Skill\n\n'
  cat "$C/.agents/skills/$(skill_for "$TITLE")/SKILL.md"
  printf '\n## Your task (from ops/tasks.toml)\n\n```json\n%s\n```\n' "$TASK_JSON"
  printf '\nWork only inside the content folder (your current directory). Write your notes (sources opened, what you confirmed, what you could not) to ops/.notes.md there.\n'
} > "$P"
run_agent_with_fallback "$P"

# last_verified = the day the page was checked, i.e. this run. Agents kept writing the notification's date there
# (2025-05-14, 2024-05-22), which the content gate then flags as stale. Normalise every exam page changed in this run.
python3 - "$C" <<'PY' || true
import datetime, re, subprocess, sys
from pathlib import Path
c = Path(sys.argv[1]); today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
changed = subprocess.run(["git", "status", "--porcelain", "--", "exams"], cwd=c, capture_output=True, text=True).stdout
for line in changed.splitlines():
    p = c / line[3:].strip().split(" -> ")[-1].removeprefix(c.name + "/")
    if p.suffix == ".md" and p.exists():
        t = p.read_text(encoding="utf-8")
        n = re.sub(r"^last_verified: \S+$", f"last_verified: {today}", t, count=1, flags=re.M)
        if n != t:
            p.write_text(n, encoding="utf-8")
PY

# Workers never regenerate README index / UPDATES.md (the JEVX lane does), so parallel PRs don't conflict.
GATE_LOG="$HIVE_HOME/$WORKER.gate.log"
if ! python3 "$C/scripts/validate.py" > "$GATE_LOG" 2>&1; then
  log "content gate failed, giving the agent one repair pass"
  { cat "$P"; printf '\n## The content gate failed. Fix these errors and change nothing else:\n```\n'; cat "$GATE_LOG"; printf '```\n'; } > "$P.fix"
  run_agent "$P.fix"
  if ! python3 "$C/scripts/validate.py" > "$GATE_LOG" 2>&1; then
    log "content gate still failing; releasing $TASK_ID"
    cat "$GATE_LOG"
    python3 "$C/ops/agentctl.py" release "$TASK_ID" || true
    exit 1
  fi
fi

if [ -z "$(git status --porcelain)" ] && [ "$(git rev-list --count "$REMOTE/$BASE"..HEAD)" = "0" ]; then
  log "agent made no changes; releasing $TASK_ID"
  python3 "$C/ops/agentctl.py" release "$TASK_ID" || true
  exit 0
fi

git add -A
python3 "$C/ops/agentctl.py" receipt "$TASK_ID" --lane "$LANE" --agent-cmd "$CMD" \
  --started "$STARTED" --validator-log "$GATE_LOG" --notes "$NOTES" --fetch-log "$FETCH_LOG" > /dev/null
rm -f "$NOTES"
git add -A
if [ "$OPEN_PR" = 0 ]; then
  git commit --quiet -m "[$TASK_ID] $TITLE (lane: $LANE)" -m "Hive-Publish: judge"
else
  git commit --quiet -m "[$TASK_ID] $TITLE (lane: $LANE)"
fi
# Fail early on claims the judge would reject anyway: scope, and "official" without fetched evidence.
if ! git diff --name-only "$REMOTE/$BASE"...HEAD | python3 "$C/scripts/hive_gate.py" --branch "$BRANCH" \
   || ! python3 "$C/scripts/evidence_gate.py" --base "$REMOTE/$BASE" --branch "$BRANCH"; then
  log "lane scope or evidence gate failed; releasing $TASK_ID"
  exit 1
fi
git push --quiet -u "$REMOTE" "HEAD:refs/heads/$BRANCH"
PR_OPENED=1   # the work branch now holds the task; closing/rejecting it with branch deletion frees it
if [ "$OPEN_PR" = 0 ]; then
  log "pushed $BRANCH for the cloud judge"
  exit 0
fi
gh pr create --base "$BASE" --head "$BRANCH" --title "[$TASK_ID] $TITLE" --body-file "$C/ops/done/$TASK_ID.md" \
  || { log "PR creation failed; branch $BRANCH is pushed, open the PR by hand or delete the branch"; exit 1; }
log "opened PR for $TASK_ID"
