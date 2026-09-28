#!/usr/bin/env python3
"""Hive task control: lock-free coordination for JEVX, Hermes and OpenCode through git alone.

State lives on the remote, so agents on different machines (or worktrees) stay in sync:
  backlog   ops/tasks.toml on <base>              (single writer: the JEVX lane)
  claimed   refs/heads/claim/<id>  or  refs/heads/agent/<lane>/<id>
  done      ops/done/<id>.md on <base>            (a receipt that landed through a merged PR)

A claim is an atomic create-only push (--force-with-lease=<ref>:), so two agents can
never hold the same task.

    agentctl.py next <lane> [--claim --agent NAME]   print next task as JSON (exit 3 if none)
    agentctl.py claim <id> --agent NAME
    agentctl.py release <id>
    agentctl.py status
    agentctl.py reap [--hours 6]                     free stale claims and claims of done tasks
    agentctl.py receipt <id> --lane L --agent-cmd CMD --started ISO --validator-log FILE [--notes FILE]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path

CONTENT = Path(__file__).resolve().parents[1]
REMOTE = os.environ.get("HIVE_REMOTE", "origin")
BASE = os.environ.get("HIVE_BASE", "main")
NO_TASK = 3


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(CONTENT), *args], text=True, capture_output=True, check=check)


def repo_prefix() -> str:
    top = Path(git("rev-parse", "--show-toplevel").stdout.strip()).resolve()
    return CONTENT.relative_to(top).as_posix()


def fetch_base() -> None:
    git("fetch", "--quiet", REMOTE, BASE)


def base_ref() -> str:
    return f"{REMOTE}/{BASE}"


def load_tasks() -> list[dict]:
    raw = git("show", f"{base_ref()}:{repo_prefix()}/ops/tasks.toml").stdout
    return tomllib.loads(raw).get("task", [])


def done_ids() -> set[str]:
    out = git("ls-tree", "--full-tree", "--name-only", base_ref(), f"{repo_prefix()}/ops/done/").stdout
    return {Path(p).stem for p in out.split() if p.endswith(".md")}


def remote_refs(pattern: str) -> dict[str, str]:
    out = git("ls-remote", REMOTE, pattern).stdout
    refs = {}
    for line in out.splitlines():
        sha, ref = line.split("\t")
        refs[ref] = sha
    return refs


def _public_cmd(cmd: str) -> str:
    """Receipts are published: show the agent command without the owner's home directory (2026-09-28)."""
    home = os.path.expanduser("~")
    return (cmd or "").replace(home, "~")


def claimed_ids() -> dict[str, str]:
    """task id -> who holds it (claim ref or work branch)."""
    held: dict[str, str] = {}
    for ref in remote_refs("refs/heads/claim/*"):
        held[ref.rsplit("/", 1)[1]] = "claim"
    for ref in remote_refs("refs/heads/agent/*"):
        parts = ref.split("/")
        if len(parts) >= 5:
            held[parts[4]] = f"branch {'/'.join(parts[2:])}"
    return held


def load_hive_config() -> dict:
    res = git("show", f"{base_ref()}:{repo_prefix()}/ops/hive.toml", check=False)
    return tomllib.loads(res.stdout) if res.returncode == 0 else {}


GOLDEN = 0.6180339887498949


def maturity(tasks: list[dict], done: set[str], plan_text: str) -> tuple[int, int]:
    """(published, rejected) counts for "india" tasks: receipts on main vs. judge rejections in ops/plan/."""
    india = {t["id"] for t in tasks if t.get("focus") == "india"}
    published = len(india & done)
    rejected = sum(1 for tid in re.findall(r"rejected `([A-Z]-\d{3})`", plan_text) if tid in india)
    return published, rejected


