#!/bin/bash
# Cloud batch runner for the hive: runs N workers against a LOCAL bare repo so claims/branches NEVER reach GitHub.
# Dry-run: HIVE_CLOUD_DRY=1 bash ops/cloud_batch.sh  (uses temp copy, mock LLM, never pushes)
# Real run:  bash ops/cloud_batch.sh  (used by .github/workflows/hive-cloud.yml)
#
# Design: ONE job, 6 workers (3 hermes-lane + 3 opencode-lane) in parallel, each looping until 40 min elapsed
# or no ready task. Then judge.py --publish --limit 30 against the hub, then push ONE commit to origin/main
# if the hub's tree differs.
#
# bash 3.2 compatible (macOS default). No arrays, no [[ ]], no local -n.
set -eu

# Script is at <repo_root>/awesome-electrical-exams/ops/cloud_batch.sh
# Go up two levels to get repo_root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$CONTENT_DIR/.." && pwd)"
CONTENT="$CONTENT_DIR"
HUB_DIR="/tmp/hive-hub-$$"
HIVE_HOME="/tmp/hive-cloud-$$"
MAX_WORKERS=6
WORKER_TIMEOUT=2400   # 40 minutes in seconds
START_TIME="$(date +%s)"
DRY_RUN="${HIVE_CLOUD_DRY:-0}"

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

# --- Step 1: Skip if Mac was seen recently (always, including dry run) ---
MAC_LAST_SEEN="${HIVE_MAC_LAST_SEEN:-0}"
NOW="$(date +%s)"
if [ "$MAC_LAST_SEEN" -gt 0 ] && [ $((NOW - MAC_LAST_SEEN)) -lt 7200 ]; then
  log "Mac was seen $((NOW - MAC_LAST_SEEN)) seconds ago (< 7200); skipping cloud run"
  exit 0
fi
log "Mac last seen $((NOW - MAC_LAST_SEEN)) seconds ago; proceeding with cloud run"

# --- Dry-run setup: copy repo to temp, use mock LLM, never push ---
if [ "$DRY_RUN" = "1" ]; then
  log "DRY RUN: setting up temp copy at $HUB_DIR"
  rm -rf "$HUB_DIR" "$HIVE_HOME"
  mkdir -p "$HUB_DIR"
  # Copy the content folder to a bare hub
  rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' "$CONTENT/" "$HUB_DIR/content/"
  cd "$HUB_DIR/content"
  git init -q
  git config user.name "hive-bot"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git add -A
  git commit -q -m "dry-run seed"
  git clone --bare . "$HUB_DIR/hub.git"
  cd "$HUB_DIR/content"
  git remote add hub "$HUB_DIR/hub.git"
  # Use mock LLM
  export HIVE_LLM_BASE_URL="http://127.0.0.1:0/v1"  # will be overridden by test
  export HIVE_SANDBOX=1
  export HIVE_WHERE=cloud
  export HIVE_OPEN_PR=0
  export HIVE_CMD_HERMES=free-agent
  export HIVE_CMD_OPENCODE=free-agent
  export HIVE_FALLBACK=free-agent
  export GITHUB_TOKEN=mock
  export HIVE_REMOTE=hub
  export HIVE_BASE=main
else
  # Real run: use the checkout from Actions (already at CONTENT)
  cd "$CONTENT"
  START_COMMIT="$(git rev-parse HEAD)"   # what this run starts from; only START..hub/main gets published
  log "Cloning bare hub at $HUB_DIR"
  rm -rf "$HUB_DIR" "$HIVE_HOME"
  mkdir -p "$HUB_DIR" "$HIVE_HOME"
  git clone --bare . "$HUB_DIR/hub.git"
  git remote add hub "$HUB_DIR/hub.git" 2>/dev/null || git remote set-url hub "$HUB_DIR/hub.git"
  git config user.name "hive-bot"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  export HIVE_HOME="$HIVE_HOME"
  export HIVE_REMOTE=hub
  export HIVE_BASE=main
  export HIVE_WHERE=cloud
  export HIVE_OPEN_PR=0
  export HIVE_SANDBOX=1
  export HIVE_CMD_HERMES=free-agent
  export HIVE_CMD_OPENCODE=free-agent
  export HIVE_FALLBACK=free-agent
