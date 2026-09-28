#!/usr/bin/env python3
"""Cloud JEVX: judge agent branches and publish the approved ones to main. Stdlib only.

For every remote branch agent/<lane>/<task> whose head commit carries the trailer "Hive-Publish: judge":
  1. code gates on the branch: lane scope, content gate, self-tests, evidence gate
  2. an LLM verdict on the diff (free tier; if no provider is available the branch waits for the next run)
  3. approved -> squash-merged onto main and pushed; rejected -> branch deleted, reason logged in ops/plan/
Afterwards the README index, all-exams list, overlap map and UPDATES.md are regenerated and pushed.

    judge.py --publish            # what the hourly cloud workflow runs
    judge.py --publish --no-llm   # code gates only (tests, or when the owner opts out of LLM review)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

CONTENT = Path(__file__).resolve().parents[1]
REMOTE = os.environ.get("HIVE_REMOTE", "origin")
BASE = os.environ.get("HIVE_BASE", "main")
TRAILER = "Hive-Publish: judge"
MAX_DIFF = 14000

sys.path.insert(0, str(CONTENT / "ops"))
import free_agent  # noqa: E402

JUDGE_SYSTEM = """You are JEVX, the judge of an automated team that maintains a free public study guide for
Indian competitive exams. Code has already checked formatting, lane scope and evidence rules. You check what
code cannot: does the change do what the task asks, is it useful to a student, is it honest? Reject if any exam
fact looks invented or is not supported by a fetched official source, if text looks copied from coaching
material, if the change weakens a check or test, or if it is empty or off-task. Reply with JSON only:
{"approve": true or false, "reason": "<one or two sentences>"}"""


def git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd or top(), text=True, capture_output=True, check=check)


_TOP: Path | None = None


def top() -> Path:
    global _TOP
    if _TOP is None:
        _TOP = Path(subprocess.run(["git", "-C", str(CONTENT), "rev-parse", "--show-toplevel"],
                                   text=True, capture_output=True, check=True).stdout.strip())
    return _TOP


def prefix() -> str:
    return CONTENT.resolve().relative_to(top().resolve()).as_posix()


def log(msg: str) -> None:
    print(f"[judge] {msg}", flush=True)


def candidates() -> list[tuple[str, str]]:
    out = git("ls-remote", REMOTE, "refs/heads/agent/*").stdout
    found = []
    for line in out.splitlines():
        sha, ref = line.split("\t")
        parts = ref.split("/")
        if len(parts) == 5 and parts[3] in ("hermes", "opencode", "jevx"):  # jevx = the Mac planner lane (plan branches)
            found.append((ref[len("refs/heads/"):], sha))
    shard = os.environ.get("HIVE_JUDGE_SHARD", "")  # "i/n": parallel judges take disjoint branch sets
    if re.fullmatch(r"\d+/\d+", shard):
        i, n = map(int, shard.split("/"))
        found = [f for f in found if int(hashlib.sha1(f[0].encode()).hexdigest(), 16) % n == i]
    return sorted(found)


def run_gates(wt: Path, branch: str, base_sha: str) -> list[str]:
    """Code gates. The gates themselves always come from main (this checkout), never from the branch, so a
    branch cannot pass by loosening them. Main's self-tests also run against the branch's code: a change that
    weakens an existing check fails a test that main already has."""
    c = wt / prefix()
    trusted = CONTENT / "scripts"
    shutil.copytree(CONTENT / "tests", c / "tests_main", dirs_exist_ok=True)
    problems = []
    diff = git("diff", "--name-only", f"{base_sha}...HEAD", cwd=wt).stdout
    steps = [
        ("lane scope", [sys.executable, str(trusted / "hive_gate.py"), "--branch", branch], diff),
        ("content gate", [sys.executable, str(trusted / "validate.py"), "--root", str(c)], None),
        ("main's self-tests on the branch", [sys.executable, "-m", "unittest", "discover", "-s", "tests_main"], None),
        ("branch self-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"], None),
        ("evidence gate", [sys.executable, str(trusted / "evidence_gate.py"), "--base", base_sha,
                           "--branch", branch, "--worktree", str(wt)], None),
    ]
    env = {**os.environ, "HIVE_IN_JUDGE": "1"}  # heavy end-to-end tests don't recurse into the judge
    # Content-only branches (no path under scripts/, tests/, ops/ except the receipt, .agents/, opencode.json, or
    # outside the content folder) cannot change what the self-tests exercise; the content, scope and evidence gates
    # still run. This keeps the judge at seconds per page instead of ~12 minutes (Mac, 2026-09-28: 47 branches queued).
    inner = [p[len(prefix()) + 1:] if p.startswith(prefix() + "/") else "/" + p for p in diff.split()]
    tooling = [p for p in inner if p.startswith(("/", "scripts/", "tests/", ".agents/", "opencode.json"))
               or (p.startswith("ops/") and not p.startswith(("ops/done/", "ops/plan/")) and p != "ops/tasks.toml")]
    # (the backlog and plan notes are data for the self-tests' fixed fixtures, not code: planner branches skip them too)
    if not tooling and os.environ.get("HIVE_JUDGE_FULL_TESTS") != "1":
        steps = [s for s in steps if "self-tests" not in s[0]]
    for name, cmd, stdin in steps:
        res = subprocess.run(cmd, cwd=c, input=stdin, text=True, capture_output=True, env=env)
        if res.returncode != 0:
            tail = "\n".join((res.stdout + res.stderr).strip().splitlines()[-8:])
            problems.append(f"{name} failed:\n{tail}")
    return problems


def llm_verdict(llm: free_agent.LLM, wt: Path, branch: str, base_sha: str) -> tuple[bool | None, str]:
    task_id = branch.rsplit("/", 1)[1]
    tasks = tomllib.loads((wt / prefix() / "ops" / "tasks.toml").read_text(encoding="utf-8")).get("task", [])
    task = next((t for t in tasks if t["id"] == task_id), {"id": task_id})
    receipt = wt / prefix() / "ops" / "done" / f"{task_id}.md"
    receipt_text = receipt.read_text(encoding="utf-8")[:5000] if receipt.exists() else "(no receipt)"
    diff = git("diff", f"{base_sha}...HEAD", "--", ".", f":!{prefix()}/ops/done", cwd=wt).stdout
    if len(diff) > MAX_DIFF:
        diff = diff[:MAX_DIFF] + f"\n[... diff truncated, {len(diff) - MAX_DIFF} more characters]"
    user = (f"## Task\n```json\n{json.dumps(task, ensure_ascii=False)}\n```\n\n## Receipt\n{receipt_text}\n\n"
            f"## Diff\n```diff\n{diff}\n```")
    try:
        msg = llm.chat([{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}],
                       max_tokens=300)
    except free_agent.NoProvider:
        return None, "no LLM provider available"
    text = msg.get("content") or ""
    match = re.search(r"\{.*\}", text, re.S)
    try:
        verdict = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        verdict = {}
    if not isinstance(verdict.get("approve"), bool):
        return False, f"judge reply was not a JSON verdict: {text[:200]!r}"
    return verdict["approve"], str(verdict.get("reason", ""))[:400] + f" (via {llm.last_route})"


def publish(branch: str, sha: str, reason: str) -> bool:
    """Squash the branch onto the latest main and push. Retries when main moved meanwhile."""
    subject = git("log", "-1", "--format=%s", sha).stdout.strip()
    for attempt in range(3):
        git("fetch", "--quiet", REMOTE, BASE)
        git("checkout", "--quiet", "--detach", "-f", f"{REMOTE}/{BASE}")
        res = git("merge", "--squash", sha, check=False)
        if res.returncode != 0:
            git("reset", "--quiet", "--hard", f"{REMOTE}/{BASE}")
            log(f"{branch}: merge conflict with {BASE}")
            return False
        gate = subprocess.run([sys.executable, str(CONTENT / "scripts" / "validate.py")],
                              text=True, capture_output=True)
        if gate.returncode != 0:
            git("reset", "--quiet", "--hard", f"{REMOTE}/{BASE}")
            log(f"{branch}: content gate fails after merging onto {BASE}")
            return False
        git("commit", "--quiet", "-m", subject, "-m", f"Judged-by: jevx-cloud. {reason}")
        if git("push", "--quiet", REMOTE, f"HEAD:refs/heads/{BASE}", check=False).returncode == 0:
            return True
        log(f"{branch}: {BASE} moved, retrying ({attempt + 1}/3)")
    return False


def delete_refs(*refs: str) -> None:
    for ref in refs:
        git("push", "--quiet", REMOTE, f":refs/heads/{ref}", check=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--publish", action="store_true", help="merge approved branches and push")
    ap.add_argument("--no-llm", action="store_true", help="code gates only")
    ap.add_argument("--limit", type=int, default=6, help="max branches per run")
    args = ap.parse_args(argv)

    git("fetch", "--quiet", REMOTE, BASE)
    llm = None if args.no_llm else free_agent.LLM(free_agent.load_config(), "jevx")
    plan_lines: list[str] = []
    now = dt.datetime.now(dt.timezone.utc)
    handled = 0
    for branch, sha in candidates():
        if handled >= args.limit:
            break
        if TRAILER not in git("log", "-1", "--format=%B", sha, check=False).stdout:
            continue  # a PR-mode branch: the Mac JEVX lane and merge_ready.sh handle those
        handled += 1
        task_id = branch.rsplit("/", 1)[1]
        git("fetch", "--quiet", REMOTE, f"refs/heads/{branch}")
        base_sha = git("merge-base", f"{REMOTE}/{BASE}", sha).stdout.strip()
        wt = Path(tempfile.mkdtemp(prefix="judge-"))
        try:
            git("worktree", "add", "--quiet", "--detach", str(wt), sha)
            problems = run_gates(wt, branch, base_sha)
            if problems:
                approve, reason = False, "code gates: " + " | ".join(p.splitlines()[0] for p in problems)
                for p in problems:
                    log(f"{branch}: {p}")
            elif llm is None:
                approve, reason = True, "code gates passed (LLM review off)"
            else:
                approve, reason = llm_verdict(llm, wt, branch, base_sha)
        finally:
            git("worktree", "remove", "--force", str(wt), check=False)
            shutil.rmtree(wt, ignore_errors=True)
        if approve is None:
            log(f"{branch}: deferred ({reason})")
            continue
        if approve and args.publish and publish(branch, sha, reason):
            log(f"{branch}: published. {reason}")
            plan_lines.append(f"- {now:%H:%M} published `{task_id}`: {reason}")
            delete_refs(branch, f"claim/{task_id}")
        elif args.publish:
            reason = reason if not approve else "approved but could not be merged cleanly onto main"
            log(f"{branch}: rejected. {reason}")
            plan_lines.append(f"- {now:%H:%M} rejected `{task_id}`: {reason}")
            delete_refs(branch)  # the claim stays until reaped: a cool-down before the task is retried
        else:
            log(f"{branch}: {'would publish' if approve else 'would reject'}. {reason}")

    if args.publish:
        git("fetch", "--quiet", REMOTE, BASE)
        git("checkout", "--quiet", "--detach", "-f", f"{REMOTE}/{BASE}")
        if plan_lines:
            plan = CONTENT / "ops" / "plan" / f"{now:%Y-%m-%d}.md"
            head = "" if plan.exists() else f"# Hive plan {now:%Y-%m-%d}\n"
            with plan.open("a", encoding="utf-8") as fh:
                fh.write(f"{head}\n## {now:%H:%M} UTC · cloud judge\n\n" + "\n".join(plan_lines) + "\n")
        subprocess.run([sys.executable, str(CONTENT / "scripts" / "validate.py"), "--write"],
                       capture_output=True, text=True)
        if git("status", "--porcelain").stdout.strip():
            git("add", "-A", prefix())
            git("commit", "--quiet", "-m", f"hive(jevx): regenerate index and log judge run {now:%Y-%m-%dT%H:%MZ}")
            if git("push", "--quiet", REMOTE, f"HEAD:refs/heads/{BASE}", check=False).returncode != 0:
                log("could not push the regenerated index (main moved); the next run will redo it")
    log(f"done: {handled} branch(es) judged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