def india_share(config: dict, published: int = 0, rejected: int = 0) -> float:
    """Share of runs for the "india" focus. It is never fixed: it starts at ramp.start (20%) and grows by
    ramp.step (1 point) for every ramp.per_published india tasks published, as long as the approval rate stays at
    or above ramp.min_acceptance. If quality drops below that, it falls back to the start until it recovers.
    Capped at ramp.max so the engineering track is never starved."""
    focus = config.get("focus", {})
    ramp = focus.get("ramp")
    if not ramp:
        total = sum(int(v) for k, v in focus.items() if isinstance(v, int)) or 1
        return int(focus.get("india", 0)) / total
    start, step = float(ramp.get("start", 0.2)), float(ramp.get("step", 0.01))
    per, cap = max(1, int(ramp.get("per_published", 5))), float(ramp.get("max", 0.6))
    judged = published + rejected
    if judged and published / judged < float(ramp.get("min_acceptance", 0.8)):
        return start
    return min(cap, start + step * (published // per))


def preferred_focus(lane: str, config: dict, slot: int | None = None, share: float | None = None) -> str:
    """Low-discrepancy (golden-ratio) choice: over any run of hours the lane spends `share` of them on "india".

    The slot is the current UTC hour (HIVE_SLOT overrides it), shifted per lane so lanes don't switch together.
    """
    if share is None:
        share = india_share(config)
    if slot is None:
        slot = int(os.environ.get("HIVE_SLOT", time.time() // 3600))
    x = ((slot + int(config.get("lane_offset", {}).get(lane, 0))) * GOLDEN) % 1.0
    return "india" if x < share else "core"


def current_share(tasks: list[dict], done: set[str], config: dict) -> tuple[float, int, int]:
    plans = git("ls-tree", "--full-tree", "--name-only", base_ref(), f"{repo_prefix()}/ops/plan/").stdout.split()
    text = "".join(git("show", f"{base_ref()}:{p}", check=False).stdout for p in plans if p.endswith(".md"))
    published, rejected = maturity(tasks, done, text)
    return india_share(config, published, rejected), published, rejected


def runnable_here(task: dict) -> bool:
    """`where = "mac"` tasks need the owner's machine (local files, local tools); cloud runs skip them."""
    where = task.get("where", "any")
    here = os.environ.get("HIVE_WHERE", "any")
    return where == "any" or where == here


def candidates(lane: str) -> list[dict]:
    tasks, done, held = load_tasks(), done_ids(), claimed_ids()
    ready = [t for t in tasks
             if t.get("lane") == lane and t["id"] not in done and t["id"] not in held and runnable_here(t)
             and not t.get("blocked") and all(d in done for d in t.get("deps", []))]
    config = load_hive_config()
    share, _, _ = current_share(tasks, done, config)
    focus = preferred_focus(lane, config, share=share)
    # Preferred focus first; the other focus is the fallback so a lane never idles while work exists.
    return sorted(ready, key=lambda t: (t.get("focus", "core") != focus, t.get("priority", 99), t["id"]))


def claim(task_id: str, agent: str) -> bool:
    base_sha = git("rev-parse", base_ref()).stdout.strip()
    tree = git("rev-parse", f"{base_sha}^{{tree}}").stdout.strip()
    msg = json.dumps({"task": task_id, "agent": agent, "at": now_iso()})
    sha = subprocess.run(["git", "-C", str(CONTENT), "commit-tree", tree, "-p", base_sha, "-m", msg],
                         text=True, capture_output=True, check=True).stdout.strip()
    ref = f"refs/heads/claim/{task_id}"
    res = git("push", "--quiet", f"--force-with-lease={ref}:", REMOTE, f"{sha}:{ref}", check=False)
    return res.returncode == 0


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cmd_next(args: argparse.Namespace) -> int:
    fetch_base()
    for task in candidates(args.lane):
        if args.claim and not claim(task["id"], args.agent or args.lane):
            continue  # another agent won the race; try the next one
        print(json.dumps(task, ensure_ascii=False))
        return 0
    return NO_TASK


def cmd_claim(args: argparse.Namespace) -> int:
    fetch_base()
    if claim(args.id, args.agent):
        print(f"claimed {args.id}")
        return 0
    print(f"{args.id} is already claimed", file=sys.stderr)
    return 1


def cmd_release(args: argparse.Namespace) -> int:
    res = git("push", "--quiet", REMOTE, f":refs/heads/claim/{args.id}", check=False)
    print(f"released {args.id}" if res.returncode == 0 else res.stderr.strip())
    return res.returncode


def cmd_status(_: argparse.Namespace) -> int:
    fetch_base()
    done, held = done_ids(), claimed_ids()
    config = load_hive_config()
    tasks = load_tasks()
    share, published, rejected = current_share(tasks, done, config)
    print(f"# india focus share = {share:.0%} (india tasks published {published}, rejected {rejected})")
    for lane in ("hermes", "opencode"):
        print(f"# {lane}: preferred focus this hour = {preferred_focus(lane, config, share=share)}")
    for t in sorted(load_tasks(), key=lambda t: (t.get("lane", ""), t.get("priority", 99), t["id"])):
        state = "done" if t["id"] in done else held.get(t["id"]) or ("blocked" if t.get("blocked") else "todo")
        print(f"{t['id']:6} {t.get('lane', '?'):9} {t.get('focus', 'core'):6} p{t.get('priority', '?'):<3} "
              f"{state:28} {t.get('title', '')}")
    return 0


def cmd_reap(args: argparse.Namespace) -> int:
    fetch_base()
    done = done_ids()
    working = {ref.split("/")[4] for ref in remote_refs("refs/heads/agent/*") if len(ref.split("/")) >= 5}
    claims = remote_refs("refs/heads/claim/*")
    if claims:
        git("fetch", "--quiet", REMOTE, "+refs/heads/claim/*:refs/hive/claim/*")
    cutoff = time.time() - args.hours * 3600
    for ref, sha in claims.items():
        tid = ref.rsplit("/", 1)[1]
        stamp = int(git("log", "-1", "--format=%ct", sha).stdout.strip() or 0)
        stale = stamp < cutoff and tid not in working
        if tid in done or stale:
            git("push", "--quiet", REMOTE, f":{ref}", check=False)
            print(f"reaped {tid} ({'done' if tid in done else 'stale'})")
    return 0


def cmd_receipt(args: argparse.Namespace) -> int:
    task = next((t for t in load_tasks() if t["id"] == args.id), {"title": ""})
    diffstat = git("diff", "--cached", "--stat", base_ref()).stdout.strip() or "(no staged diff)"
    log = Path(args.validator_log).read_text(encoding="utf-8").strip()
    notes = Path(args.notes).read_text(encoding="utf-8").strip() if args.notes and Path(args.notes).exists() else ""
    # Quoted, so nothing the agent writes can pose as a code-written section of the receipt.
    notes = "\n".join(f"> {line}" if line else ">" for line in notes.splitlines())
    fetched = ""
    if args.fetch_log and Path(args.fetch_log).exists():
        fetched = Path(args.fetch_log).read_text(encoding="utf-8").strip()
    accept = "\n".join(f"- [ ] {a}" for a in task.get("accept", []))
    body = f"""---
task: {args.id}
lane: {args.lane}
title: {task.get('title', '')}
started_at: {args.started}
finished_at: {now_iso()}
---

# {args.id} · {task.get('title', '')}

Receipt written by `ops/run-hourly.sh`. Sections marked *code* were produced by the runner, not by the agent.

## Acceptance criteria (JEVX ticks these during review)

{accept or '- (none listed)'}

## Diff against {BASE} (code)

```
{diffstat}
```

## Content gate output (code)

```
{log}
```

## Sources fetched (code)

```jsonl
{fetched or '# no fetches recorded'}
```

## Agent notes (claims by the agent, not verified by code)

{notes or '_The agent left no notes._'}

Agent command: `{_public_cmd(args.agent_cmd)}`
"""
    out = CONTENT / "ops" / "done" / f"{args.id}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    print(out)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("next")
    p.add_argument("lane")
    p.add_argument("--claim", action="store_true")
    p.add_argument("--agent")
    p.set_defaults(fn=cmd_next)
    p = sub.add_parser("claim")
    p.add_argument("id")
    p.add_argument("--agent", required=True)
    p.set_defaults(fn=cmd_claim)
    p = sub.add_parser("release")
    p.add_argument("id")
    p.set_defaults(fn=cmd_release)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    p = sub.add_parser("reap")
    p.add_argument("--hours", type=float, default=6)
    p.set_defaults(fn=cmd_reap)
    p = sub.add_parser("receipt")
    p.add_argument("id")
    p.add_argument("--lane", required=True)
    p.add_argument("--agent-cmd", required=True)
    p.add_argument("--started", required=True)
    p.add_argument("--validator-log", required=True)
    p.add_argument("--notes")
    p.add_argument("--fetch-log")
    p.set_defaults(fn=cmd_receipt)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except subprocess.CalledProcessError as exc:
        print(f"git failed: {' '.join(exc.cmd)}\n{exc.stderr}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
