#!/usr/bin/env bash
# Merge agent PRs that are approved and green. Called by the JEVX lane at the end of each run.
#   agent/jevx/*  -> needs green checks (CI's hive-gate already limits it to ops/ + generated files)
#   agent/*/*     -> needs the hive:approved label (set by JEVX after review) AND green checks
# Code decides the merge, not an agent: a PR merges only when `gh pr checks` exits 0.
set -euo pipefail

gh label create "hive:approved" --color 0E8A16 --description "Reviewed and approved by the JEVX lane" --force >/dev/null 2>&1 || true

gh pr list --state open --limit 100 --json number,headRefName,labels \
  --jq '.[] | select(.headRefName | startswith("agent/")) | "\(.number)\t\(.headRefName)\t\([.labels[].name] | join(","))"' |
while IFS=$'\t' read -r num head labels; do
  case "$head" in
    agent/jevx/*) ready=1 ;;
    *) case ",$labels," in *,hive:approved,*) ready=1 ;; *) ready=0 ;; esac ;;
  esac
  [ "$ready" = 1 ] || continue
  if gh pr checks "$num" >/dev/null 2>&1; then
    gh pr merge "$num" --squash --delete-branch && echo "merged #$num ($head)"
  else
    echo "#$num ($head) approved but checks not green yet"
  fi
done
