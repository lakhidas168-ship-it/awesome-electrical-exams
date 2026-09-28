#!/usr/bin/env python3
"""Hive MCP server (stdio, JSON-RPC 2.0, stdlib only).

Gives any MCP-capable agent (OpenCode, Hermes, JEVX, Claude...) the same hive tools the cloud agent has, including
`fetch_url`, which records every fetch to $HIVE_FETCH_LOG so the receipt carries code-written evidence.

    python3 ops/mcp_server.py        # register as a local stdio MCP server (see opencode.json)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

CONTENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTENT / "scripts"))
sys.path.insert(0, str(CONTENT / "ops"))
import hive_gate  # noqa: E402
import validate  # noqa: E402

PROTOCOL = "2025-06-18"


def _run(*cmd: str) -> str:
    res = subprocess.run([sys.executable, *cmd], cwd=CONTENT, capture_output=True, text=True)
    return (res.stdout + res.stderr).strip() or f"(exit {res.returncode}, no output)"


def _registry() -> dict:
    return tomllib.loads((CONTENT / "registry" / "exams.toml").read_text(encoding="utf-8"))


def t_hive_status() -> str:
    return _run(str(CONTENT / "ops" / "agentctl.py"), "status")


def t_next_task(lane: str) -> str:
    return _run(str(CONTENT / "ops" / "agentctl.py"), "next", lane)


def t_validate_content() -> str:
    return _run(str(CONTENT / "scripts" / "validate.py"))


def t_check_lane_scope(branch: str, paths: list) -> str:
    problems = hive_gate.check(branch, [str(p) for p in paths])
    return "PASS" if not problems else "\n".join(problems)


def t_list_exams(family: str = "") -> str:
    reg = _registry()
    rows = []
    for ex in reg.get("exam", []):
        if family and ex["family"] != family:
            continue
        page = CONTENT / "exams" / ex["family"] / f"{ex['id']}.md"
        rows.append(f"{ex['id']:24} {ex['family']:20} {'page' if page.exists() else 'queued':6} {ex['name']}")
    return "\n".join(rows) or "no exams"


def t_exam_info(id: str) -> str:  # noqa: A002 - MCP argument name
    reg = _registry()
    ex = next((e for e in reg.get("exam", []) if e["id"] == id), None)
    if not ex:
        return f"unknown exam {id}"
    page = CONTENT / "exams" / ex["family"] / f"{id}.md"
    meta = validate.parse_frontmatter(page.read_text(encoding="utf-8"))[0] if page.exists() else None
    return json.dumps({"registry": ex, "page": page.relative_to(CONTENT).as_posix() if page.exists() else None,
                       "frontmatter": meta}, ensure_ascii=False, indent=2)


def t_fetch_url(url: str, offset: int = 0) -> str:
    import free_agent  # imported lazily: only this tool needs it
    if not url.startswith(("http://", "https://")):
        return "refused: only http(s) URLs"
    text, rec = free_agent.fetch(url, os.environ.get("HIVE_FETCH_LOG"))
    chunk = text[int(offset): int(offset) + 8000]
    return (f"status={rec.get('status')} official_domain={rec['official']} bytes={rec['bytes']} "
            f"recorded={'yes' if os.environ.get('HIVE_FETCH_LOG') else 'no (HIVE_FETCH_LOG not set)'}\n\n{chunk}")


def t_harvest_search(query: str) -> str:
    return _run(str(CONTENT / "ops" / "harvest.py"), "search", query)


def t_harvest_item(id: str) -> str:  # noqa: A002 - MCP argument name
    return _run(str(CONTENT / "ops" / "harvest.py"), "show", id)


def t_read_skill(name: str) -> str:
    path = CONTENT / ".agents" / "skills" / name / "SKILL.md"
    if not path.exists():
        names = sorted(p.parent.name for p in (CONTENT / ".agents" / "skills").glob("*/SKILL.md"))
        return f"unknown skill {name}; available: {', '.join(names)}"
    return path.read_text(encoding="utf-8")


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


S, I = {"type": "string"}, {"type": "integer"}
TOOLS = {
    "hive_status": (t_hive_status, "Backlog status: every task, its lane, focus and state, plus this hour's focus.",
                    _schema({}, [])),
    "next_task": (t_next_task, "Show the task a lane would pick next (does not claim it).",
                  _schema({"lane": S}, ["lane"])),
    "validate_content": (t_validate_content, "Run the content gate and return its report.", _schema({}, [])),
    "check_lane_scope": (t_check_lane_scope, "Check whether a set of changed paths is allowed for an agent branch.",
                         _schema({"branch": S, "paths": {"type": "array", "items": S}}, ["branch", "paths"])),
    "list_exams": (t_list_exams, "List registry exams (optionally one family) and whether each has a page.",
                   _schema({"family": S}, [])),
    "exam_info": (t_exam_info, "Registry entry, page path and frontmatter for one exam id.",
                  _schema({"id": S}, ["id"])),
    "fetch_url": (t_fetch_url, "Fetch a web page or PDF as text. Every fetch is recorded as evidence for the "
                               "receipt; cite exactly the URL you fetched under 'Official sources'.",
                  _schema({"url": S, "offset": I}, ["url"])),
    "harvest_search": (t_harvest_search, "Search the owner's local inventory of earlier exam work (Mac only). "
                                         "Returns item ids like inv:1a2b3c4d.", _schema({"query": S}, ["query"])),
    "harvest_item": (t_harvest_item, "Read one local inventory item (Mac only). Use it for structure and leads; "
                                     "re-verify every fact officially; never copy personal data or paths.",
                     _schema({"id": S}, ["id"])),
    "read_skill": (t_read_skill, "Read a hive skill (exam-page, module-page, harvest-import, hive-tooling, "
                                 "review-agent-work, hive-sync).", _schema({"name": S}, ["name"])),
}


def handle(req: dict) -> dict | None:
    method, rid = req.get("method"), req.get("id")
    if rid is None:
        return None  # notification (e.g. notifications/initialized): no reply
    if method == "initialize":
        version = (req.get("params") or {}).get("protocolVersion") or PROTOCOL
        result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "hive", "version": "1.0.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (_, d, s) in TOOLS.items()]}
    elif method == "tools/call":
        params = req.get("params") or {}
        entry = TOOLS.get(params.get("name", ""))
        if entry is None:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": f"unknown tool {params.get('name')}"}}
        try:
            text, is_error = entry[0](**(params.get("arguments") or {})), False
        except Exception as exc:  # report tool failures to the agent instead of crashing the server
            text, is_error = f"{type(exc).__name__}: {exc}", True
        result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    else:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            reply = handle(req)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
