#!/usr/bin/env bash
# Cron entry point on the owner's Mac: loads ~/.hive/agents.env, fixes PATH, runs one job, appends to its log.
#   hive-cron.sh <lane> [worker]    one hive run (see run-hourly.sh)
#   hive-cron.sh harvest            refresh the private local inventory of past work (ops/harvest.py)
#   hive-cron.sh doctor             health check into ~/.hive/doctor.log
set -u
HIVE_HOME="${HIVE_HOME:-$HOME/.hive}"
mkdir -p "$HIVE_HOME"
# shellcheck disable=SC1091
[ -f "$HIVE_HOME/agents.env" ] && . "$HIVE_HOME/agents.env"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.opencode/bin:$HOME/.npm-global/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export HIVE_HOME HIVE_WHERE="${HIVE_WHERE:-mac}"
HERE="$(cd "$(dirname "$0")" && pwd)"
job="${1:?usage: hive-cron.sh <lane> [worker] | harvest | doctor}"
name="${2:-$1}"
exec >> "$HIVE_HOME/$name.log" 2>&1
echo "----- $(date -u +%Y-%m-%dT%H:%M:%SZ) start $*"
case "$job" in
  harvest) python3 "$HERE/harvest.py" scan ;;
  doctor)  python3 "$HERE/doctor.py" --mac ;;
  *)       "$HERE/run-hourly.sh" "$@" ;;
esac
rc=$?
echo "----- $(date -u +%Y-%m-%dT%H:%M:%SZ) end (exit $rc)"
exit $rc
