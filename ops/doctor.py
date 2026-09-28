#!/usr/bin/env python3
"""Hive doctor: a health check that tells the hive (and the owner) exactly what is broken and how to fix it.

The JEVX lane reads this every hour and turns each FAIL/WARN into a task: tooling problems become OpenCode tasks,
anything that needs a login, a payment or a settings click becomes an `H-` owner task.

    python3 ops/doctor.py            # repo checks (+ Mac checks when HIVE_WHERE=mac)
    python3 ops/doctor.py --mac      # force the Mac checks
    python3 ops/doctor.py --json     # machine-readable
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

CONTENT = Path(__file__).resolve().parents[1]
HIVE_HOME = Path(os.environ.get("HIVE_HOME", Path.home() / ".hive"))
sys.path.insert(0, str(CONTENT / "ops"))

results: list[dict] = []


def report(level: str, check: str, detail: str, fix: str = "") -> None:
    results.append({"level": level, "check": check, "detail": detail, "fix": fix})


def run(*cmd: str, timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def repo_checks() -> None:
    gate = run(sys.executable, str(CONTENT / "scripts" / "validate.py"))
    last = (gate.stdout.strip().splitlines() or ["(no output)"])[-1]
    if gate.returncode == 0:
        report("OK", "content gate", last)
    else:
        report("FAIL", "content gate", last, "OpenCode/Hermes task: fix the errors listed by scripts/validate.py")
    try:
        import agentctl
        agentctl.fetch_base()
        tasks, done, held = agentctl.load_tasks(), agentctl.done_ids(), agentctl.claimed_ids()
        share, published, rejected = agentctl.current_share(tasks, done, agentctl.load_hive_config())
    except Exception as exc:  # offline or no remote: report instead of crashing
        report("WARN", "backlog", f"could not read the remote backlog ({type(exc).__name__})",
               "check network and `git remote -v`; run `gh auth status`")
        return
    report("OK", "focus", f"india share {share:.0%} (published {published}, rejected {rejected})")
    if published + rejected >= 5 and rejected / (published + rejected) > 0.3:
        report("WARN", "quality", f"{rejected} of {published + rejected} india tasks rejected",
               "JEVX: read the rejection reasons in ops/plan/ and sharpen the task accept criteria or skills")
    for lane in ("hermes", "opencode"):
        for focus in ("core", "india"):
            ready = [t for t in tasks if t.get("lane") == lane and t.get("focus", "core") == focus
                     and t["id"] not in done and t["id"] not in held and not t.get("blocked")
                     and all(d in done for d in t.get("deps", []))]
            level = "OK" if ready else "WARN"
            report(level, f"backlog {lane}/{focus}", f"{len(ready)} ready tasks",
                   "" if ready else f"JEVX: add {focus} tasks for the {lane} lane to ops/tasks.toml")
    stale = [tid for tid, how in held.items() if how == "claim" and tid not in done]
    if len(stale) > 10:
        report("WARN", "claims", f"{len(stale)} claims held without a work branch",
               "they are freed after 6h by `agentctl.py reap`; many at once usually means agents are crashing")


def tool_version(name: str, *args: str) -> str | None:
    if not shutil.which(name):
        return None
    out = run(name, *args, timeout=20)
    return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr).strip() else "present"


def mac_checks() -> None:
    if sys.version_info < (3, 11):
        report("FAIL", "python", sys.version.split()[0], "install Python 3.11+ (brew install python@3.12)")
    for name, args, need, fix in [
        ("git", ("--version",), True, "xcode-select --install"),
        ("gh", ("--version",), True, "brew install gh && gh auth login --web"),
        ("perl", ("-v",), True, "perl ships with macOS; reinstall Command Line Tools"),
        ("opencode", ("--version",), False, "curl -fsSL https://opencode.ai/install | bash"),
        ("hermes", ("--version",), False, "install Hermes Agent (see its docs)"),
        ("gemini", ("--version",), False, "npm install -g @google/gemini-cli && gemini (sign in once)"),
        ("agy", ("--version",), False, "install the Antigravity CLI and sign in once"),
        ("ollama", ("--version",), False, "brew install ollama (optional: unlimited local model)"),
    ]:
        version = tool_version(name, *args)
        if version:
            report("OK", f"tool {name}", version)
        else:
            report("FAIL" if need else "WARN", f"tool {name}", "not found", fix)
    if shutil.which("gh"):
        auth = run("gh", "auth", "status")
        if auth.returncode == 0:
            report("OK", "github login", "gh is logged in")
        else:
            report("FAIL", "github login", "gh is not logged in", "OWNER: run `gh auth login --web` once")
    env = HIVE_HOME / "agents.env"
    report("OK" if env.exists() else "FAIL", "agents.env", str(env),
           "" if env.exists() else "run ops/mac-bootstrap.sh")
    cron = run("crontab", "-l")
    installed = ">>> hive >>>" in cron.stdout
    report("OK" if installed else "FAIL", "schedule", "hive block in crontab" if installed else "no hive cron block",
           "" if installed else "run ops/mac-bootstrap.sh")
    now = time.time()
    for log in sorted(HIVE_HOME.glob("*.log")):
        age_h = (now - log.stat().st_mtime) / 3600
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]
        errors = [l for l in tail if re.search(r"ERROR|Traceback|failed|exited with|not logged|denied", l)]
        worker = log.stem
        if age_h > 3:
            report("WARN", f"worker {worker}", f"last ran {age_h:.0f}h ago",
                   "Mac asleep or cron not running: keep the Mac awake/plugged in; check `crontab -l`")
        elif errors:
            detail = errors[-1][:200]
            fix = ("OWNER: grant Full Disk Access to /usr/sbin/cron" if "Operation not permitted" in detail or
                   "denied" in detail else f"OpenCode task: investigate the {worker} failure in ~/.hive/{worker}.log")
            report("WARN", f"worker {worker}", detail, fix)
        else:
            report("OK", f"worker {worker}", f"ran {age_h:.1f}h ago, no errors in the last run")
    inv = HIVE_HOME / "harvest" / "inventory.jsonl"
    if inv.exists():
        count = sum(1 for _ in inv.open(encoding="utf-8"))
        report("OK", "harvest", f"{count} local items indexed, updated {(now - inv.stat().st_mtime) / 3600:.0f}h ago")
    else:
        report("WARN", "harvest", "no local inventory yet", "run `python3 ops/harvest.py scan` (bootstrap schedules it)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mac", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    repo_checks()
    if args.mac or os.environ.get("HIVE_WHERE") == "mac":
        mac_checks()
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{r['level']:4} {r['check']:22} {r['detail']}" + (f"\n     fix: {r['fix']}" if r["fix"] else ""))
    return 1 if any(r["level"] == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