fi

# --- Helper: resolve command for fallback check ---
resolve_cmd() {
  if [ "$1" = "free-agent" ]; then
    echo "python3 $CONTENT/ops/free_agent.py --lane hermes"
  else
    echo "$1"
  fi
}

# --- Helper: run a single worker loop ---
# Args: $1 = lane (hermes|opencode), $2 = worker name (e.g., hermes-1)
run_worker() {
  LANE="$1"
  WORKER="$2"
  LANE_UPPER="$(echo "$LANE" | tr 'a-z' 'A-Z')"
  WORKER_UPPER="$(echo "$WORKER" | tr 'a-z-' 'A-Z_')"
  CMD_VAR="HIVE_CMD_${WORKER_UPPER}"
  CMD="${!CMD_VAR:-}"
  if [ -z "$CMD" ]; then
    CMD_VAR="HIVE_CMD_${LANE_UPPER}"
    CMD="${!CMD_VAR:-free-agent}"
  fi
  if [ "$CMD" = "free-agent" ]; then
    CMD="python3 $CONTENT/ops/free_agent.py --lane $LANE"
  fi

  log "Worker $WORKER ($LANE) starting with command: $CMD"

  # Worktree for this worker
  WT="$HIVE_HOME/worktrees/$WORKER"
  mkdir -p "$WT"
  git -C "$HUB_DIR/content" fetch --quiet hub main
  if [ ! -d "$WT" ]; then
    git -C "$HUB_DIR/content" worktree add --quiet --detach "$WT" hub/main
  fi

  # Sync to latest hub/main
  cd "$WT"
  git fetch --quiet hub main
  git checkout --quiet --detach -f hub/main
  git clean -fdq

  C="$WT"
  NOTES="$C/ops/.notes.md"
  FETCH_LOG="$HIVE_HOME/$WORKER.fetch.jsonl"
  rm -f "$NOTES" "$FETCH_LOG"

  export HIVE_NOTES="$NOTES"
  export HIVE_FETCH_LOG="$FETCH_LOG"

  # Loop until timeout or no ready task
  while :; do
    NOW="$(date +%s)"
    if [ $((NOW - START_TIME)) -ge $WORKER_TIMEOUT ]; then
      log "Worker $WORKER: 40 minute timeout reached"
      break
    fi

    # Reap stale claims first
    python3 "$C/ops/agentctl.py" reap --hours 6 >/dev/null 2>&1 || true

    # Claim next task
    TASK_JSON="$(python3 "$C/ops/agentctl.py" next "$LANE" --claim --agent "$WORKER" 2>/dev/null)" || true
    RC=$?
    if [ $RC -eq 3 ]; then
      log "Worker $WORKER: no ready task"
      break
    fi
    if [ $RC -ne 0 ]; then
      log "Worker $WORKER: agentctl next failed ($RC)"
      break
    fi

    TASK_ID="$(printf '%s' "$TASK_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')"
    TITLE="$(printf '%s' "$TASK_JSON" | python3 -c 'import json,sys;print(json.load(sys.stdin)["title"])')"
    BRANCH="agent/$LANE/$TASK_ID"
    STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    export HIVE_TASK_ID="$TASK_ID"

    log "Worker $WORKER claimed $TASK_ID: $TITLE"
    git checkout --quiet -B "$BRANCH"

    # Build prompt
    P="$HIVE_HOME/$WORKER.prompt.md"
    SKILL_NAME=""
    case "$LANE:$TITLE" in
      hermes:Harvest*) SKILL_NAME=harvest-import ;;
      hermes:*modules/*) SKILL_NAME=module-page ;;
      hermes:*) SKILL_NAME=exam-page ;;
      opencode:*) SKILL_NAME=hive-tooling ;;
      *) SKILL_NAME=review-agent-work ;;
    esac

    {
      cat "$C/ops/prompts/$LANE.md"
      printf '\n## Skill\n\n'
      cat "$C/.agents/skills/$SKILL_NAME/SKILL.md"
      printf '\n## Your task (from ops/tasks.toml)\n\n```json\n%s\n```\n' "$TASK_JSON"
      printf '\nWork only inside the content folder (your current directory). Write your notes (sources opened, what you confirmed, what you could not) to ops/.notes.md there.\n'
    } > "$P"

    # Run agent with fallback
    AGENT_RC=0
    run_agent() {
      local prompt_file="$1"
      local prompt_text="$(cat "$prompt_file")"
      (cd "$C" && env -u GITHUB_TOKEN -u GH_TOKEN -u GITHUB_MODELS_TOKEN HIVE_NOTES="$NOTES" \
         perl -e 'alarm shift; exec @ARGV' "$WORKER_TIMEOUT" $CMD "$prompt_text") && AGENT_RC=0 || AGENT_RC=$?
    }

    run_agent "$P"

    # Fallback if agent failed without changes
    if [ "$AGENT_RC" != 0 ] && [ -z "$(git status --porcelain)" ] && [ -n "${HIVE_FALLBACK:-}" ]; then
      FALLBACK_CMD="python3 $C/ops/free_agent.py --lane $LANE"
      if [ "$(resolve_cmd "$HIVE_FALLBACK")" != "$CMD" ]; then
        log "Worker $WORKER: agent failed without changes; retrying with fallback"
        CMD="$FALLBACK_CMD"
        run_agent "$P"
      fi
    fi

    if [ "$AGENT_RC" = 75 ]; then
      log "Worker $WORKER: no free LLM capacity (exit 75); task requeued"
      python3 "$C/ops/agentctl.py" release "$TASK_ID" >/dev/null 2>&1 || true
      continue
    fi

    # Content gate
    GATE_LOG="$HIVE_HOME/$WORKER.gate.log"
    if ! python3 "$C/scripts/validate.py" > "$GATE_LOG" 2>&1; then
      log "Worker $WORKER: content gate failed, one repair pass"
      { cat "$P"; printf '\n## The content gate failed. Fix these errors and change nothing else:\n```\n'; cat "$GATE_LOG"; printf '```\n'; } > "$P.fix"
      run_agent "$P.fix"
      if ! python3 "$C/scripts/validate.py" > "$GATE_LOG" 2>&1; then
        log "Worker $WORKER: content gate still failing; releasing $TASK_ID"
        python3 "$C/ops/agentctl.py" release "$TASK_ID" >/dev/null 2>&1 || true
        continue
      fi
    fi

    if [ -z "$(git status --porcelain)" ] && [ "$(git rev-list --count "hub/main"..HEAD 2>/dev/null || echo 0)" = "0" ]; then
      log "Worker $WORKER: agent made no changes; releasing $TASK_ID"
      python3 "$C/ops/agentctl.py" release "$TASK_ID" >/dev/null 2>&1 || true
      continue
    fi

    git add -A
    python3 "$C/ops/agentctl.py" receipt "$TASK_ID" --lane "$LANE" --agent-cmd "$CMD" \
      --started "$STARTED" --validator-log "$GATE_LOG" --notes "$NOTES" --fetch-log "$FETCH_LOG" >/dev/null
    rm -f "$NOTES"
    git add -A
    git commit --quiet -m "[$TASK_ID] $TITLE (lane: $LANE)" -m "Hive-Publish: judge"

    # Lane scope and evidence gates
    if ! git diff --name-only "hub/main"...HEAD | python3 "$C/scripts/hive_gate.py" --branch "$BRANCH" \
       || ! python3 "$C/scripts/evidence_gate.py" --base "hub/main" --branch "$BRANCH" --worktree "$WT"; then
      log "Worker $WORKER: lane scope or evidence gate failed; releasing $TASK_ID"
      git reset --quiet --hard "hub/main"
      git clean -fdq
      python3 "$C/ops/agentctl.py" release "$TASK_ID" >/dev/null 2>&1 || true
      continue
    fi

    git push --quiet hub "HEAD:refs/heads/$BRANCH"
    log "Worker $WORKER: pushed $BRANCH for the cloud judge"
  done

  log "Worker $WORKER finished"
}

# --- Run 6 workers in parallel (3 hermes + 3 opencode) ---
log "Starting $MAX_WORKERS workers (3 hermes + 3 opencode)"

PIDS=""
for i in 1 2 3; do
  run_worker hermes "hermes-$i" &
  PIDS="$PIDS $!"
done
for i in 1 2 3; do
  run_worker opencode "opencode-$i" &
  PIDS="$PIDS $!"
done

# Wait for all workers
for PID in $PIDS; do
  wait "$PID" || true
done

log "All workers finished. Running judge..."

# --- Step 5: Run judge against the hub ---
cd "$HUB_DIR/content"
python3 "$CONTENT/ops/judge.py" --publish --limit 30 2>&1 | while IFS= read -r line; do
  log "JUDGE: $line"
done
JUDGE_RC=${PIPESTATUS[0]}
if [ $JUDGE_RC -ne 0 ]; then
  log "Judge exited with $JUDGE_RC"
fi

# --- Step 6: Push ONE commit to origin/main if hub tree differs ---
if [ "$DRY_RUN" = "1" ]; then
  log "DRY RUN: checking if hub tree differs from origin/main (simulated)"
  # In dry run, we simulate the check
  HUB_TREE="$(git -C "$HUB_DIR/content" rev-parse "hub/main^{tree}" 2>/dev/null || echo "")"
  ORIGIN_TREE="$(git -C "$HUB_DIR/content" rev-parse "origin/main^{tree}" 2>/dev/null || echo "")"
  if [ -n "$HUB_TREE" ] && [ -n "$ORIGIN_TREE" ] && [ "$HUB_TREE" != "$ORIGIN_TREE" ]; then
    log "DRY RUN: hub tree differs from origin/main; would create commit"
    STAT="$(git -C "$HUB_DIR/content" diff --shortstat "origin/main" "hub/main" 2>/dev/null | sed 's/^ //')"
    COMMIT="$(git -C "$HUB_DIR/content" commit-tree "$HUB_TREE" -p "$ORIGIN_TREE" -m "Cloud hive update $(date -u '+%F'): $STAT" \
      2>/dev/null || echo "dry-run-commit")"
    log "DRY RUN: candidate commit $COMMIT"
  else
    log "DRY RUN: no difference; nothing to push"
  fi
  log "DRY RUN complete"
  exit 0
fi

# Real run: at most ONE push to origin/main (GitHub). Only the hive's own changes (START..hub/main) are published:
# if origin/main moved during the run (Mac publish, a merged PR), they are re-applied on top of it, never overwritten.
git fetch --quiet hub main
HUB_TREE="$(git rev-parse "hub/main^{tree}" 2>/dev/null || echo "")"
if [ -n "$HUB_TREE" ] && [ "$HUB_TREE" != "$(git rev-parse "$START_COMMIT^{tree}")" ]; then
  STAT="$(git diff --shortstat "$START_COMMIT" "hub/main" | sed 's/^ //')"
  COMMIT_MSG="Cloud hive update $(date -u '+%F %H:%M') UTC: $STAT"
  git fetch --quiet origin main
  if [ "$(git rev-parse origin/main)" = "$START_COMMIT" ]; then
    COMMIT="$(git commit-tree "$HUB_TREE" -p "$START_COMMIT" -m "$COMMIT_MSG")"
  else
    log "origin/main moved during the run; re-applying the hive's changes on top of it"
    git checkout --quiet -f --detach origin/main
    if ! git diff --binary "$START_COMMIT" "hub/main" | git apply --3way --index; then
      log "hive changes conflict with the new origin/main; nothing pushed (the next run retries)"; exit 0
    fi
    COMMIT="$(git commit-tree "$(git write-tree)" -p origin/main -m "$COMMIT_MSG")"
  fi
  if git push --quiet origin "$COMMIT:refs/heads/main"; then log "Pushed $COMMIT to origin/main"; else log "push rejected; nothing pushed (the next run retries)"; fi
else
  log "No hive changes; nothing to push"
fi

log "Cloud batch run complete"
