#!/usr/bin/env python3
"""Harvest: find the owner's past exam work scattered across the Mac and Google accounts, so the hive can merge it.

Everything this script writes stays on the Mac (~/.hive/harvest/). File paths and file contents are never
committed. The public backlog only ever sees an opaque item id (inv:xxxxxxxx) and the exam it relates to.

    harvest.py scan                 index candidate files (read-only) into ~/.hive/harvest/inventory.jsonl
    harvest.py summary              counts by family and risk
    harvest.py tasks --start 501    print ready-to-append tasks.toml entries (Mac-only, Hermes lane)
    harvest.py search "<words>"     find items (for agents, via the MCP tool harvest_search)
    harvest.py show inv:xxxxxxxx    local text excerpt of one item (MCP tool harvest_item)

Where it looks (existing folders only): Documents, Desktop, Downloads, code/Projects/dev folders, every Google
Drive for desktop mount (one per signed-in Google account), iCloud Drive, and ~/Hive-Inbox (unzip Google
Takeout exports there). Add more with HIVE_HARVEST_ROOTS=/path/a:/path/b.

Risk flags keep the hive honest: lecture transcripts and coaching-brand material are never turned into tasks
(copyright). Items with personal data are flagged so agents never copy them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tomllib
import zipfile
from pathlib import Path

CONTENT = Path(__file__).resolve().parents[1]
HIVE_HOME = Path(os.environ.get("HIVE_HOME", Path.home() / ".hive"))
OUT = HIVE_HOME / "harvest"
TEXT_EXT = {".md", ".markdown", ".txt", ".json", ".jsonl", ".csv", ".toml", ".yaml", ".yml", ".html", ".htm",
            ".tex", ".ipynb", ".srt", ".vtt"}
DOC_EXT = {".pdf", ".docx", ".gdoc", ".sqlite", ".db"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".cache", ".Trash", "build", "dist",
             "site-packages", ".npm", ".cargo", ".rustup", ".gradle", "Pods", "DerivedData", ".hive"}
MAX_BYTES = 50 * 1024 * 1024
GENERIC = ("syllabus", "exam pattern", "previous year", "pyq", "cutoff", "notification", "question paper",
           "mock test", "awesome", "study plan", "formula sheet", "revision")
COACHING = ("made easy", "madeeasy", "ace academy", "ace engineering", "gate academy", "unacademy", "physics wallah",
            "physicswallah", "testbook", "adda247", "byju", "vedantu", "allen career", "aakash", "drishti ias",
            "vision ias", "insightsonindia", "oliveboard", "gradeup", "ies master", "engineers academy")
TIMESTAMP = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?\b")
PERSONAL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\b(?:\+91[\s-]?)?[6-9]\d{9}\b|\b\d{4}\s\d{4}\s\d{4}\b")


def default_roots() -> list[Path]:
    home = Path.home()
    roots = [home / d for d in ("Documents", "Desktop", "Downloads", "code", "Projects", "dev", "Hive-Inbox")]
    roots += sorted((home / "Library" / "CloudStorage").glob("*")) if (home / "Library" / "CloudStorage").exists() else []
    roots.append(home / "Library" / "Mobile Documents" / "com~apple~CloudDocs")
    roots += [Path(p) for p in os.environ.get("HIVE_HARVEST_ROOTS", "").split(":") if p]
    return [r for r in roots if r.exists()]


STOP = {"exam", "and", "the", "main", "state", "test", "entrance", "recruitment", "group", "level", "officer",
        "grade", "assistant", "post", "posts", "service", "services", "combined", "india", "indian", "national",
        "central", "university", "staff", "selection", "teacher", "class", "general", "junior", "engineer"}


def load_registry() -> tuple[list[tuple[str, str, re.Pattern]], dict[str, str]]:
    reg = tomllib.loads((CONTENT / "registry" / "exams.toml").read_text(encoding="utf-8"))
    focus = {f["id"]: f["focus"] for f in reg.get("family", [])}
    exams = []
    for ex in reg.get("exam", []):
        words = {ex["id"].replace("-", " "), re.sub(r"\s*\(.*?\)", "", ex["name"].lower()).strip()}
        words |= {w for w in re.findall(r"[a-z]{3,}", ex["id"]) if w not in STOP}
        pattern = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")\b")
        exams.append((ex["id"], ex["family"], pattern))
    return exams, focus


def extract_text(path: Path, limit: int = 200_000) -> str:
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXT:
            text = path.read_text(encoding="utf-8", errors="replace")[:limit]
            if ext == ".ipynb":
                try:
                    cells = json.loads(text).get("cells", [])
                    text = "\n".join("".join(c.get("source", [])) for c in cells)[:limit]
                except (json.JSONDecodeError, AttributeError):
                    pass
            return text
        if ext == ".docx":
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", errors="replace")
            return re.sub(r"<[^>]+>", " ", xml)[:limit]
        if ext == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError:
                return ""
            reader = PdfReader(str(path))
            return "\n".join((p.extract_text() or "") for p in reader.pages[:15])[:limit]
        if ext == ".gdoc":  # Google Drive for desktop pointer: the document itself lives in Drive
            return path.read_text(encoding="utf-8", errors="replace")[:2000]
    except Exception:  # unreadable, locked or malformed files are common in personal folders
        return ""
    return ""


def classify(path: Path, text: str) -> str:
    low_path, low = str(path).lower(), text[:100_000].lower()
    if path.suffix.lower() in {".srt", ".vtt"} or "transcript" in low_path or len(TIMESTAMP.findall(text[:50_000])) >= 25:
        return "transcript"
    if any(brand in low_path or brand in low for brand in COACHING):
        return "third-party"
    if PERSONAL.search(text[:50_000]):
        return "personal"
    return "own"


def score(path: Path, text: str, exams: list) -> tuple[int, str, str]:
    hay = (str(path).lower().replace("_", " ").replace("-", " ") + "\n" + text[:100_000].lower())
    best, best_exam, best_family = 0, "", ""
    for eid, family, pattern in exams:
        hits = sum(len(m.split()) for m in pattern.findall(hay))  # "ssc cgl" outweighs a bare "ssc"
        if hits > best:
            best, best_exam, best_family = hits, eid, family
    generic = sum(hay.count(w) for w in GENERIC)
    return best * 3 + generic, best_exam, best_family


def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in TEXT_EXT | DOC_EXT:
                yield p


def cmd_scan(args: argparse.Namespace) -> int:
    exams, _ = load_registry()
    roots = [Path(r).expanduser() for r in args.roots] if args.roots else default_roots()
    OUT.mkdir(parents=True, exist_ok=True)
    seen: dict[str, dict] = {}
    denied = 0
    for root in roots:
        for path in walk(root):
            try:
                size = path.stat().st_size
                if size == 0 or size > MAX_BYTES:
                    continue
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except PermissionError:
                denied += 1
                continue
            except OSError:
                continue
            if digest in seen:
                seen[digest]["copies"] += 1
                continue
            text = extract_text(path)
            pts, exam, family = score(path, text, exams)
            if pts < args.min_score:
                continue
            seen[digest] = {"id": f"inv:{digest[:8]}", "path": str(path), "sha256": digest, "size": size,
                            "ext": path.suffix.lower(), "mtime": int(path.stat().st_mtime), "score": pts,
                            "exam": exam, "family": family, "risk": classify(path, text), "copies": 1,
                            "chars": len(text)}
    items = sorted(seen.values(), key=lambda i: -i["score"])
    with (OUT / "inventory.jsonl").open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item) + "\n")
    print(f"indexed {len(items)} candidate items from {len(roots)} roots into {OUT / 'inventory.jsonl'}")
    if denied:
        print(f"Operation not permitted on {denied} files: grant Full Disk Access to the scanning app "
              "(for cron: /usr/sbin/cron)")
    return 0


def load_inventory() -> list[dict]:
    inv = OUT / "inventory.jsonl"
    if not inv.exists():
        raise SystemExit("no inventory yet: run `harvest.py scan` on the Mac first")
    return [json.loads(line) for line in inv.open(encoding="utf-8") if line.strip()]


def cmd_summary(_: argparse.Namespace) -> int:
    items = load_inventory()
    by: dict[tuple[str, str], int] = {}
    for i in items:
        key = (i["family"] or "unmatched", i["risk"])
        by[key] = by.get(key, 0) + 1
    print(f"{len(items)} items ({sum(i['copies'] - 1 for i in items)} duplicate copies skipped)")
    for (family, risk), n in sorted(by.items()):
        print(f"  {family:22} {risk:12} {n}")
    return 0


def cmd_tasks(args: argparse.Namespace) -> int:
    _, focus = load_registry()
    existing = tomllib.loads((CONTENT / "ops" / "tasks.toml").read_text(encoding="utf-8")).get("task", [])
    used = {t["id"] for t in existing}
    already = {m for t in existing for m in re.findall(r"inv:[0-9a-f]{8}", t.get("title", ""))}
    n, made = args.start, 0
    for item in load_inventory():
        if made >= args.top:
            break
        if item["risk"] != "own" or not item["exam"] or item["id"] in already:
            continue  # transcripts, coaching material and personal files never become public work
        while f"T-{n:03d}" in used:
            n += 1
        page = f"exams/{item['family']}/{item['exam']}.md"
        print(f'''[[task]]
id = "T-{n:03d}"
lane = "hermes"
focus = "{focus.get(item['family'], 'india')}"
where = "mac"
priority = 2
title = "Harvest {item['id']} into {page} (owner's earlier work, local)"
accept = [
  "read the item with the harvest_item tool; use it only for structure, study advice and leads",
  "every exam fact re-verified against the official notification with fetch_url; nothing unverifiable is kept",
  "written in your own words; no local path, file name or personal data appears in the repository",
]
''')
        used.add(f"T-{n:03d}")
        made += 1
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    words = args.query.lower().split()
    hits = [i for i in load_inventory() if all(w in (i["exam"] + " " + i["family"] + " " + Path(i["path"]).name.lower())
                                                 for w in words)]
    for i in hits[: args.limit]:
        print(f"{i['id']}  {i['family']:20} {i['exam']:18} {i['risk']:12} score={i['score']}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    item = next((i for i in load_inventory() if i["id"] == args.id), None)
    if item is None:
        print(f"unknown item {args.id}")
        return 1
    if item["risk"] in ("transcript", "third-party"):
        print(f"{args.id} is flagged {item['risk']}: not usable for public content (copyright)")
        return 1
    text = extract_text(Path(item["path"]))
    note = " (contains personal data: never copy names, phone numbers, emails or IDs)" if item["risk"] == "personal" else ""
    print(f"{args.id} · exam={item['exam']} · family={item['family']}{note}\n")
    print(text[: args.chars])
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan")
    p.add_argument("--roots", nargs="*")
    p.add_argument("--min-score", type=int, default=3)
    p.set_defaults(fn=cmd_scan)
    sub.add_parser("summary").set_defaults(fn=cmd_summary)
    p = sub.add_parser("tasks")
    p.add_argument("--start", type=int, default=501)
    p.add_argument("--top", type=int, default=40)
    p.set_defaults(fn=cmd_tasks)
    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(fn=cmd_search)
    p = sub.add_parser("show")
    p.add_argument("id")
    p.add_argument("--chars", type=int, default=6000)
    p.set_defaults(fn=cmd_show)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
