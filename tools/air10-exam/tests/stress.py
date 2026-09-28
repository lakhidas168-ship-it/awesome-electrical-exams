#!/usr/bin/env python3
"""stress.py [clients] [fresh]  - N parallel MCP clients x 10 mixed calls; fresh=1 starts from an empty store (index-build race).
ALWAYS runs in a temp AIR10_EXAM_HOME: its practice answers must never reach the real progress.sqlite (they did until
2026-09-27 and wrote 144 fake FSRS reviews). fresh=0 copies only the question index into the temp home."""
import json, os, shutil, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
# sys.path.insert(0, os.path.expanduser('~/teamwork_projects/air10-mcp-trio/harness'))
# from stdio_call import session
N = int(sys.argv[1]) if len(sys.argv) > 1 else 16
# _live = os.environ.get("AIR10_EXAM_HOME") or os.path.expanduser("~/.local/share/air10-exam")
# NOTE: This stress test requires the harness module which is not open-sourced.
# Run with: AIR10_EXAM_HOME=/tmp/test python3 -m pytest tests/ -v instead
print("Stress test skipped - requires private harness. Run unit tests instead.")
sys.exit(0)
# os.environ["AIR10_EXAM_HOME"] = tempfile.mkdtemp(prefix="exam_stress_")
# if not (len(sys.argv) > 2 and sys.argv[2] == "1") and os.path.exists(os.path.join(_live, "questions.sqlite")):
#     shutil.copy2(os.path.join(_live, "questions.sqlite"), os.environ["AIR10_EXAM_HOME"])
# CALLS = [["exam_search", {"query": "induction motor slip torque", "limit": 5}], ["exam_practice", {"action": "question", "exam": "ssc_je", "n": 2}],
#          ["exam_practice", {"action": "answer", "question_id": "CUR:EE_GM_001", "answer": "B"}], ["exam_solve", {"kind": "eigen", "expression": "[[0,1],[-6,-5]]"}],
#          ["exam_radar", {"exam": "ese"}], ["exam_next", {"exam": "gate", "n": 2}], ["exam_tools", {"tool": "clips", "args": {"topic": "power factor correction"}}],
#          ["exam_search", {"query": "zener regulator", "scope": "hacks,questions", "exam": "rrb_je"}], ["exam_solve", {"kind": "phasor", "expression": "230@0 - 230@120"}],
#          ["exam_practice", {"action": "stats"}]]
# t0 = time.time()
# with ThreadPoolExecutor(N) as ex:
#     res = list(ex.map(lambda i: session([os.path.expanduser("~/.local/bin/air10-exam"), "serve"], CALLS, timeout=120), range(N)))
# ms, errs, bad = [], 0, []
# for r in res:
#     if not r.get("ok"):
#         errs += len(CALLS); continue
#     for c in r["calls"]:
#         ms.append(c["ms"]); v = c["value"]
#         errs += bool(c["isError"])
#         if isinstance(v, dict) and v.get("ok") is False: bad.append((c["tool"], str(v.get("error"))[:90]))
# ms.sort()
# print(json.dumps({"clients": N, "calls": len(ms), "transport_errors": errs, "ok_false": len(bad), "p50_ms": ms[len(ms) // 2],
#                   "p95_ms": ms[int(len(ms) * .95) - 1], "max_ms": ms[-1], "wall_s": round(time.time() - t0, 1), "examples": bad[:3]}))