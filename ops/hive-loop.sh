#!/usr/bin/env bash
# Continuous mode for the owner's Mac: many workers per lane, each taking tasks back-to-back until stopped.
# Hourly cron is the steady state; this is the "use the whole Mac now" mode.
#
#   bash awesome-electrical-exams/ops/hive-loop.sh start     # launch (keeps the Mac awake while running)
#   bash awesome-electrical-exams/ops/hive-loop.sh status    # who is alive, last line of each log
#   bash awesome-electrical-exams/ops/hive-loop.sh stop      # stop every loop
#
# ~/.hive/agents.env settings (defaults in brackets):
#   HIVE_LOOP_HERMES [6]    parallel Hermes-lane workers (hermes-1..N, command HIVE_CMD_HERMES)
#   HIVE_LOOP_OPENCODE [6]  parallel OpenCode-lane workers (opencode-1..N, command HIVE_CMD_OPENCODE)
#   HIVE_LOOP_EXTRA ["hermes:gemini hermes:antigravity" when those commands are set]  extra lane:worker loops
#   HIVE_LOOP_JEVX_EVERY [1800]  seconds between JEVX review/plan/merge runs
#   HIVE_LOOP_IDLE [600]    seconds a worker waits when there is no ready task (or no LLM capacity)
# Workers never collide: every task claim is atomic on GitHub. Compatible with macOS bash 3.2.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
HIVE_HOME="${HIVE_HOME:-$HOME/.hive}"
mkdir -p "$HIVE_HOME"
# shellcheck disable=SC1091
[ -f "$HIVE_HOME/agents.env" ] && . "$HIVE_HOME/agents.env"
PIDS="$HIVE_HOME/loop.pids"

worker_loop() {  # $1 lane, $2 worker name
  trap '' HUP   # keep running after the Terminal window that started it is closed
  while true; do
    HIVE_NO_TASK_EXIT=3 /bin/bash "$HERE/hive-cron.sh" "$1" "$2"
    rc=$?
    if [ "$rc" = 3 ]; then sleep "${HIVE_LOOP_IDLE:-600}"; else sleep 5; fi
  done
}

jevx_loop() {
  trap '' HUP
  while true; do
    /bin/bash "$HERE/hive-cron.sh" jevx
    sleep "${HIVE_LOOP_JEVX_EVERY:-1800}"
  done
}

start() {
  if [ -f "$PIDS" ] && kill -0 "$(head -1 "$PIDS")" 2>/dev/null; then echo "already running (hive-loop.sh status)"; exit 0; fi
  : > "$PIDS"
  set -m   # every loop gets its own process group, so `stop` can end it with everything it started
  extra="${HIVE_LOOP_EXTRA:-}"
  if [ -z "$extra" ]; then
    [ -n "${HIVE_CMD_GEMINI:-}" ] && extra="$extra hermes:gemini"
    [ -n "${HIVE_CMD_ANTIGRAVITY:-}" ] && extra="$extra hermes:antigravity"
  fi
  # Loops never hold the caller's stdout/stderr open, so `start` returns at once even when its output is
  # captured (for example by an agent's shell tool).
  L="$HIVE_HOME/loop.log"
  i=1; while [ "$i" -le "${HIVE_LOOP_HERMES:-6}" ]; do
    worker_loop hermes "hermes-$i" >> "$L" 2>&1 < /dev/null & echo $! >> "$PIDS"; i=$((i + 1)); done
  i=1; while [ "$i" -le "${HIVE_LOOP_OPENCODE:-6}" ]; do
    worker_loop opencode "opencode-$i" >> "$L" 2>&1 < /dev/null & echo $! >> "$PIDS"; i=$((i + 1)); done
  for pair in $extra; do worker_loop "${pair%%:*}" "${pair#*:}" >> "$L" 2>&1 < /dev/null & echo $! >> "$PIDS"; done
  jevx_loop >> "$L" 2>&1 < /dev/null & echo $! >> "$PIDS"
  # Keep the Mac awake (display may sleep) for as long as the first loop lives.
  if command -v caffeinate >/dev/null 2>&1; then
    caffeinate -ims -w "$(head -1 "$PIDS")" >> "$L" 2>&1 < /dev/null & echo $! >> "$PIDS"
  fi
  echo "started $(wc -l < "$PIDS" | tr -d ' ') processes; logs in $HIVE_HOME/*.log"
}

stop() {
  [ -f "$PIDS" ] || { echo "not running"; exit 0; }
  # Kill only the process groups this script started (never match other processes by name).
  while read -r pid; do kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null; done < "$PIDS"
  rm -f "$PIDS"
  echo "stopped (claims of interrupted tasks are released, or freed by reap within 6 hours)"
}

status() {
  if [ -f "$PIDS" ]; then
    alive=0; while read -r pid; do kill -0 "$pid" 2>/dev/null && alive=$((alive + 1)); done < "$PIDS"
    echo "$alive of $(wc -l < "$PIDS" | tr -d ' ') loop processes alive"
  else
    echo "not running"
  fi
  for log in "$HIVE_HOME"/*.log; do
    [ -f "$log" ] && printf '%-18s %s\n' "$(basename "$log" .log)" "$(grep -v '^-----' "$log" | tail -1 | cut -c1-110)"
  done
}

case "${1:-status}" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  *) echo "usage: hive-loop.sh start|stop|status"; exit 2 ;;
esac
