#!/usr/bin/env python3
"""air10-exam - ONE MCP for Electrical Engineering competitive exams (GATE EE, UPSC ESE, SSC JE, RRB JE, State AE/JE, PSUs).

Merges Rajon's study stack into 6 tools (2026-09-27): JARVIS exam radar + formula/hacks vault + PYQ solver + drills,
air10-study-engine (FSRS/BKT), quiz masters, the 20,576-lecture vault + teacher library, notes, NotebookLM catalog.
Every source is opened READ-ONLY; the only thing this server writes is your own progress (air10-exam/progress.sqlite).
Every question carries provenance: curated_unverified (formerly curated_pyq: official year/shift not verified) | practice | upsc_cse_pyq. No synthetic/template questions (moved to Trash 2026-09-27).

  exam_search(query, scope, exam, subject)   one search over hacks, formulas, questions, 65k lecture transcripts, notes
  exam_next(exam, days_left, n)              what to study next: FSRS memory decay x exam weightage x days left
  exam_practice(action, ...)                 question -> answer (auto-checked, FSRS-scheduled, mistakes logged) | stats
  exam_solve(kind, ...)                      SymPy/SciPy solver: tf, eigen, laplace_inv, rlc, vr, phasor, linsolve, three_phase
  exam_radar(exam, subject)                  pattern + weightage of 6 exams; crosswalk = topics that pay in most exams
  exam_tools(tool, args)                     clips, notebook_route, crosswalk, sources, build_index, formula_check, units

CLI: air10-exam serve | build | search "query" | next gate | radar ese | solve tf "25/(s**2+6*s+25)" | selftest
     air10-exam practice question --exam gate --subject "Power Systems" --n 3   (also --topic/--provenance/--question-id/--answer/--rating)
"""
import datetime as dt
import hashlib
import importlib.util
import json
import logging
import math
import os
import re
import sqlite3
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

logging.disable(logging.INFO)
_CLI = __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] != "serve"
if not _CLI:
    try:
        from mcp.server.mcpserver import MCPServer as FastMCP  # mcp 2.x
    except ImportError:  # pragma: no cover
        from mcp.server.fastmcp import FastMCP  # mcp 1.x

H = Path.home()
def _env_path(key: str, default: str | Path | None) -> Path | None:
    """Get path from env var, expanding user. Returns None if env var not set and no valid default."""
    val = os.environ.get(key)
    if val:
        return Path(val).expanduser()
    if default:
        return Path(default).expanduser()
    return None

env = lambda k, d: _env_path(k, d)
DATA = env("AIR10_EXAM_DATA", "")
HOME = env("AIR10_EXAM_HOME", Path.cwd() / ".air10_exam_data")
# Filter out None values from env()
_src_raw = {
    "unified": env("AIR10_EXAM_UNIFIED", ""),
    "hacks": env("AIR10_EXAM_HACKS", ""),
    "notes": env("AIR10_EXAM_NOTES", ""),
    "registry": env("AIR10_EXAM_REGISTRY", ""),
    "radar": env("AIR10_EXAM_RADAR", ""),
    "study": env("AIR10_EXAM_STUDY", ""),
    "vault": env("AIR10_EXAM_VAULT", ""),
    "nlm_catalog": env("AIR10_EXAM_NLM_CATALOG", ""),
    "library": env("AIR10_EXAM_LIBRARY", ""),
    "exam_dag": env("AIR10_EXAM_DAG", ""),
}
SRC = {k: v for k, v in _src_raw.items() if v is not None and str(v).strip() and Path(str(v)).exists()}

_qbanks_raw = [
    (env("AIR10_EXAM_Q_CURATED", ""), "curated_sqlite", "curated_unverified"),
    (env("AIR10_EXAM_Q_TOP100", ""), "top100_json", "curated_unverified"),
    (env("AIR10_EXAM_Q_QUIZ", ""), "quiz_sqlite", "practice"),
    (env("AIR10_EXAM_Q_EMFT", ""), "quiz_sqlite", "practice"),
    (env("AIR10_EXAM_Q_UPSC", ""), "upsc_sqlite", "upsc_cse_pyq"),
    (env("AIR10_EXAM_Q_OFFICIAL", ""), "official_sqlite", "official_pyq"),
    (env("AIR10_EXAM_Q_COLLECTED", ""), "pyq_sqlite", "pyq_collected"),
]
QBANKS = [(p, k, pr) for p, k, pr in _qbanks_raw if p is not None and str(p).strip() and Path(str(p)).exists()]
try:  # ESE official bank lives in a separate source module (task 02, 2026-09-27): no bank-table edits needed
    try:
        from ese_official import EXTRA_QBANKS as _ESE_QBANKS
    except ImportError:  # serve mode: sibling dir may not be on sys.path
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location("ese_official", Path(__file__).parent / "ese_official.py")
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _ESE_QBANKS = _mod.EXTRA_QBANKS
    QBANKS = QBANKS + [b for b in _ESE_QBANKS if b not in QBANKS]
except (ImportError, OSError):
    pass
QINDEX = HOME / "questions.sqlite"
PROGRESS = HOME / "progress.sqlite"
PROVENANCE_NOTE = {"official_pyq": "OFFICIAL GATE question + final answer key from the organizing IIT (figures not reproduced: open the PDF page)",
                   "curated_unverified": "curated local question; official PYQ origin and answer not verified",
                   "pyq_collected": "previous-year question copied from a public paper/solution PDF (coaching copy of an official paper: ACE / MADE EASY / Zollege / Collegedunia / Scribd); answer only as stated in that document - verify",
                   "practice": "practice question written from teacher lectures (not an official PYQ)",
                   "upsc_cse_pyq": "UPSC CSE previous-year question (not Electrical)",
                   }
EXAMS = ["gate", "ese", "ssc_je", "rrb_je", "state_ae_je", "psu"]
SUBJECTS = ["Electrical Machines", "Power Systems", "Control Systems", "Power Electronics", "Circuits & Network Theory",
            "Analog & Digital Electronics", "Measurement & Instrumentation", "Electromagnetic Fields", "Signals & Systems",
            "Engineering Mathematics", "Basic Electrical & Circuit Laws", "Utilization & Estimation"]
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
mcp = SimpleNamespace(tool=lambda: (lambda f: f)) if _CLI else FastMCP("air10-exam", version=SOURCE_SHA256[:12])
_tl = threading.local()
_lock = threading.Lock()


# ---------------------------------------------------------------- helpers
def _ro(path):
    conns = getattr(_tl, "conns", None) or {}
    _tl.conns = conns
    p = str(path)
    stamp = (Path(path).stat().st_dev, Path(path).stat().st_ino)
    if p in conns and conns[p][0] != stamp:
        conns.pop(p)[1].close()
    if p not in conns:
        c = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        c.row_factory = sqlite3.Row
        conns[p] = (stamp, c)
    return conns[p][1]


def _rw():
    HOME.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(PROGRESS, timeout=10)
    c.execute("pragma journal_mode=wal")
    c.executescript("""create table if not exists reviews(qid text, ts real, rating int, correct int, answer text, topic text, exam text);
        create table if not exists cards(qid text primary key, topic text, subject text, card_json text, due text, updated real);
        create table if not exists mistakes(qid text, ts real, topic text, kind text, note text);
        create table if not exists attempt_receipts(attempt_id text primary key, fingerprint text not null, result_json text not null);""")
    return c


def _safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:  # never crash the server
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:400]}"}


_STOP = set("a an the of in on for to and or is are was what which how why when with by from at as be this that it its "
            "ka ki ke hai kya kaise se me mein aur".split())


def _fts(q, max_terms=8):
    """Free text -> safe FTS5 OR query of quoted terms (no syntax errors from user punctuation)."""
    terms = [t for t in re.findall(r"[A-Za-z0-9]+", q.lower()) if t not in _STOP and len(t) > 1][:max_terms]
    return " OR ".join(f'"{t}"' for t in terms) or '"electrical"'


def _clip(s, n=260):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n - 1] + "…"


def _exists(p):
    return Path(p).exists()


def _exam_tags(raw, default="gate"):
    """Free exam label ('🔥 GATE EE / UPSC ESE / PGCIL', 'RRB', 'STATE_AE_JE') -> '|gate|ese|psu|' (one question, many exams)."""
    t, tags = str(raw or "").lower(), []
    for tag, keys in (("gate", ("gate",)), ("ese", ("ese", "ies", "upsc")), ("ssc_je", ("ssc",)), ("rrb_je", ("rrb",)),
                      ("state_ae_je", ("state", "uppcl", "mpsc", "tnpsc", "rpsc", "apsc", "wbpsc", "msedcl", " ae", "_ae")),
                      ("psu", ("psu", "isro", "barc", "pgcil", "ntpc", "bhel", "drdo", "coal india", "gail", "sail", "iocl"))):
        if any(k in t for k in keys):
            tags.append(tag)
    return "|" + "|".join(tags or [default]) + "|"


def _norm_exam(e):
    e = (e or "").lower().replace(" ", "_").replace("-", "_")
    return {"gate_ee": "gate", "upsc_ese": "ese", "ies": "ese", "sscje": "ssc_je", "rrbje": "rrb_je", "state": "state_ae_je",
            "ae": "state_ae_je", "je": "ssc_je", "state_ae": "state_ae_je", "psus": "psu"}.get(e, e)


# ---------------------------------------------------------------- question index (built from all banks, provenance kept)
def _load_bank(path, kind, prov):
    rows = []
    if not _exists(path):
        return rows
    if kind == "top100_json":
        d = json.loads(Path(path).read_text())
        items = d if isinstance(d, list) else (d.get("questions") or next(iter(d.values())))
        for it in items:
            opts = it.get("options") or []
            if isinstance(opts, dict):
                opts = [f"{k}) {v}" for k, v in opts.items()]
            rows.append(dict(qid=f"T100:{it.get('id')}", exam="|ssc_je|", subject=it.get("pillar_name") or it.get("pillar") or "",
                             topic=it.get("subtopic") or it.get("microtopic") or "", stem=it.get("question_text") or it.get("question_stem") or "",
                             options=[str(o) for o in opts], answer=str(it.get("correct_option") or ""),
                             explanation=_clip(it.get("step_by_step_solution") or "", 1500), year=None, video="", prov=prov))
        return rows
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    tabs = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    if kind == "curated_sqlite" and "questions" in tabs:
        for r in con.execute("select * from questions"):
            r = dict(r)
            rows.append(dict(qid=f"CUR:{r['id']}", exam=_exam_tags(r.get("exam")),
                             subject=r.get("subject") or "", topic=r.get("topic") or r.get("subtopic") or "", stem=r.get("question_text") or "",
                             options=_jl(r.get("options_json")), answer=str(r.get("correct_answer") or ""),
                             explanation=_clip(r.get("explanation") or r.get("solution") or "", 1500), year=r.get("year"), video="", prov=prov, source_ref=r.get("source_reference") or str(path)))
    elif kind == "quiz_sqlite":
        for t in ("quiz_questions_catalog", "power_systems_10k_questions", "electrical_machines_10k_catalog", "eem_10k_questions"):
            if t not in tabs:
                continue
            for r in con.execute(f"select * from {t}"):
                r = dict(r)
                rows.append(dict(qid=f"QZ:{Path(path).stem}:{t}:{r.get('question_id') or r.get('id')}", exam=_exam_tags(r.get("exam_tag") or r.get("exam_frequency")),
                                 subject=r.get("module_title") or r.get("round_title") or "", topic=r.get("topic") or "",
                                 stem=r.get("question_text") or r.get("stem") or "", options=_jl(r.get("options_json")),
                                 answer=str(r.get("correct_index")) if r.get("correct_index") is not None else "",
                                 explanation=_clip(r.get("explanation") or "", 1200), year=None, video=r.get("youtube_video_id") or "", prov=prov))
    elif kind == "official_sqlite" and "questions" in tabs:
        overlay = _official_stems(path)   # OCR stems for image-only PDFs; official_pyq.sqlite stays read-only
        for r in con.execute("select * from questions"):
            r = dict(r); pages = json.loads(r["pages"] or "[]")
            stem, opts, fig = r["stem"] or "", _jl(r["options_json"]), int(r["has_figure"] or 0)
            ov = overlay.get(r["id"])
            if ov:
                if not stem.strip() and ov["stem"].strip():
                    stem = ov["stem"]   # OCR stem fills the empty image-only row (key row untouched)
                if not opts and ov["options"]:
                    opts = ov["options"]
                fig = max(fig, ov["needs_figure"])
            note = f" [figure in the official paper: open page {pages[0]} of {Path(r['pdf']).name}]" if fig and pages else ""
            org = r["organizer"] or ""
            tag = "ESE" if (org == "UPSC" or "|ese|" in str(r["exam"])) else "GATE"
            key = r["answer_key"] or ""
            keybit = f"key: {key}" if key else "official key not on upsc.gov.in live pages (verified 2026-09-27)"
            branch = "COMMON" if r.get("section") == "GS" else "EE"
            rows.append(dict(qid=r["id"], exam=r["exam"], subject=r["l2"] or "", topic=r["l3"] or "", stem=stem + note,
                             options=opts, answer=key, year=r["year"], video="", prov=prov,
                             explanation=f"Official {r['qtype']} ({r['marks']} mark), {keybit} - {tag} {r['year']} {org}",
                             source_ref=f"{r['source_url']}#page={pages[0] if pages else 1} ; key {r['key_url']}",
                             figure=fig, branch=branch, plabel=_build_plabel(r["id"], r.get("section"), r.get("qno"))))
    elif kind == "pyq_sqlite" and "questions" in tabs:
        tag = {"GATE": "|gate|", "ESE": "|ese|", "SSC_JE": "|ssc_je|", "RRB_JE": "|rrb_je|", "APSC": "|state_ae_je|", "STATE_AE_JE": "|state_ae_je|", "PSU": "|psu|"}
        for r in con.execute("select * from questions where length(stem) > 20 and exam <> 'UNKNOWN' and coalesce(l2, '') <> 'MECHANICAL_CIVIL'"):   # not Rajon's branch
            r = dict(r)
            expl = _clip(r["explanation"] or "", 900)
            if r["official"]:   # coaching copy of an official paper (ACE / MADE EASY / Zollege / Collegedunia / Scribd): keep the stated answer, never official_pyq
                expl = (expl + " [coaching copy of official paper: answer as stated in the source document - verify]").strip()
            rows.append(dict(qid=f"PYQ:{r['id']}", exam=tag.get(r["exam"], "|gate|"), subject=r.get("l2") or r["branch"], topic=r.get("l3") or "",
                             stem=r["stem"] + (" [figure in source PDF]" if r["has_figure"] else ""), options=_jl(r["options_json"]),
                             answer=r["answer"] or "", year=r["year"], video="", explanation=expl, prov=prov,
                             source_ref=f"{r['source_url']} ({r['source_title']})",
                             figure=int(r["has_figure"] or 0), branch=r["branch"] or "UNKNOWN", plabel=None))
    elif kind == "upsc_sqlite" and "pyq_questions" in tabs:
        for r in con.execute("select * from pyq_questions"):
            r = dict(r)
            rows.append(dict(qid=f"UPSC:{r['id']}", exam="|upsc_cse|", subject=r.get("topic") or "", topic=r.get("subtopic") or "",
                             stem=r.get("stem") or "", options=_jl(r.get("options_json")), answer=str(r.get("answer") or ""),
                             explanation=_clip(r.get("explanation") or "", 1200), year=r.get("year"), video="", prov=prov))
    con.close()
    return rows


def _jl(s):
    try:
        v = json.loads(s) if isinstance(s, str) else (s or [])
    except ValueError:
        return []
    if isinstance(v, dict):
        return [f"{k}) {x}" for k, x in v.items()]
    return [str(x) for x in v] if isinstance(v, list) else []


def _official_stems(official_path):
    """qid -> {stem, options, needs_figure} OCR overlay for image-only official PDFs (2026-09-27).

    The OCR lives in a SEPARATE read-only file (sibling official_stems.sqlite, or AIR10_EXAM_Q_STEMS);
    official_pyq.sqlite itself is never written. Returns {} when the file is absent so the build
    works with or without the overlay."""
    try:
        cand = os.environ.get("AIR10_EXAM_Q_STEMS") or str(Path(official_path).parent / "official_stems.sqlite")
        if not Path(cand).exists():
            return {}
        c = sqlite3.connect(f"file:{cand}?mode=ro", uri=True, timeout=5)
        try:
            tabs = {r[0] for r in c.execute("select name from sqlite_master where type='table'")}
            if "stems" not in tabs:
                return {}
            out = {}
            for r in c.execute("select qid, stem, options_json, needs_figure from stems"):
                out[r[0]] = {"stem": r[1] or "",
                             "options": _jl(r[2]),
                             "needs_figure": int(r[3] or 0)}
            return out
        finally:
            c.close()
    except (sqlite3.Error, OSError, ValueError):
        return {}


# ---------------------------------------------------------------- audit fixes (2026-09-27)
# official_pyq = ONLY $AIR10_EXAM_Q_OFFICIAL rows (organizer PDFs).
# Everything from pyq.sqlite is a coaching copy -> pyq_collected, even when answer_source says 'official'.
GATE_NON_EE_BRANCHES = ("EC", "IN", "CS", "DA")   # pyq.sqlite branches that are not Rajon's EE paper
_YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YT_HEX = re.compile(r"^[0-9a-f]{11}$")   # 11-hex ids are content hashes, not YouTube ids (library convention)


def _build_plabel(qid, section, qno):
    """Printed paper number, e.g. GATE2018_EE_Q11 -> 'EE Q.1', GATE2016_EE_S2_Q54 -> 'EE Set-2 Q.44'.
    The source DB stores the overall number (GA Q1-10, then EE); the paper prints the section number."""
    try:
        n = int(qno)
    except (TypeError, ValueError):
        return None
    m = re.search(r"_S(\d)_", str(qid or ""))
    suffix = f" Set-{m.group(1)}" if m else ""
    if (section or "") == "GA":
        return f"GA{suffix} Q.{n}"
    if (section or "") == "EE":
        return f"EE{suffix} Q.{n - 10}" if n > 10 else f"EE{suffix} Q.{n}"
    return None


_ERRATA = {}


def _errata():
    """qid -> override from errata.json (lives next to this file, ships with the code)."""
    global _ERRATA
    if not _ERRATA:
        try:
            _ERRATA = json.loads((Path(__file__).parent / "errata.json").read_text())
        except (OSError, ValueError):
            _ERRATA = {}
    return _ERRATA


def _apply_errata(rows):
    """Apply errata.json overrides to loaded bank rows (sources stay read-only). Returns (applied, skipped)."""
    applied, skipped = [], []
    by_qid = {}
    for r in rows:
        by_qid.setdefault(r["qid"], r)   # dupes resolved later; errata targets the first (official wins, see below)
    for qid, e in _errata().items():
        if qid.startswith("_"):
            continue
        r = by_qid.get(qid)
        if r is None:
            skipped.append(qid)
            continue
        if e.get("action") == "unusable":
            r["figure"] = 1
            applied.append(qid)
        elif e.get("action") == "fix_stem" and e.get("stem"):
            r["stem"] = e["stem"]
            applied.append(qid)
        elif e.get("action") == "fix_stem" and e.get("stem_from"):
            if r["stem"].count(e["stem_from"]) >= 1:
                r["stem"] = r["stem"].replace(e["stem_from"], e.get("stem_to", ""))
                applied.append(qid)
            else:
                skipped.append(qid)
        else:
            skipped.append(qid)
    return applied, skipped


def _yt_id(raw):
    """A stored video reference -> real 11-char YouTube id, or None (never a fake/placeholder)."""
    v = re.sub(r"^(yt:|https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/))", "", str(raw or "").strip())
    v = v.split("&")[0].split("#")[0].strip()
    if _YT_ID.match(v) and not _YT_HEX.match(v):
        return v
    return None


def _yt_url(raw):
    vid = _yt_id(raw)
    return f"https://youtu.be/{vid}" if vid else None


def _watch_url(url):
    """A library/lecture URL -> canonical youtu.be URL with a real 11-char id, or None (drops TEACHER_* placeholders)."""
    m = re.search(r"[?&]v=([^&#\s]+)", str(url or ""))
    cand = m.group(1) if m else url
    return _yt_url(cand)


# Radar overlays (2026-09-27 audit): the external radar file covers 8 GATE subjects and 8 ESE rows.
# GATE additions use the official paper structure (GA 15M + Math 13M are fixed in the pattern; EMFT /
# Measurements / Digital are typical recent-paper ranges - GATE publishes no finer official split).
# ESE: UPSC publishes no per-subject weights at all, so every ESE row below is estimated=True.
GATE_EXTRA_WEIGHTAGE = [
    ("General Aptitude", "15M", "Verbal + numerical + spatial (Q1-10, fixed 15 marks)"),
    ("Electromagnetic Fields", "2-4M", "GATE Section 3: Maxwell, transmission lines, Smith chart (typical recent-paper range)"),
    ("Measurement & Instrumentation", "3-5M", "GATE Section 8: bridges, meters, CRO, transducers (typical recent-paper range)"),
    ("Digital Electronics", "2-4M", "GATE Section 9 second half: logic families, counters, ADC/DAC (typical recent-paper range)"),
]
ESE_EXTRA_WEIGHTAGE = [
    ("Engineering Mathematics", "4-6%", "Linear algebra, calculus, complex variables (estimated: UPSC publishes no split)"),
    ("Electrical Materials", "3-5%", "Bands, conductors, superconductivity (estimated: UPSC publishes no split)"),
    ("Computer Fundamentals", "2-4%", "Number systems, 8085/8086 basics (estimated: UPSC publishes no split)"),
    ("Basic Electronics Engineering", "3-5%", "Diodes, BJT biasing, small-signal (estimated: UPSC publishes no split)"),
    ("Systems & Signal Processing", "4-6%", "LTI, Fourier/Z, sampling, DSP basics (estimated: UPSC publishes no split)"),
]
# provenance insert order: the official organizer row always wins a normalized-stem duplicate (audit fix 4)
PROV_PRIORITY = {"official_pyq": 0, "curated_unverified": 1, "pyq_collected": 2, "practice": 3, "upsc_cse_pyq": 4}


def _norm_stem(stem):
    """Normalized-stem hash: empty/garbled stubs hash to '' so every one of them is dropped as a dupe."""
    raw = re.sub(r"[^a-z0-9]+", " ", (stem or "").lower()).strip()[:220]
    return hashlib.sha256(raw.encode()).hexdigest()[:16] if len(raw) >= 8 else ""


def _build_index():
    """(Re)build questions.sqlite from every bank. Idempotent; takes ~2 s for ~11.7k questions."""
    t0 = time.time()
    HOME.mkdir(parents=True, exist_ok=True)
    tmp = QINDEX.with_name(f"questions.{uuid.uuid4().hex}.tmp")   # per-process temp: a manual rebuild never clobbers another
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript("""create table q(qid text primary key, exam text, subject text, topic text, stem text, options text,
        answer text, explanation text, year int, video text, prov text, source_ref text,
        figure int default 0, branch text default '', plabel text);
        create virtual table qfts using fts5(qid unindexed, subject, topic, stem, content='q', content_rowid='rowid', tokenize='porter unicode61');""")
    counts, all_rows = {}, []
    for path, kind, prov in QBANKS:
        try:
            rows = _load_bank(path, kind, prov)
        except Exception as e:
            counts[str(Path(path).name)] = f"error {type(e).__name__}: {e}"
            continue
        all_rows += rows
        counts[str(Path(path).name)] = len(rows)
    errata_applied, errata_skipped = _apply_errata(all_rows)
    seen, dupes = set(), 0
    for r in sorted(enumerate(all_rows), key=lambda t: (PROV_PRIORITY.get(t[1]["prov"], 9), t[0])):
        r = r[1]
        key = _norm_stem(r["stem"])
        if len(key) < 8 or key in seen:   # same question stored in two banks -> the official organizer row wins
            dupes += 1
            continue
        seen.add(key)
        con.execute("insert or ignore into q values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (r["qid"], r["exam"], r["subject"], r["topic"], r["stem"],
                    json.dumps(r["options"], ensure_ascii=False), r["answer"], r["explanation"], r["year"], r["video"], r["prov"], r.get("source_ref") or "",
                    int(r.get("figure") or 0), r.get("branch") or "", r.get("plabel")))
    con.execute("insert into qfts(qfts) values('rebuild')")
    total = con.execute("select count(*) from q").fetchone()[0]
    con.commit(); con.close()
    errors = {key: value for key, value in counts.items() if isinstance(value, str)}
    if errors:
        tmp.unlink(missing_ok=True)
        return {"ok": False, "error": "source read failed; existing index preserved", "sources": counts}
    os.replace(tmp, QINDEX)
    return {"ok": True, "questions": counts, "total": total, "dupes_dropped": dupes,
            "errata_applied": errata_applied, "errata_skipped": errata_skipped,
            "source_rows": sum(v for v in counts.values() if isinstance(v, int)), "seconds": round(time.time() - t0, 2)}


def build_index():
    import fcntl
    HOME.mkdir(parents=True, exist_ok=True)
    with _lock, open(HOME / ".build.lock", "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        return _build_index()


def _qdb():
    if not QINDEX.exists():
        result = build_index()
        if not result.get("ok"):
            raise RuntimeError(result["error"])
    else:
        try:
            cols = {r[1] for r in _ro(QINDEX).execute("pragma table_info(q)")}
            if not {"figure", "branch", "plabel"} <= cols:   # stale pre-audit index: rebuild with the new columns
                old = getattr(_tl, "conns", {}).pop(str(QINDEX), None)
                if old is not None:
                    try:
                        old[1].close()
                    except Exception:
                        pass
                result = build_index()
                if not result.get("ok"):
                    raise RuntimeError(result["error"])
        except sqlite3.Error:
            result = build_index()
            if not result.get("ok"):
                raise RuntimeError(result["error"])
    return _ro(QINDEX)


def _answer_index(q):
    """An explicit stored option index/letter or exact option text; never fuzzy substring guessing."""
    a, opts = (q["answer"] or "").strip(), json.loads(q["options"] or "[]")
    if not opts or not a:
        return None
    if a.isdigit():
        return int(a) if int(a) < len(opts) else None
    if re.fullmatch(r"[A-Da-d]", a):
        index = "abcd".index(a.lower())
        return index if index < len(opts) else None
    normalize = lambda text: re.sub(r"^[A-Da-d][).]\s*", "", text.strip()).casefold()
    matches = [i for i, option in enumerate(opts) if normalize(option) == normalize(a)]
    return matches[0] if len(matches) == 1 else None


# ---------------------------------------------------------------- 1. search
SCOPES = ("hacks", "questions", "segments", "transcripts", "lectures", "insights", "notes", "notebooklm", "tools")


def _search_source(query, scope="all", exam="", subject="", limit=8):
    limit = max(1, min(int(limit or 8), 25))
    want = SCOPES if scope in ("", "all") else tuple(s.strip() for s in scope.split(","))
    fq, hits, used = _fts(f"{query} {subject}".strip()), [], []
    fqv = f'({fq}) NOT "could not retrieve a transcript"' if fq else fq   # 4,289 vault rows are YouTube IP-block errors, not lectures

    junk = _junk_ids()

    def add(src, rows, score_i=0):
        rows = [r for r in rows if str(r.get("id", "")) not in junk and str(r.get("video_id", "")) not in junk]   # junk.py: 2 models = unrelated
        for rank, r in enumerate(rows):
            hits.append({"src": src, "rank": rank, **r}); used.append(src) if src not in used else None

    if "hacks" in want and _exists(SRC["hacks"]):
        rows = _ro(SRC["hacks"]).execute("select h.hack_id, h.subject, h.subtopic, h.exam_target, h.title, h.core_formula, h.shortcut_trick, "
                                         "h.cognitive_trap from exam_hacks_fts f join exam_hacks h on h.rowid=f.rowid "
                                         "where exam_hacks_fts match ? order by rank limit ?", (fq, limit)).fetchall()
        add("hack", [{"id": r["hack_id"], "title": r["title"], "subject": r["subject"], "exam": r["exam_target"],
                      "formula": _clip(r["core_formula"], 200), "trick": _clip(r["shortcut_trick"], 220), "trap": _clip(r["cognitive_trap"], 160)} for r in rows])
    if _exists(SRC["unified"]) and ({"hacks", "transcripts", "tools"} & set(want)):
        types = [t for s, t in (("hacks", "HACK"), ("transcripts", "TRANSCRIPT"), ("tools", "TOOL")) if s in want]
        rows = _ro(SRC["unified"]).execute(
            f"select entity_type, entity_id, domain_or_subject, title, snippet(unified_super_fts, 4, '«', '»', '…', 24) sn from unified_super_fts "
            f"where unified_super_fts match ? and entity_type in ({','.join('?' * len(types))}) order by rank limit ?", (fq, *types, limit)).fetchall()
        add("unified", [{"type": r["entity_type"].lower(), "id": r["entity_id"], "title": _clip(r["title"], 140), "subject": r["domain_or_subject"],
                         "snippet": _clip(r["sn"], 260), **({"url": f"https://youtu.be/{r['entity_id']}"} if r["entity_type"] == "TRANSCRIPT"
                                                            and re.fullmatch(r"[\w-]{11}", r["entity_id"] or "") else {})} for r in rows])
    if "lectures" in want and _exists(SRC["vault"]):   # 20,576 rows, 13,379 with real text (audit 2026-09-27: teacher_library.meta)
        rows = _ro(SRC["vault"]).execute(
            "select video_id, title, channel, topic, snippet(transcripts_fts, 5, '«', '»', '…', 24) sn from transcripts_fts "
            "where transcripts_fts match ? order by rank limit ?", (fqv, limit)).fetchall()
        add("lecture", [{"id": r["video_id"], "title": _clip(r["title"], 140), "channel": r["channel"], "subject": r["topic"], "snippet": _clip(r["sn"], 260),
                         **({"url": f"https://youtu.be/{r['video_id']}"} if re.fullmatch(r"[\w-]{11}", r["video_id"] or "") else {})} for r in rows])
    if "lectures" in want and _exists(SRC["library"]):   # teacher library: raw transcripts that were only on disk
        dom = "and v.domain='ELECTRICAL_ENGINEERING' " if exam or subject else ""
        stubs = ("and v.video_id not in (select video_id from stub_manifest where text_after_manifest = 0) "   # 21,339 manifest-only rows
                 if _ro(SRC["library"]).execute("select 1 from sqlite_master where name='stub_manifest'").fetchone() else "")
        rows = _ro(SRC["library"]).execute(
            f"select v.video_id, v.title, v.domain, v.url, snippet(videos_fts, 3, '«', '»', '…', 24) sn from videos_fts f join videos v on v.rowid=f.rowid "
            f"where videos_fts match ? {dom}{stubs}order by rank limit ?", (fq, limit)).fetchall()
        real_yt = lambda v: bool(re.fullmatch(r"[\w-]{11}", v or "")) and not re.fullmatch(r"[0-9a-f]{11}", v)   # all-hex ids are hash ids, not YouTube
        add("library", [{"id": r["video_id"], "title": ("" if (r["title"] or "").startswith("URL:") else _clip(r["title"], 140)) or f"lecture {r['video_id']}",
                         "domain": r["domain"], "snippet": _clip(r["sn"], 260),
                         **({"url": f"https://youtu.be/{r['video_id']}"} if real_yt(r["video_id"]) else {})} for r in rows])
    if "notes" in want and _exists(SRC["notes"]):
        rows = _ro(SRC["notes"]).execute(
            "select doc_id, vault_source, domain, subtopic, title, url, local_path, snippet(jarvis_master_fts, 5, '«', '»', '…', 24) sn "
            "from jarvis_master_fts where jarvis_master_fts match ? order by rank limit ?", (fq, limit)).fetchall()
        add("note", [{"id": r["doc_id"], "title": _clip(r["title"], 140), "subject": r["domain"], "topic": r["subtopic"], "snippet": _clip(r["sn"], 260),
                      **({"url": r["url"]} if r["url"] else {}), **({"path": str(r["local_path"]).replace(str(H), "~")} if r["local_path"] else {})} for r in rows])
    if "segments" in want and _exists(SRC["vault"]):   # exact moment inside a lecture (763k timed segments)
        rows = _ro(SRC["vault"]).execute(
            "select f.segment_id, f.video_id, f.video_title, f.channel, s.start_time_s st, snippet(segments_fts, 4, '«', '»', '…', 22) sn "
            "from segments_fts f join transcript_segments s on s.segment_id=f.segment_id where segments_fts match ? order by rank limit ?", (fqv, limit)).fetchall()
        add("segment", [{"id": r["segment_id"], "title": _clip(r["video_title"], 120), "channel": r["channel"], "at_s": int(r["st"] or 0),
                         "snippet": _clip(r["sn"], 240), **({"url": f"https://youtu.be/{r['video_id']}?t={int(r['st'] or 0)}"}
                                                            if re.fullmatch(r"[\w-]{11}", r["video_id"] or "") else {"video_id": r["video_id"]})} for r in rows])
    if "insights" in want and _exists(SRC["vault"]):
        rows = _ro(SRC["vault"]).execute("select h.insight_id, h.canonical_subject, h.micro_concept, h.title, h.hacks_json, h.exam_traps_json, "
                                         "h.governing_formulas_json from hierarchy_fts f join hierarchical_insights h on h.insight_id=f.insight_id "
                                         "where hierarchy_fts match ? order by rank limit ?", (fq, limit)).fetchall()
        add("insight", [{"id": r["insight_id"], "subject": r["canonical_subject"], "concept": r["micro_concept"], "title": _clip(r["title"], 120),
                         "hacks": _clip(r["hacks_json"], 260), "traps": _clip(r["exam_traps_json"], 200), "formulas": _clip(r["governing_formulas_json"], 200)} for r in rows])
    if "notebooklm" in want and _exists(SRC["nlm_catalog"]):
        rows = _ro(SRC["nlm_catalog"]).execute("select s.account, s.notebook_id, s.notebook_title, s.title, s.url, s.subject, s.micro_topic, s.channel_teacher "
                                               "from sources_fts f join sources s on s.rowid=f.rowid where sources_fts match ? order by rank limit ?", (fq, limit)).fetchall()
        add("nlm_source", [{"notebook": _clip(r["notebook_title"], 90), "notebook_id": r["notebook_id"], "account": (r["account"] or "").split("@")[0],
                            "source": _clip(r["title"], 120), "subject": r["subject"], "topic": r["micro_topic"], "teacher": r["channel_teacher"],
                            **({"url": r["url"]} if r["url"] else {})} for r in rows])
    if "questions" in want:
        ex = _norm_exam(exam)
        sql = ("select q.qid, q.exam, q.subject, q.topic, q.stem, q.prov, q.year, q.source_ref, q.branch, q.plabel from qfts f join q on q.rowid=f.rowid where qfts match ? "
               + ("and q.exam like ? " if ex else "and q.exam!='|upsc_cse|' ") + "order by (q.prov='official_pyq') desc, (q.prov='curated_unverified') desc, rank limit ?")
        rows = _qdb().execute(sql, (fq, f"%|{ex}|%", limit) if ex else (fq, limit)).fetchall()
        add("question", [{"id": r["qid"], "exams": r["exam"].strip("|").split("|"), "subject": r["subject"], "topic": _clip(r["topic"], 120), "stem": _clip(r["stem"], 240),
                          "provenance": r["prov"], "source_reference": r["source_ref"], "verification_status": "unverified_source", **({"claimed_year": r["year"]} if r["year"] else {}), **({"branch": r["branch"]} if r["branch"] else {}), **({"paper_label": r["plabel"]} if r["plabel"] else {})} for r in rows])
    order = {"hack": "hacks", "question": "questions", "segment": "segments", "unified": "transcripts", "lecture": "lectures", "library": "lectures",
             "insight": "insights", "note": "notes", "nlm_source": "notebooklm"}
    hits.sort(key=lambda h: (h["rank"], SCOPES.index(order.get(h["src"], "tools"))))
    reranked = _rerank(query, hits)
    for h in hits:
        h.pop("rank", None)
    return {"ok": True, "query": query, "scopes": used, "reranked": reranked, "count": len(hits[: limit * 2]), "results": hits[: limit * 2]}


_JUNK = {"t": 0, "ids": frozenset()}


def _junk_ids():
    """video ids moved out by junk.py (cached 10 min)"""
    if time.time() - _JUNK["t"] > 600:
        try:
            _JUNK["ids"] = frozenset(v for (v,) in _ro(SRC["library"]).execute("select video_id from junk"))
        except Exception:
            _JUNK["ids"] = frozenset()
        _JUNK["t"] = time.time()
    return _JUNK["ids"]


def search(query, scope="all", exam="", subject="", limit=8):
    """Failure-isolated federation: report unavailable sources without discarding healthy hits."""
    if not isinstance(query, str) or not query.strip():
        return {"ok": False, "error": "query must be non-empty"}
    if len(query) > 2000:
        return {"ok": False, "error": "query exceeds 2000 characters"}
    selected = list(SCOPES) if scope in ("", "all") else list(dict.fromkeys(scope.split(",")))
    selected = [x.strip() for x in selected]
    if any(x not in SCOPES for x in selected):
        return {"ok": False, "error": "unknown search scope", "allowed": list(SCOPES)}
    n = max(1, min(int(limit or 8), 25))
    hits, errors, seen, used = [], [], set(), []
    for sc in selected:
        try:
            result = _search_source(query, sc, exam, subject, n)
            for rank, hit in enumerate(result["results"]):
                key = (hit.get("src"), hit.get("id") or hit.get("url") or json.dumps(hit, sort_keys=True))
                if key in seen:
                    continue
                seen.add(key)
                hits.append((rank, len(used), hit))
            used.extend(x for x in result["scopes"] if x not in used)
        except (sqlite3.Error, OSError, ValueError, KeyError) as exc:
            errors.append({"scope": sc, "error": f"{type(exc).__name__}: {str(exc)[:180]}"})
    hits.sort(key=lambda item: item[:2])
    results = [item[2] for item in hits]
    reranked = _rerank(query, results)
    results = results[:n * 2]
    return {"ok": bool(results) or not errors, "query": query, "scopes": used,
            "degraded": bool(errors), "source_errors": errors, "reranked": reranked,
            "count": len(results), "results": results}


FLASHRANK_DIR = env("AIR10_EXAM_FLASHRANK", HOME / "flashrank")
_ranker = None


def _rerank(query, hits):
    """Re-order merged hits with a local cross-encoder (FlashRank ms-marco-TinyBERT, ~4 ms per 20). Offline; skipped if absent."""
    global _ranker
    if FLASHRANK_DIR is None or len(hits) < 3 or not (FLASHRANK_DIR / "ms-marco-TinyBERT-L-2-v2").exists():
        return False
    try:
        from flashrank import Ranker, RerankRequest
        with _lock:
            if _ranker is None:
                _ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2", cache_dir=str(FLASHRANK_DIR))
        text = lambda h: " ".join(str(h.get(k, "")) for k in ("title", "stem", "trick", "formula", "snippet", "concept", "hacks", "source", "topic"))
        res = _ranker.rerank(RerankRequest(query=query, passages=[{"id": i, "text": text(h)[:600]} for i, h in enumerate(hits)]))
        ranked = [hits[r["id"]] for r in res]
        hits[:] = ranked
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- 2. radar + crosswalk
_RADAR = None
STATE_AE_JE = {"title": "State AE/JE (state PSC / state electricity boards) — Electrical",
               "pattern": "Varies by state (e.g. MPSC, TNPSC, RPSC, APSC, WBPSC, UPPSC; board exams like UPPCL, MSEDCL). Usually 1-2 objective "
                          "papers on core EE + general studies; check the latest notification of the specific state.",
               "target": "Top-10 state rank", "weightage": [(s, "varies", "same core EE syllabus as SSC JE / ESE Paper-II") for s in
                                                             ("Electrical Machines", "Power Systems", "Basic Electrical & Circuit Laws",
                                                              "Measurement & Instrumentation", "Power Electronics", "Utilization & Estimation")],
               "sweet_spot": "Use SSC JE + ESE Paper-II weightage as a proxy; no official per-subject weightage is published.",
               "estimated": True}


def _overlay_radar(data):
    """Audit 2026-09-27: GATE gains GA/EMFT/Measurements/Digital; ESE Paper-II gains 5 estimated rows.
    Idempotent (skips rows already present); the external radar file is never edited."""
    g = data.get("gate")
    if g is not None:
        g["weightage"] = list(g["weightage"])
        have = {n for n, _, _ in g["weightage"]}
        g["weightage"] = [(n, ("3-5M" if n == "Analog Electronics" else w),
                             (("GATE Section 9 first half: op-amps, diodes, BJT small-signal (typical recent-paper range)"
                               if n == "Analog Electronics" else f""))) for n, w, f in g["weightage"]]
        g["weightage"] += [w for w in GATE_EXTRA_WEIGHTAGE if w[0] not in have]
    e = data.get("ese")
    if e is not None:
        e = dict(e); e["weightage"] = list(e["weightage"]); data["ese"] = e
        have = {n for n, _, _ in e["weightage"]}
        e["weightage"] += [w for w in ESE_EXTRA_WEIGHTAGE if w[0] not in have]
        e["estimated"] = True   # UPSC publishes no per-subject split: every ESE share below is estimated
        e["sweet_spot"] = (e.get("sweet_spot") or "") + " Shares are estimated from recent papers (UPSC publishes no per-subject split)."


def _radar():
    global _RADAR
    if _RADAR is None:
        data = {}
        if _exists(SRC["radar"]):
            spec = importlib.util.spec_from_file_location("jarvis_exam_radar", SRC["radar"])
            m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
            data = {k: dict(v) for k, v in m.EXAM_DATA.items()}
        data["state_ae_je"] = STATE_AE_JE
        _overlay_radar(data)
        _RADAR = data
    return _RADAR


def _weight(txt, exam_rows):
    """'18-22%' or '10-12M' or '13M' -> share of the exam (0..1). 'varies' -> None.
    Percent rows are normalized by the rows' own total so the shares always sum to 1.0."""
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(txt))]
    if not nums:
        return None
    mid = sum(nums) / len(nums)
    if "%" in str(txt):
        tot = 0.0
        for _, w, _ in exam_rows:
            n = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(w))]
            if "%" in str(w) and n:
                tot += sum(n) / len(n)
        return mid / tot if tot else None
    total = sum((lambda n: sum(n) / len(n) if n else 0)([float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(w))]) for _, w, _ in exam_rows)
    return mid / total if total else None


# Canonical subject map (2026-09-27 fix). Radar rows ("Network Theory", "Power Electronics & Microcontrollers"), official codes
# (ELECTRIC_CIRCUITS), curated names (Networks) all resolve here; question pickers filter on it, never on FTS over the stem
# (FTS "electrical OR machines" matched an EMFT question for the Machines row). Order = primary subject of a multi-subject name.
SUBJECT_MAP = (
    ("Electrical Machines", r"\bmachines?\b|\btransformers?\b"),
    ("Power Systems", r"\bpower systems?\b|\bgeneration\b|\btransmission\b|\bdistribution\b|\bswitchgear\b|\bgrid\b"),
    ("Control Systems", r"\bcontrol\b"),                                   # word match: "microcontrollers" is not control
    ("Power Electronics", r"\bpower electronics?\b|\bdrives?\b|\belectric vehicles?\b"),
    ("Circuits & Network Theory", r"\bcircuits?\b|\bnetworks?\b|\bbasic (concepts|electrical)\b"),
    ("Analog & Digital Electronics", r"\banalog(ue)?\b|\bdigital\b|\bbasic electronics\b|\bmicro(controller|processor)s?\b"),
    ("Measurement & Instrumentation", r"\bmeasurements?\b|\binstrument"),
    ("Electromagnetic Fields", r"\bemft\b|\belectromagnetic|\bantennas?\b"),
    ("Signals & Systems", r"\bsignals?\b|\bdsp\b"),
    ("Engineering Mathematics", r"\bmathematics\b|\bmaths?\b"),
    ("Utilization & Estimation", r"\butili[sz]ation\b|\bestimation\b|\bcosting\b|\btraction\b"),
    ("General Aptitude", r"\baptitude\b|\bverbal\b|\breasoning\b"),
)
# Quiz banks title rounds "Round 3: Stage 1 Fundamentals", so the source table / id prefix names the subject (checked row by row).
_QZ_SUBJECT = (
    (r"^QZ:rajon_emft_quiz_master:", "Electromagnetic Fields"),
    (r":eem_10k_questions:", "Measurement & Instrumentation"),
    (r":electrical_machines_10k_catalog:", "Electrical Machines"),
    (r":power_systems_10k_questions:", "Power Systems"),
    (r":quiz_questions_catalog:CS_", "Control Systems"),
    (r":quiz_questions_catalog:NT_", "Circuits & Network Theory"),
    (r":quiz_questions_catalog:R4_", "Electrical Machines"),               # transformers, induction + synchronous motors
)


def _subject_keys(name):
    """Name -> ordered canonical subjects it covers ([] = not an EE subject we know)."""
    n = re.sub(r"[_\s]+", " ", str(name or "")).lower()
    return [c for c, rx in SUBJECT_MAP if re.search(rx, n)]


def _canon_subject(name):
    keys = _subject_keys(name)
    return keys[0] if keys else name


def _question_subject(qid, subject="", topic=""):
    """Canonical subject of one bank question, or None when it cannot be told (then no subject filter ever returns it)."""
    if str(qid).startswith("QZ:"):
        for rx, canon in _QZ_SUBJECT:
            if re.search(rx, qid):
                return canon
        if re.search(r":quiz_questions_catalog:R[123]_", qid):              # basic rounds: circuits, except bridge / wattmeter items
            return "Measurement & Instrumentation" if re.search(r"bridge|wattmeter", topic or "", re.I) else "Circuits & Network Theory"
        subject = re.sub(r"^(round|module)\s*\d+\s*:?\s*", "", subject or "", flags=re.I)
    keys = _subject_keys(subject)
    return keys[0] if keys else None


_FIG_REF = re.compile(r"\bfig(ure)?s?\b|\bfig\.|\bshown\b|\bdepicted\b|\bgiven below\b|\bplot\b|\bdiagram\b", re.I)
_FIG_NOTE = "[figure in the official paper"
_FIG_ANY = "[figure in "   # covers '[figure in the official paper' and '[figure in source PDF]'
_UNREADABLE = re.compile(r"[\uf000-\uf8ff\ufffd]")   # private-use / replacement glyphs: matrix art lost in extraction


def _unusable(stem, options, answer="", figure=0):
    """Why a question cannot be answered from its text alone (None = usable)."""
    opts = json.loads(options or "[]") if isinstance(options, str) else list(options or [])
    key = (answer or "").strip()
    if figure:
        return "needs the figure from the official paper"
    if _FIG_ANY in (stem or ""):
        return "needs the figure from the official paper"
    if any(not str(o).strip() for o in opts):
        return "an option is missing/figure-only in the text"
    if any(re.match(r"\s*fig(ure)?\b|\s*fig\.", str(o), re.I) for o in opts):
        return "options are figures"
    if _FIG_NOTE in (stem or "") and _FIG_REF.search((stem or "").split(_FIG_NOTE)[0]):
        return "needs the figure from the official paper"
    if opts and any(_UNREADABLE.search(str(o)) for o in opts):
        return "options contain unreadable glyphs (extraction error)"
    if not opts and re.fullmatch(r"[A-Da-d]|\d", key):
        return "MCQ answer key but the options are missing in the source"
    if opts and re.fullmatch(r"-?[\d.]+ to -?[\d.]+.*", key):
        return "numeric answer key but MCQ options attached (extraction error)"
    if key.upper().startswith("MTA"):
        return "official key: marks to all (question dropped)"
    return None


_QMETA = {}


def _qmeta():
    """qid -> (canonical subject | None, unusable reason | None); cached per question-index file version."""
    con = _qdb()
    st = QINDEX.stat()
    key = (str(QINDEX), st.st_ino, st.st_mtime_ns, st.st_size)
    if _QMETA.get("key") != key:
        meta = {r["qid"]: (_question_subject(r["qid"], r["subject"], r["topic"]), _unusable(r["stem"], r["options"], r["answer"], r["figure"]))
                for r in con.execute("select qid, subject, topic, stem, options, answer, figure from q")}
        _QMETA.clear()
        _QMETA.update(key=key, map=meta)
    return _QMETA["map"]


def crosswalk():
    """Subject -> share in each exam; ranked by how many exams it pays in and how much (study once, score in many)."""
    R, table = _radar(), {}
    for ex, d in R.items():
        for name, w, _ in d["weightage"]:
            s = _canon_subject(name); share = _weight(w, d["weightage"])
            table.setdefault(s, {})[ex] = round(share, 3) if share is not None else "varies"
    ranked = sorted(table.items(), key=lambda kv: (-sum(1 for v in kv[1].values()), -sum(v for v in kv[1].values() if isinstance(v, float))))
    return [{"subject": s, "exams": len(v), "combined_share": round(sum(x for x in v.values() if isinstance(x, float)), 3), "per_exam": v} for s, v in ranked]


def radar(exam="all", subject=""):
    R, ex = _radar(), _norm_exam(exam)
    if ex in ("", "all"):
        return {"ok": True, "exams": {k: {"title": v["title"], "pattern": _clip(v["pattern"], 300)} for k, v in R.items()},
                "crosswalk_top": crosswalk()[:6], "note": "State AE/JE weightage varies by state: estimated=True, no numbers invented."}
    if ex not in R:
        return {"ok": False, "error": f"unknown exam {exam!r}", "exams": list(R)}
    d = R[ex]
    rows = [{"subject": n, "weight": w, "focus": f, "share": _weight(w, d["weightage"])} for n, w, f in d["weightage"]
            if not subject or subject.lower() in n.lower()]
    return {"ok": True, "exam": ex, "title": d["title"], "pattern": d["pattern"], "target": d.get("target"), "weightage": rows,
            "sweet_spot": d.get("sweet_spot"), **({"estimated": True} if d.get("estimated") else {})}


# ---------------------------------------------------------------- 3. practice (FSRS via the official py-fsrs package)
def _sched():
    from fsrs import Scheduler
    return Scheduler()


def _card(con, qid):
    from fsrs import Card
    r = con.execute("select card_json from cards where qid=?", (qid,)).fetchone()
    return Card.from_dict(json.loads(r[0])) if r else Card()


def practice(action="question", exam="", subject="", topic="", question_id="", answer="", rating=0, n=1, provenance="", attempt_id=""):
    action = (action or "question").lower()
    q = _qdb()
    if action == "question":
        ex = _norm_exam(exam)
        where, args = ["1=1"], []
        if ex:
            where.append("exam like ?"); args.append(f"%|{ex}|%")
            if ex == "gate":   # Rajon's paper is EE: EC/IN/CS/DA paper rows stay searchable, never served here (audit fix 3)
                where.append(f"coalesce(branch,'') not in ({','.join('?' * len(GATE_NON_EE_BRANCHES))})")
                args += list(GATE_NON_EE_BRANCHES)
        else:
            where.append("exam!='|upsc_cse|'")
        if provenance:
            provenance = {"curated_pyq": "curated_unverified"}.get(provenance, provenance)   # old name, same 110 rows
            where.append("prov=?"); args.append(provenance)
        meta = _qmeta()
        keys = _subject_keys(subject) if subject else []
        if keys:   # a known subject: filter on the canonical map (FTS over the stem crossed subjects)
            ids = {qid for qid, (canon, _) in meta.items() if canon in keys}
            if topic:
                ids &= {r[0] for r in q.execute("select q.qid from qfts f join q on q.rowid=f.rowid where qfts match ? limit 5000", (_fts(topic),))}
            if not ids:
                return {"ok": False, "error": f"no {' / '.join(keys)} questions{f' on {topic!r}' if topic else ''} in the bank", "subject_keys": keys}
            ids = sorted(ids)
            where.append(f"qid in ({','.join('?' * len(ids))})"); args += ids
        elif subject or topic:
            ids = [r[0] for r in q.execute("select q.qid from qfts f join q on q.rowid=f.rowid where qfts match ? limit 400",
                                           (_fts(f"{subject} {topic}"),))]
            if not ids:
                return {"ok": False, "error": f"no questions match {subject or topic!r}"}
            where.append(f"qid in ({','.join('?' * len(ids))})"); args += ids
        con = _rw()
        due = {r[0] for r in con.execute("select qid from cards where due <= ?", (dt.datetime.now(dt.timezone.utc).isoformat(),))}
        seen = {r[0] for r in con.execute("select qid from cards")}
        con.close()
        rows = q.execute(f"select * from q where {' and '.join(where)}", args).fetchall()
        skipped = sum(1 for r in rows if (meta.get(r["qid"]) or (None, None))[1])
        rank = {"official_pyq": 0, "curated_unverified": 1, "practice": 2}
        rows = sorted((r for r in rows if not (meta.get(r["qid"]) or (None, None))[1]),   # figure-only / option-less MCQs are skipped
                      key=lambda r: (r["qid"] not in due, r["qid"] in seen, rank.get(r["prov"], 3), r["options"] == "[]", -(r["year"] or 0), r["qid"]))
        rows = rows[: max(1, min(int(n or 1), 10))]
        if not rows:
            return {"ok": False, "error": "no usable questions for these filters" + (f" ({skipped} need a figure or lost their options)" if skipped else "")}
        return {"ok": True, "questions": [{"id": r["qid"], "exams": r["exam"].strip("|").split("|"), "subject": r["subject"],
                                           "subject_canonical": (meta.get(r["qid"]) or (None,))[0], "topic": _clip(r["topic"], 140),
                                           "question": r["stem"], "options": json.loads(r["options"]), "provenance": r["prov"],
                                           "provenance_note": PROVENANCE_NOTE.get(r["prov"], ""), "source_reference": r["source_ref"], "verification_status": "unverified_source", "due_review": r["qid"] in due,
                                           **({"branch": r["branch"]} if r["branch"] else {}),
                                           **({"paper_label": r["plabel"]} if r["plabel"] else {}),
                                           **({"claimed_year": r["year"]} if r["year"] else {}),
                                           **({"lecture": u} if (u := _yt_url(r["video"])) else {})} for r in rows],
                "how_to_answer": "exam_practice(action='answer', question_id=..., answer='B' or option index, rating optional 1-4)"}
    if action == "answer":
        r = q.execute("select * from q where qid=?", (question_id,)).fetchone()
        if not r:
            return {"ok": False, "error": "unknown question_id"}
        idx, correct = _answer_index(r), None
        given = str(answer or "").strip()
        rt = int(rating or 0)
        if not given and not rt:
            return {"ok": False, "error": "supply an answer or explicit self-rating; progress unchanged"}
        if rt not in (0, 1, 2, 3, 4):
            return {"ok": False, "error": "rating must be 1-4; progress unchanged"}
        opts = json.loads(r["options"])
        key = (r["answer"] or "").strip()
        if r["prov"] == "official_pyq" and given and (re.fullmatch(r"[A-D](;[A-D])+", key) or re.fullmatch(r"-?[\d.]+ to -?[\d.]+", key)):
            if " to " in key:   # NAT: official range, inclusive
                lo, hi = (float(x) for x in key.split(" to "))
                try:
                    correct = lo <= float(given) <= hi
                except ValueError:
                    return {"ok": False, "error": "NAT answer must be a number; progress unchanged"}
            else:               # MSQ: exact set of options
                got = set(re.findall(r"[A-Da-d]", given.upper()))
                if not got:
                    return {"ok": False, "error": "MSQ answer = option letters like 'A,B,D'; progress unchanged"}
                correct = got == set(key.split(";"))
            idx = None
        elif idx is not None and given:
            if re.fullmatch(r"[A-Da-d]", given):
                gi = "abcd".index(given.lower())
            elif given.isdigit():
                gi = int(given)
            else:
                return {"ok": False, "error": "answer must be one option letter A-D or a zero-based index"}
            if gi >= len(opts):
                return {"ok": False, "error": "option index outside available options"}
            correct = gi == idx
        elif not rt:
            return {"ok": False, "error": "no checkable answer key; compare the cited source then provide rating 1-4"}
        # An incorrect attempt cannot be silently recorded as remembered.
        rt = 1 if correct is False else (rt or 3)
        if attempt_id and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", attempt_id):
            return {"ok": False, "error": "invalid attempt_id"}
        fingerprint = hashlib.sha256(json.dumps([question_id, given, rt], separators=(",", ":")).encode()).hexdigest()
        from fsrs import Rating
        con = _rw()
        try:
            con.execute("begin immediate")
            if attempt_id:
                prior = con.execute("select fingerprint,result_json from attempt_receipts where attempt_id=?", (attempt_id,)).fetchone()
                if prior:
                    con.rollback()
                    if prior[0] != fingerprint:
                        return {"ok": False, "error": "attempt_id already used with different input"}
                    return {**json.loads(prior[1]), "replayed": True}
            card = _card(con, question_id)
            card, _ = _sched().review_card(card, Rating(rt))
            now = time.time()
            con.execute("insert or replace into cards values(?,?,?,?,?,?)", (question_id, r["topic"], r["subject"], json.dumps(card.to_dict()), card.due.isoformat(), now))
            con.execute("insert into reviews values(?,?,?,?,?,?,?)", (question_id, now, rt, None if correct is None else int(correct), given, r["topic"], r["exam"].strip("|")))
            if correct is False:
                con.execute("insert into mistakes values(?,?,?,?,?)", (question_id, now, r["topic"], "wrong_option", given))
            result = {"ok": True, "correct": correct, "correct_option": (("ABCD"[idx] + ") " + _clip(opts[idx], 160)) if idx is not None and idx < 4 else (opts[idx] if idx is not None else r["answer"] or None)),
                      "checked": correct is not None, "check_basis": "stored local answer key; independently unverified",
                      "explanation": _clip(r["explanation"], 900) or None, "next_review": card.due.isoformat(),
                      "rating_used": rt, "provenance": r["prov"], "source_reference": r["source_ref"], "attempt_id": attempt_id or None}
            if attempt_id:
                con.execute("insert into attempt_receipts values(?,?,?)", (attempt_id, fingerprint, json.dumps(result)))
            con.commit()
            return result
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    if action == "stats":
        con = _rw()
        tot = con.execute("select count(*), sum(correct), count(correct) from reviews").fetchone()
        weak = con.execute("select topic, count(*) n, sum(1-coalesce(correct,1)) wrong from reviews group by topic having wrong>0 "
                           "order by wrong*1.0/n desc, n desc limit 8").fetchall()
        due = con.execute("select count(*) from cards where due <= ?", (dt.datetime.now(dt.timezone.utc).isoformat(),)).fetchone()[0]
        con.close()
        bank = {r[0]: r[1] for r in q.execute("select prov, count(*) from q group by prov")}
        return {"ok": True, "reviews": tot[0], "accuracy": round(tot[1] / tot[2], 3) if tot[2] else None, "due_now": due,
                "weak_topics": [{"topic": _clip(w[0], 100), "attempts": w[1], "wrong": w[2]} for w in weak], "question_bank": bank}
    return {"ok": False, "error": "action must be question | answer | stats"}


# ---------------------------------------------------------------- 4. next (FSRS decay x exam weightage x days left)
def next_topics(exam="gate", days_left=0, n=5, clips=True):
    ex = _norm_exam(exam) or "gate"
    rd = radar(ex)
    if not rd.get("ok"):
        return rd
    con = _rw()
    now = dt.datetime.now(dt.timezone.utc)
    sched = _sched()
    mem = {}
    from fsrs import Card
    meta = _qmeta()
    for qid, subj, cj in con.execute("select qid, subject, card_json from cards"):
        try:
            r = sched.get_card_retrievability(Card.from_dict(json.loads(cj)), now)
        except TypeError:
            r = sched.get_card_retrievability(Card.from_dict(json.loads(cj)))
        mem.setdefault((meta.get(qid) or (None,))[0] or _canon_subject(subj or ""), []).append(r)
    con.close()
    urgency = 1.0 if not days_left else min(3.0, max(1.0, 90 / max(1, int(days_left))))
    out = []
    avail = {}
    for qid, (canon, bad) in meta.items():   # usable bank questions per canonical subject (coverage denominator)
        if canon and not bad:
            avail[canon] = avail.get(canon, 0) + 1
    for w in rd["weightage"]:
        keys = _subject_keys(w["subject"]); share = w["share"] if w["share"] is not None else 0.1
        rs = [x for k in (keys or [w["subject"]]) for x in mem.get(k, [])]
        recall = sum(rs) / len(rs) if rs else 0.0
        have = sum(avail.get(k, 0) for k in (keys or [w["subject"]]))
        coverage = min(1.0, len(rs) / have) if have else 0.0   # one right answer out of hundreds served != mastered
        gap = 1 - recall * coverage
        prio = round(share * gap * urgency, 4)
        out.append({"subject": w["subject"], "weight": w["weight"], "share": share, "cards": len(rs), "cards_available": have,
                    "coverage": round(coverage, 3), "avg_recall": round(recall, 3),
                    "priority": prio, "focus": w["focus"]})
    out.sort(key=lambda x: -x["priority"])
    top = out[: max(1, min(int(n or 5), 8))]
    for t in top:
        keys = _subject_keys(t["subject"])   # never the free-text fallback: a row gets its own subject's question or none
        pq = practice("question", exam=ex, subject=t["subject"]) if keys else {"ok": False, "error": "subject not in the canonical map"}
        if keys and not pq.get("ok"):   # none tagged for this exam: same subject from the other EE banks (GATE papers overlap ESE/JE)
            other = practice("question", subject=t["subject"])
            if other.get("ok"):
                pq, t["practice_scope"] = other, f"same subject, no {ex}-tagged question: taken from the {'/'.join(other['questions'][0]['exams'])} bank"
        t["practice"] = pq["questions"][0] if pq.get("ok") else None
        if t["practice"] is None:
            t["practice_note"] = f"no usable {' / '.join(keys) or t['subject']} question for {ex} in the bank ({pq.get('error')})"
        if clips:
            sr = search(f"{t['subject']} {t['focus']}", scope="segments", limit=2)
            t["clips"] = [{"title": h["title"], "url": h["url"]} for h in sr.get("results", []) if h.get("url")][:2]
    return {"ok": True, "exam": ex, "days_left": days_left or None, "rule": "priority = exam share x (1 - FSRS recall x coverage) x urgency(days_left); coverage = cards_seen/cards_available",
            "plan": top}


# ---------------------------------------------------------------- 5. solve (SymPy / SciPy; returns data, never prints)
def solve(kind="help", expression="", params=None):
    import sympy as sp
    from math_safety import parse_math
    p = dict(params or {})
    s, t = sp.symbols("s t")
    kind = (kind or "help").lower()
    if kind == "help":
        return {"ok": True, "kinds": {"tf": "expression G(s): poles, zeros, stability, DC gain, wn/zeta/Mp/ts for 2nd order",
                                      "eigen": "expression '[[0,1],[-2,-3]]': eigenvalues, stability",
                                      "laplace_inv": "expression F(s) -> f(t)", "rlc": "params R, L, C (series|parallel): f0, Q, BW",
                                      "vr": "params V_noload, V_fullload: voltage regulation %",
                                      "phasor": "expression like '10@30 + 5@-45' (polar a@deg) -> rectangular + polar",
                                      "linsolve": "expression 'x+y=3; x-y=1'", "three_phase": "params V_line, I_line, pf (star/delta): P, Q, S",
                                      "swing": "params pm, pmax_pre, pmax_fault, pmax_post, H, f0, tc, t_end: rotor-angle trajectory, stable?, critical clearing time",
                                      "eac": "params pm, pmax_pre, pmax_fault, pmax_post: equal-area critical clearing angle",
                                      "margins": "params num, den (descending powers of s): gain margin, phase margin, crossover frequencies",
                                      "powerflow": "params case (case9|case14|case30|case39): IEEE AC power flow via pandapower",
                                      "per_unit": "params z_pu_old (or z_ohm), kv_old, mva_old, kv_new, mva_new: change of base",
                                      "netlist": "expression = SPICE-style netlist ('V1 1 0 10; R1 1 2 2; C1 2 0 1e-6', sources may be 'step'/'ac'); params query all|nodes|elements|thevenin, a, b, elements: node voltages, element v/i (DC, phasor, step transients), Thevenin/Norton (lcapy)",
                                      "control": "params num/den (open loop, descending powers) or G='25/(s*(s+6))', or A,B,C[,D]: margins, unity-feedback Mp/tr/ts/tp/bandwidth, type + Kp/Kv/Ka, controllability/observability (python-control)",
                                      "logic": "expression like \"A'B + AB'\" (or params minterms, dontcares, variables): truth table minterms, minimal SOP and POS (SymPy)",
                                      "twoport": "params Z or Y or ABCD or h = [[a,b],[c,d]] (complex as '1+2j'): all other parameter sets, reciprocal, symmetric, AD-BC"}}
    if kind == "tf":
        G = parse_math(expression, {"s": s})
        num, den = sp.fraction(sp.together(G))
        poles, zeros = sp.Poly(den, s).nroots(), (sp.Poly(num, s).nroots() if sp.Poly(num, s).degree() > 0 else [])
        stable = all(sp.re(x) < 0 for x in poles)
        out = {"G": str(G), "poles": [str(sp.N(x, 5)) for x in poles], "zeros": [str(sp.N(x, 5)) for x in zeros],
               "stable": bool(stable), "dc_gain": str(sp.N(sp.limit(G, s, 0), 6)), "order": sp.Poly(den, s).degree()}
        if sp.Poly(den, s).degree() == 2:
            a2, a1, a0 = [float(c) for c in sp.Poly(den, s).all_coeffs()]
            wn = math.sqrt(a0 / a2); z = a1 / (2 * a2 * wn)
            out.update({"wn": round(wn, 4), "zeta": round(z, 4)})
            if 0 < z < 1:
                out.update({"wd": round(wn * math.sqrt(1 - z * z), 4), "Mp_percent": round(100 * math.exp(-z * math.pi / math.sqrt(1 - z * z)), 3),
                            "ts_2pct": round(4 / (z * wn), 4), "tp": round(math.pi / (wn * math.sqrt(1 - z * z)), 4)})
        return {"ok": True, "kind": kind, **out}
    if kind == "eigen":
        M = sp.Matrix(parse_math(expression))
        ev = M.eigenvals()
        return {"ok": True, "kind": kind, "eigenvalues": {str(sp.N(k, 6)): int(v) for k, v in ev.items()},
                "stable_continuous": all(sp.re(k) < 0 for k in ev), "det": str(M.det()), "trace": str(M.trace())}
    if kind == "laplace_inv":
        F = parse_math(expression, {"s": s})
        f = sp.inverse_laplace_transform(F, s, t)
        return {"ok": True, "kind": kind, "F": str(F), "f_t": str(sp.simplify(f.subs(sp.Heaviside(t), 1)))}
    if kind == "rlc":
        R, L, C = float(p["R"]), float(p["L"]), float(p["C"])
        f0 = 1 / (2 * math.pi * math.sqrt(L * C))
        Q = (1 / R) * math.sqrt(L / C) if p.get("type", "series") == "series" else R * math.sqrt(C / L)
        return {"ok": True, "kind": kind, "f0_hz": round(f0, 4), "w0": round(2 * math.pi * f0, 4), "Q": round(Q, 4), "bandwidth_hz": round(f0 / Q, 4),
                "type": p.get("type", "series")}
    if kind == "vr":
        vn, vf = float(p["V_noload"]), float(p["V_fullload"])
        return {"ok": True, "kind": kind, "regulation_percent": round(100 * (vn - vf) / vf, 4)}
    if kind == "phasor":
        expr = re.sub(r"([\d.]+)\s*@\s*(-?[\d.]+)", lambda m: f"({m.group(1)}*exp(I*pi*{m.group(2)}/180))", expression)
        z = complex(sp.N(parse_math(expr)))
        return {"ok": True, "kind": kind, "rectangular": f"{z.real:.4f} {'+' if z.imag >= 0 else '-'} j{abs(z.imag):.4f}",
                "magnitude": round(abs(z), 4), "angle_deg": round(math.degrees(math.atan2(z.imag, z.real)), 4)}
    if kind == "linsolve":
        eqs = [sp.Eq(*[parse_math(x) for x in e.split("=")]) for e in expression.split(";") if "=" in e]
        syms = sorted(set().union(*[e.free_symbols for e in eqs]), key=str)
        sol = sp.solve(eqs, syms, dict=True)
        return {"ok": True, "kind": kind, "solutions": [{str(k): str(sp.N(v, 6)) for k, v in d.items()} for d in sol]}
    if kind == "three_phase":
        V, I, pf = float(p["V_line"]), float(p["I_line"]), float(p.get("pf", 1))
        S = math.sqrt(3) * V * I
        return {"ok": True, "kind": kind, "S_VA": round(S, 3), "P_W": round(S * pf, 3), "Q_VAR": round(S * math.sin(math.acos(pf)), 3),
                "note": "P = sqrt(3) V_L I_L cos(phi), same for star and delta with line quantities"}
    if kind == "eac":
        return {"ok": True, "kind": kind, **_eac(float(p.get("pm", 1.0)), float(p.get("pmax_pre", 1.8)), float(p.get("pmax_fault", 0.0)),
                                                   float(p.get("pmax_post", 1.5)))}
    if kind == "swing":
        return {"ok": True, "kind": kind, **_swing(**{k: float(v) for k, v in p.items() if k in ("pm", "pmax_pre", "pmax_fault", "pmax_post", "H", "f0", "tc", "t_end")})}
    if kind == "margins":
        return {"ok": True, "kind": kind, **_margins([float(x) for x in p["num"]], [float(x) for x in p["den"]])}
    if kind == "powerflow":
        return _powerflow(str(p.get("case", "case9")))
    if kind == "per_unit":   # merged from the per-unit-normalizer skill
        kvn, mvan = float(p["kv_new"]), float(p["mva_new"])
        zb_new = kvn ** 2 / mvan
        if "z_ohm" in p:
            return {"ok": True, "kind": kind, "z_base_new_ohm": round(zb_new, 6), "z_pu_new": round(float(p["z_ohm"]) / zb_new, 6)}
        kvo, mvao = float(p["kv_old"]), float(p["mva_old"])
        return {"ok": True, "kind": kind, "z_pu_new": round(float(p["z_pu_old"]) * (kvo / kvn) ** 2 * (mvan / mvao), 6),
                "z_base_new_ohm": round(zb_new, 6), "formula": "Z_new = Z_old (kV_old/kV_new)^2 (MVA_new/MVA_old)"}
    if kind in ("netlist", "control", "logic", "twoport"):   # ee_solvers.py: lcapy / python-control / SymPy, no eval of input
        import ee_solvers as E
        if kind == "netlist":
            return E.netlist(expression, str(p.get("query", "all")), p.get("a"), p.get("b"), p.get("elements"))
        if kind == "control":
            return E.control({**p, **({"G": expression} if expression and "G" not in p else {})})
        if kind == "logic":
            return E.logic(expression, p.get("minterms"), p.get("dontcares"), p.get("variables"))
        return E.twoport(p)
    return {"ok": False, "error": f"unknown kind {kind!r}", "kinds": list(solve('help')['kinds'])}


# ---- power-system + control solvers (merged from hermes_air10_supertutor antigravity_bridge_mcp, rebuilt on SciPy/NumPy only)
def _eac(pm, pmax_pre, pmax_fault, pmax_post):
    d0 = math.asin(pm / pmax_pre)
    if pm >= pmax_post:
        return {"delta0_deg": round(math.degrees(d0), 3), "stable_possible": False, "why": "Pm >= post-fault Pmax: no equilibrium after clearing"}
    dmax = math.pi - math.asin(pm / pmax_post)
    c = (pm * (dmax - d0) + pmax_post * math.cos(dmax) - pmax_fault * math.cos(d0)) / (pmax_post - pmax_fault)
    if not -1 <= c <= 1:
        return {"delta0_deg": round(math.degrees(d0), 3), "stable_possible": False, "why": "no real critical clearing angle"}
    dcr = math.acos(c)
    return {"delta0_deg": round(math.degrees(d0), 3), "delta_max_deg": round(math.degrees(dmax), 3), "critical_clearing_angle_deg": round(math.degrees(dcr), 3),
            "stable_possible": True, "formula": "cos(dcr) = [Pm(dmax-d0) + Pmax2 cos dmax - Pmax1 cos d0] / (Pmax2 - Pmax1)"}


def _swing(pm=1.0, pmax_pre=1.8, pmax_fault=0.0, pmax_post=1.5, H=5.0, f0=50.0, tc=0.15, t_end=1.0):
    from scipy.integrate import solve_ivp
    M = H / (math.pi * f0)                       # pu-s^2/rad
    d0 = math.asin(min(1.0, pm / pmax_pre))
    d_unstable = math.pi - math.asin(min(1.0, pm / pmax_post))   # 2026-09-27 fix: was pi, which let 138-180 deg count as stable

    def run(tclear):
        def f(t, y):
            pe = (pmax_fault if t < tclear else pmax_post) * math.sin(y[0])
            return [y[1], (pm - pe) / M]
        sol = solve_ivp(f, (0, t_end), [d0, 0.0], max_step=0.002, rtol=1e-7, atol=1e-9)
        return sol, bool(max(sol.y[0]) < d_unstable)   # past the post-fault unstable equilibrium there is no way back
    sol, stable = run(tc)
    lo, hi = 0.0, 2.0                             # critical clearing time by bisection (stable at lo, unstable at hi)
    if run(hi)[1]:
        cct = None
    else:
        for _ in range(22):
            mid = (lo + hi) / 2
            (lo, hi) = (mid, hi) if run(mid)[1] else (lo, mid)
        cct = round(lo, 4)
    idx = [int(i) for i in range(0, len(sol.t), max(1, len(sol.t) // 12))]
    return {"stable": stable, "delta0_deg": round(math.degrees(d0), 3), "delta_max_deg": round(math.degrees(max(sol.y[0])), 3),
            "critical_clearing_time_s": cct, "eac": _eac(pm, pmax_pre, pmax_fault, pmax_post),
            "trajectory": [[round(float(sol.t[i]), 3), round(math.degrees(float(sol.y[0][i])), 2)] for i in idx],
            "model": "M d2delta/dt2 = Pm - Pmax sin(delta), M = H/(pi f0); RK45"}


def _margins(num, den):
    import numpy as np
    from scipy.optimize import brentq
    G = lambda w: np.polyval(num, 1j * w) / np.polyval(den, 1j * w)
    ws = np.logspace(-3, 4, 20000)
    mag = np.abs(G(ws)); ph = np.unwrap(np.angle(G(ws)))
    out = {"open_loop_poles": [str(complex(round(r.real, 4), round(r.imag, 4))) for r in np.roots(den)]}
    gc = np.where(np.diff(np.sign(mag - 1)))[0]
    if len(gc):
        wgc = brentq(lambda w: abs(G(w)) - 1, ws[gc[0]], ws[gc[0] + 1])
        pmg = 180 + math.degrees(np.interp(wgc, ws, ph))
        out.update({"gain_crossover_rad_s": round(wgc, 4), "phase_margin_deg": round(((pmg + 180) % 360) - 180, 3)})
    else:
        out.update({"gain_crossover_rad_s": None, "phase_margin_deg": float("inf")})
    pc = np.where(np.diff(np.sign(ph + np.pi)))[0]
    if len(pc):
        wpc = brentq(lambda w: np.interp(w, ws, ph) + np.pi, ws[pc[0]], ws[pc[0] + 1])
        gm = 1 / abs(G(wpc))
        out.update({"phase_crossover_rad_s": round(wpc, 4), "gain_margin": round(float(gm), 4), "gain_margin_db": round(20 * math.log10(gm), 3)})
    else:
        out.update({"phase_crossover_rad_s": None, "gain_margin": float("inf"), "gain_margin_db": float("inf")})
    out["closed_loop_stable"] = bool(all(r.real < 0 for r in np.roots(np.polyadd(den, num))))
    return out


PANDAPOWER_PY = env("AIR10_EXAM_PANDAPOWER_PY", "")
_PF_CODE = ("import json,sys,pandapower as pp,pandapower.networks as pn\n"
            "c=sys.argv[1]; net={'case9':pn.case9,'case14':pn.case14,'case30':pn.case30,'case39':pn.case39}[c](); pp.runpp(net)\n"
            "b=net.res_bus; print(json.dumps({'case':c,'buses':len(b),'vm_pu_min':round(float(b.vm_pu.min()),4),'vm_pu_max':round(float(b.vm_pu.max()),4),"
            "'weakest_bus':int(b.vm_pu.idxmin()),'losses_mw':round(float(net.res_line.pl_mw.sum()+(net.res_trafo.pl_mw.sum() if len(net.trafo) else 0)),4),"
            "'max_line_loading_pct':round(float(net.res_line.loading_percent.max()),2),'gen_p_mw':[round(float(x),2) for x in net.res_gen.p_mw]}))")


def _powerflow(case):
    import subprocess
    if case not in ("case9", "case14", "case30", "case39"):
        return {"ok": False, "error": "case must be case9|case14|case30|case39"}
    if not PANDAPOWER_PY or not Path(PANDAPOWER_PY).exists():
        return {"ok": False, "error": "pandapower python not found (set AIR10_EXAM_PANDAPOWER_PY)"}
    r = subprocess.run([str(PANDAPOWER_PY), "-c", _PF_CODE, case], capture_output=True, text=True, timeout=120)
    try:
        return {"ok": True, "kind": "powerflow", **json.loads(r.stdout.strip().splitlines()[-1])}
    except (ValueError, IndexError):
        return {"ok": False, "error": _clip(r.stderr or r.stdout, 300)}


# ---------------------------------------------------------------- 6. tools (hidden helpers)
def _formula_check(text=""):
    """Broken-math detector for notes (same idea as air10_formula_leak_court): unbalanced $, (), [], {} and \\begin/\\end."""
    issues = []
    if text.count("$") % 2:
        issues.append("odd number of $ delimiters")
    for a, b in ("()", "[]", "{}"):
        if text.count(a) != text.count(b):
            issues.append(f"unbalanced {a}{b}: {text.count(a)} vs {text.count(b)}")
    begins, ends = re.findall(r"\\begin\{(\w+)\}", text), re.findall(r"\\end\{(\w+)\}", text)
    if sorted(begins) != sorted(ends):
        issues.append(f"\\begin/\\end mismatch: {begins} vs {ends}")
    return {"ok": True, "clean": not issues, "issues": issues}


_UNITS = {"kv": ("V", 1e3), "mv": ("V", 1e-3), "v": ("V", 1), "ka": ("A", 1e3), "ma": ("A", 1e-3), "a": ("A", 1), "kw": ("W", 1e3),
          "mw": ("W", 1e6), "w": ("W", 1), "kva": ("VA", 1e3), "mva": ("VA", 1e6), "kvar": ("VAR", 1e3), "mvar": ("VAR", 1e6),
          "uf": ("F", 1e-6), "nf": ("F", 1e-9), "pf": ("F", 1e-12), "mh": ("H", 1e-3), "uh": ("H", 1e-6), "kohm": ("ohm", 1e3),
          "mohm": ("ohm", 1e6), "ohm": ("ohm", 1), "khz": ("Hz", 1e3), "mhz": ("Hz", 1e6), "hz": ("Hz", 1)}


def _units(value=""):
    from math_safety import normalize_units
    return normalize_units(value)


def _notebook_route(subject=""):
    if not _exists(SRC["registry"]):
        return {"ok": False, "error": "15-subject registry not found"}
    reg = json.loads(Path(SRC["registry"]).read_text())
    key = _canon_subject(subject).upper().replace("&", "").replace("  ", " ").replace(" ", "_")
    best = max(reg.items(), key=lambda kv: sum(w in kv[0] for w in key.split("_") if len(w) > 3)) if subject else None
    return {"ok": True, "subject": subject, "notebook": ({"title": best[1].get("title"), "notebook_id": best[1].get("notebook_id"),
                                                          "sources": best[1].get("sources_count")} if best else None),
            "all": {k: v.get("sources_count") for k, v in reg.items()},
            "how": "notebooklm MCP: ask_question(question=..., notebook_id=..., fast=False)"}


def sources():
    out = {}
    for k, p in SRC.items():
        out[k] = {"path": str(p).replace(str(H), "~"), "present": _exists(p), **({"mb": round(Path(p).stat().st_size / 1e6, 1)} if _exists(p) else {})}
    qi = _qdb()
    out["question_index"] = {"path": str(QINDEX).replace(str(H), "~"), "by_provenance": {r[0]: r[1] for r in qi.execute("select prov, count(*) from q group by prov")},
                             "by_exam": {e: qi.execute("select count(*) from q where exam like ?", (f"%|{e}|%",)).fetchone()[0] for e in EXAMS + ["upsc_cse"]}}
    return {"ok": True, "sources": out, "version": SOURCE_SHA256[:12]}


def _study_log():
    if not _exists(SRC["study"]):
        return {"ok": False, "error": "sovereign_study_master.sqlite not found"}
    c = _ro(SRC["study"])
    tabs = [r[0] for r in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
    return {"ok": True, "tables": {t: c.execute(f"select count(*) from {t}").fetchone()[0] for t in tabs},
            "streak": [dict(r) for r in c.execute("select * from streaks limit 3")] if "streaks" in tabs else []}


def triangulate(topic="", limit=3):
    """Same concept, three teachers: triad symposiums + cross-video dialogue edges (agree / contradict / extend) + lethal trap."""
    v = _ro(SRC["vault"]); fq = _fts(topic)
    like = f"%{' '.join(re.findall(r'[A-Za-z0-9]+', topic))[:40]}%"
    tri = v.execute("select topic, grandfather_title, grandfather_channel, video_grandfather_id, father_title, father_channel, video_father_id, "
                    "subset_title, subset_channel, video_subset_id, symposium_synopsis, exam_lethality_trap from triad_symposiums "
                    "where topic like ? or symposium_synopsis like ? or grandfather_title like ? or father_title like ? or subset_title like ? limit ?",
                    (like,) * 5 + (int(limit),)).fetchall()
    edges = v.execute("select topic, title_a, channel_a, video_a_id, title_b, channel_b, video_b_id, relation_type, mathematical_invariant "
                      "from cross_video_dialogue_edges where topic like ? or dialogue_script like ? limit ?", (like, like, int(limit) * 2)).fetchall()
    return {"ok": True, "topic": topic,
            "triads": [{"topic": r["topic"], "teachers": [{"title": _clip(r[f"{k}_title"], 90), "channel": r[f"{k}_channel"],
                                                           **({"url": f"https://youtu.be/{r[f'video_{k}_id']}"} if re.fullmatch(r"[\w-]{11}", r[f"video_{k}_id"] or "") else {})}
                                                          for k in ("grandfather", "father", "subset")],
                        "synopsis": _clip(r["symposium_synopsis"], 500), "lethal_trap": _clip(r["exam_lethality_trap"], 240)} for r in tri],
            "dialogues": [{"relation": r["relation_type"], "a": f"{_clip(r['title_a'], 70)} ({r['channel_a']})", "b": f"{_clip(r['title_b'], 70)} ({r['channel_b']})",
                           "invariant": _clip(r["mathematical_invariant"], 200)} for r in edges],
            "note": "empty = no multi-teacher analysis stored for this topic yet (820 triads, 2,948 dialogue edges exist)"}


def trap_radar(topic="", exam=""):
    """Most common traps for a concept: video taxonomy trap_type counts + insight exam_traps."""
    v = _ro(SRC["vault"])
    rows = v.execute("select t.trap_type, count(*) n, max(t.micro_concept) c from taxonomy_fts f join video_taxonomy t on t.video_id=f.video_id "
                     "where taxonomy_fts match ? and t.trap_type is not null and t.trap_type<>'' group by t.trap_type order by n desc limit 8",
                     (_fts(topic),)).fetchall()
    ins = search(topic, scope="insights", limit=3).get("results", [])
    return {"ok": True, "topic": topic, "trap_types": [{"trap": r["trap_type"], "videos": r["n"], "example_concept": r["c"]} for r in rows],
            "insight_traps": [i.get("traps") for i in ins if i.get("traps")]}


def route(topic="", limit=5):
    """Exact NotebookLM notebook + source to ask for a topic (53,510-source canonical catalog), with the owning account."""
    r = search(topic, scope="notebooklm", limit=limit)
    by_nb = {}
    for h in r.get("results", []):
        by_nb.setdefault(h["notebook_id"], {"notebook_id": h["notebook_id"], "notebook": h["notebook"], "account": h["account"], "sources": []})["sources"].append(h["source"])
    return {"ok": True, "topic": topic, "notebooks": list(by_nb.values())[:3],
            "how": "notebooklm MCP: ask_question(question=..., notebook_id=..., fast=False); cloud access is checked at call time"}


def exam_family(exam="gate"):
    d = _ro(SRC["exam_dag"])
    key = {"gate": "GATE EE", "ese": "Engineering Services", "ssc_je": "SSC JE", "rrb_je": "RRB JE", "psu": "PSU", "state_ae_je": "AE"}.get(_norm_exam(exam), exam)
    me = d.execute("select exam_id, name from exams where name like ? limit 1", (f"%{key}%",)).fetchone()
    if not me:
        return {"ok": False, "error": f"{exam!r} not in the 2,000-exam DAG"}
    nb = d.execute("select e.name, x.transferability_weight w, x.rationale, (x.source_exam_id=?) outgoing from dag_edges x join exams e "
                   "on e.exam_id = case when x.source_exam_id=? then x.target_exam_id else x.source_exam_id end "
                   "where x.source_exam_id=? or x.target_exam_id=? order by w desc limit 20", (me["exam_id"],) * 4).fetchall()
    return {"ok": True, "exam": me["name"], "related": [{"exam": r["name"], "syllabus_overlap": r["w"], "direction": "leads_to" if r["outgoing"] else "feeds_from",
                                                         "why": _clip(r["rationale"], 140)} for r in nb]}


YT_MODULE = env("AIR10_EXAM_YT", "")
_yt = None


def _youtube(fn, arg, n=5):
    """Hermes youtube_mcp_server functions (transcript with yt-dlp fallback, lecture search). Needs network."""
    global _yt
    if not YT_MODULE:
        return {"ok": False, "error": "YouTube module not found (set AIR10_EXAM_YT)"}
    if _yt is None:
        spec = importlib.util.spec_from_file_location("hermes_youtube", YT_MODULE)
        _yt = importlib.util.module_from_spec(spec); spec.loader.exec_module(_yt)
    out = _yt.fetch_youtube_transcript(arg) if fn == "transcript" else _yt.search_youtube_lectures(arg, max_results=int(n))
    try:
        return {"ok": True, **(json.loads(out) if isinstance(out, str) else {"result": out})}
    except ValueError:
        return {"ok": True, "result": _clip(out, 4000)}


def _gemini_study(action="status", target=""):
    """Gemini Study Notebook bridge (air10-study CLI / fastpath MCP): fixed sub-commands only."""
    import subprocess
    if action not in ("status", "doctor", "resume", "next", "launch", "prepare"):
        return {"ok": False, "error": "action: status|doctor|resume|next|launch|prepare"}
    argv = [str(H / ".local/bin/air10-study"), action] + (["--target", re.sub(r"[^\w-]", "", target)] if action == "prepare" and target else [])
    r = subprocess.run(argv, capture_output=True, text=True, timeout=90, stdin=subprocess.DEVNULL)
    return {"ok": r.returncode == 0, "action": action, "output": _clip((r.stdout or "") + (r.stderr or ""), 1500)}


# ---------------------------------------------------------------- study packet: the 8-layer library joins everything by one key
LIBRARY_TREE = env("AIR10_EXAM_LIBRARY_TREE", "")
SECTION_OF = {"ENGINEERING_MATHEMATICS": 1, "ELECTRIC_CIRCUITS": 2, "ELECTROMAGNETIC_FIELDS": 3, "SIGNALS_AND_SYSTEMS": 4, "ELECTRICAL_MACHINES": 5,
              "POWER_SYSTEMS": 6, "CONTROL_SYSTEMS": 7, "MEASUREMENTS": 8, "ANALOG_ELECTRONICS": 9, "DIGITAL_ELECTRONICS": 9, "POWER_ELECTRONICS": 10}
SOLVERS_OF = {"ELECTRIC_CIRCUITS": ["netlist", "twoport", "rlc", "phasor", "three_phase", "linsolve"], "CONTROL_SYSTEMS": ["control", "tf", "margins", "eigen", "laplace_inv"],
              "SIGNALS_AND_SYSTEMS": ["laplace_inv", "tf"], "ELECTRICAL_MACHINES": ["vr", "three_phase", "per_unit"],
              "POWER_SYSTEMS": ["powerflow", "swing", "eac", "per_unit", "three_phase"], "DIGITAL_ELECTRONICS": ["logic"],
              "ANALOG_ELECTRONICS": ["netlist", "tf"], "MEASUREMENTS": ["netlist", "phasor"], "ENGINEERING_MATHEMATICS": ["eigen", "linsolve", "laplace_inv"],
              "POWER_ELECTRONICS": ["netlist", "units"], "ELECTROMAGNETIC_FIELDS": ["units"], "BASIC_ELECTRICAL_ENGINEERING": ["netlist", "phasor", "units"]}


def _words(x):
    return {w.rstrip("S") for w in re.split(r"[^A-Z0-9]+", (x or "").upper()) if len(w) > 1} - {"AND", "OF", "THE", "IN"}


def study_packet(subject="", chapter="", topic="", n=8):
    """One chapter, every store joined by the shared 8-layer key (L1 GATE_ESE_EE > L2 subject > L3 official-syllabus chapter)."""
    if not LIBRARY_TREE:
        return {"ok": False, "error": "library not built (set AIR10_EXAM_LIBRARY_TREE)"}
    spec_f, lib_f = LIBRARY_TREE / "taxonomy_spec.json", LIBRARY_TREE / "library.sqlite"
    if not spec_f.exists():
        return {"ok": False, "error": f"library not built: {spec_f} missing"}
    spec = json.loads(spec_f.read_text())["L3_GATE_ESE_EE"]
    want, sub = _words(f"{subject} {chapter} {topic}"), _words(subject)
    best = max(((l2, l3) for l2, ch in spec.items() for l3 in ch),
               key=lambda k: (len(want & _words(k[1])) * 2 + len(want & _words(k[0])) + (3 if sub and sub <= _words(k[0]) else 0)), default=None)
    if not best or not (want & (_words(best[0]) | _words(best[1]))):
        return {"ok": False, "error": "could not match a GATE EE chapter", "subjects": {k: v for k, v in spec.items()}}
    l2, l3 = best
    out = {"ok": True, "key": ["GATE_ESE_EE", l2, l3], "library_folder": str(LIBRARY_TREE / "youtube" / "GATE_ESE_EE" / l2 / l3).replace(str(H), "~")}
    syl = LIBRARY_TREE / "syllabi/GATE2026_EE_Syllabus.txt"
    if syl.exists() and l2 in SECTION_OF:
        txt = re.sub(r"GATE 2026\s+IIT Guwahati \| Organizing Institute", " ", syl.read_text())
        k = SECTION_OF[l2]
        m = re.search(rf"Section {k}:(.*?)(?:Section {k + 1}:|$)", txt, re.S)
        out["official_syllabus_gate2026"] = _clip(re.sub(r"\s+", " ", m.group(1)), 900) if m else None
    words = " ".join(w.lower() for w in l2.split("_"))
    need = _words(l2) - {"SYSTEM", "ENGINEERING"}   # every distinctive word must match: Control Systems != Power Systems
    out["weightage"] = {ex: [r for r in (radar(ex).get("weightage") or []) if need and need <= _words(r["subject"])][:2] for ex in ("gate", "ese", "ssc_je")}
    if lib_f.exists():
        con = _ro(lib_f)
        base = ("from items where l1='GATE_ESE_EE' and l2=? and l3=? and merged_into is null and coalesce(action,'') <> 'trashed' "
                "and rel in ('core','study')")
        tree = {}
        for l4, l5, c in con.execute(f"select coalesce(l4,'(chapter-wide)'), coalesce(l5,''), count(*) {base} group by 1, 2 order by 3 desc", (l2, l3)):
            tree.setdefault(l4, {})[l5 or "(topic-wide)"] = c
        out["library_tree"] = {k: tree[k] for k in list(tree)[:14]}
        out["lectures_total"] = con.execute(f"select count(*) {base}", (l2, l3)).fetchone()[0]
        depth = "(l4 is not null) + (l5 is not null) + (l6 is not null) + (l7 is not null) + (l8 is not null)"
        rows = con.execute(f"select title, topic_phrase, url, path, l4, l5, l6, l7, l8, text_chars {base} and text_chars > 1500 "
                           f"order by {depth} desc, text_chars desc limit ?", (l2, l3, n)).fetchall()
        out["lectures"] = [{"title": _clip(r["title"] or (r["topic_phrase"] or "").replace("_", " ").title(), 120), "url": _watch_url(r["url"]), "file": (r["path"] or "").replace(str(H), "~") or None,
                            "layers": [x for x in (r["l4"], r["l5"], r["l6"], r["l7"], r["l8"]) if x], "chars": r["text_chars"]} for r in rows]
        try:
            reps = con.execute("select name, lib_path, exam_use from repos where l1='GATE_ESE_EE' and l2=? and coalesce(action,'') not in ('trashed') "
                               "order by (l3=?) desc, rel='core' desc limit 6", (l2, l3)).fetchall()
            out["reference_repos"] = [{"name": r["name"], "path": (r["lib_path"] or "").replace(str(H), "~"), "use": r["exam_use"]} for r in reps]
        except sqlite3.Error:
            out["reference_repos"] = []
    fq = _fts(f"{l3.replace('_', ' ')} {words}")
    try:
        meta, keys = _qmeta(), _subject_keys(l2)
        ok = lambda r: not meta.get(r["qid"], (None, None))[1] and meta.get(r["qid"], (None, None))[0] in keys   # own subject, text-answerable
        official = [r for r in _qdb().execute("select qid, stem, prov, exam, branch, plabel from q where prov='official_pyq' and subject=? order by (topic=?) desc, year desc",
                                              (l2, l3)).fetchall() if ok(r)][:5]
        qs = official + [r for r in _qdb().execute("select q.qid, q.stem, q.prov, q.exam, q.branch, q.plabel from qfts f join q on q.rowid=f.rowid where qfts match ? "
                                                   "and q.prov <> 'official_pyq' order by rank limit 200", (fq,)).fetchall() if ok(r)][:max(0, 6 - len(official))]
        out["practice_questions"] = [{"id": r["qid"], "question": _clip(r["stem"], 200), "provenance": r["prov"], "exams": r["exam"].strip("|").split("|"),
                                        **({"branch": r["branch"]} if r["branch"] else {}), **({"paper_label": r["plabel"]} if r["plabel"] else {})} for r in qs]
    except sqlite3.Error as e:
        out["practice_questions"] = {"error": str(e)[:120]}
    out["solvers"] = {k: solve("help")["kinds"].get(k) for k in SOLVERS_OF.get(l2, [])}
    out["how_to_use"] = "read the official line -> watch 1-2 lectures from the deepest layers -> solve with the listed solvers -> exam_practice answers -> exam_next"
    return out


TOOLS = {"gemini_study": ("Gemini Study Notebook session: status|doctor|resume|next|launch|prepare(target)", lambda a: _gemini_study(a.get("action", "status"), a.get("target", ""))),
         "youtube_transcript": ("fetch a lecture transcript (time-aligned) by YouTube URL/id - network", lambda a: _youtube("transcript", a.get("url", ""))),
         "youtube_search": ("search YouTube for GATE/ESE lectures - network", lambda a: _youtube("search", a.get("query", ""), a.get("n", 5))),
         "clips": ("timestamped lecture clips for a topic (763k segments), falls back to whole lectures", lambda a: search(a.get("topic", ""), scope="segments,lectures", limit=a.get("limit", 5))),
         "triangulate": ("same concept from 3 teachers + agree/contradict edges + lethal exam trap", lambda a: triangulate(a.get("topic", ""), a.get("limit", 3))),
         "trap_radar": ("most frequent traps for a concept across 20k classified lectures", lambda a: trap_radar(a.get("topic", ""), a.get("exam", ""))),
         "route": ("which NotebookLM notebook/source/account to ask for a topic (53k sources)", lambda a: route(a.get("topic", ""), a.get("limit", 5))),
         "exam_family": ("exams related to an exam in the 2,000-exam DAG", lambda a: exam_family(a.get("exam", "gate"))),
         "crosswalk": ("subjects ranked by how many of the 6 exams they pay in", lambda a: {"ok": True, "crosswalk": crosswalk()}),
         "notebook_route": ("which of the 15 canonical NotebookLM notebooks to ask for a subject", lambda a: _notebook_route(a.get("subject", ""))),
         "sources": ("every merged data source, presence, size, question counts by provenance", lambda a: sources()),
         "build_index": ("rebuild the unified question index from all banks", lambda a: build_index()),
         "formula_check": ("find broken math delimiters in note text", lambda a: _formula_check(a.get("text", ""))),
         "units": ("normalize an EE quantity to SI ('11 kV', '4.7 uF')", lambda a: _units(a.get("value", ""))),
         "study_packet": ("one GATE EE chapter joined across stores by the 8-layer key: official syllabus line, exam weightage, best lectures from $AIR10_EXAM_LIBRARY_TREE (deepest layers first), practice questions, matching exam_solve kinds, reference repos. args: subject, chapter, topic, n",
                          lambda a: study_packet(a.get("subject", ""), a.get("chapter", ""), a.get("topic", ""), int(a.get("n", 8)))),
         "study_log": ("streaks/cards/mistakes from the sovereign study master (read-only)", lambda a: _study_log())}


def tools(tool="list", args=None):
    a = dict(args or {})
    if tool in ("list", "", None):
        return {"ok": True, "tools": {k: v[0] for k, v in TOOLS.items()}}
    if tool not in TOOLS:
        return {"ok": False, "error": f"unknown tool {tool!r}", "tools": list(TOOLS)}
    return TOOLS[tool][1](a)


# ---------------------------------------------------------------- MCP surface (6 tools)
@mcp.tool()
def exam_search(query: str, scope: str = "all", exam: str = "", subject: str = "", limit: int = 8) -> dict:
    """One search over EE exam knowledge: hacks, questions (provenance-labelled), 763k timestamped lecture segments, 86k lectures,
    insights, notes, 53k NotebookLM sources. scope: all | hacks,questions,segments,transcripts,lectures,insights,notes,notebooklm,tools."""
    return _safe(search, query, scope, exam, subject, limit)


@mcp.tool()
def exam_next(exam: str = "gate", days_left: int = 0, n: int = 5) -> dict:
    """What to study next: subjects ranked by exam weightage x (1 - your FSRS recall) x urgency, each with a practice
    question and 2 lecture clips. exam: gate|ese|ssc_je|rrb_je|state_ae_je|psu."""
    return _safe(next_topics, exam, days_left, n)


@mcp.tool()
def exam_practice(action: str = "question", exam: str = "", subject: str = "", topic: str = "", question_id: str = "",
                  answer: str = "", rating: int = 0, n: int = 1, provenance: str = "", attempt_id: str = "") -> dict:
    """Practice loop. action=question (filters exam/subject/topic/provenance curated_unverified|practice, n<=10; old name curated_pyq still accepted) |
    answer (question_id + answer 'B' or index; auto-checked, FSRS-scheduled, mistakes logged) | stats (accuracy, weak topics, due)."""
    return _safe(practice, action, exam, subject, topic, question_id, answer, rating, n, provenance, attempt_id)


@mcp.tool()
def exam_solve(kind: str = "help", expression: str = "", params: dict | None = None) -> dict:
    """Exact math for EE problems: tf (poles/zeros/wn/zeta/Mp/ts) | margins (GM/PM) | eigen | laplace_inv | rlc | vr | phasor ('10@30+5@-45') |
    linsolve | three_phase | swing (transient stability + critical clearing time) | eac | powerflow (IEEE case9-39). kind=help lists params."""
    return _safe(solve, kind, expression, params)


@mcp.tool()
def exam_radar(exam: str = "all", subject: str = "") -> dict:
    """Pattern + subject weightage for GATE EE, UPSC ESE, SSC JE, RRB JE, State AE/JE (estimated), PSUs; exam=all adds the
    crosswalk of subjects that pay in the most exams."""
    return _safe(radar, exam, subject)


@mcp.tool()
def exam_tools(tool: str = "list", args: dict | None = None) -> dict:
    """Extra helpers: clips(topic, timestamped) | triangulate(topic: 3 teachers) | trap_radar(topic) | route(topic: exact NotebookLM
    notebook) | exam_family(exam) | crosswalk | notebook_route(subject) | sources | build_index | formula_check(text) | units(value) | study_log."""
    return _safe(tools, tool, args)


if not _CLI and os.environ.get("AIR10_MCP_DIET", "1") != "0":
    try:
        sys.path.insert(0, str(H / ".local/bin"))
        import air10_mcp_diet
        air10_mcp_diet.apply(mcp)
    except ImportError:  # standalone install without the diet module
        pass


def _cli_flags(rest):
    """Split CLI args into positionals + --key value flags (also accepts --key=value)."""
    pos, flags, i = [], {}, 0
    while i < len(rest):
        a = rest[i]
        if a.startswith("--"):
            k, eq, v = a[2:].partition("=")
            k = k.replace("-", "_")
            if eq:
                flags[k] = v
            elif i + 1 < len(rest) and not rest[i + 1].startswith("--"):
                flags[k] = rest[i + 1]; i += 1
            else:
                flags[k] = "1"
        else:
            pos.append(a)
        i += 1
    return pos, flags


def _cli(argv):
    cmd, rest = argv[0], argv[1:]
    pr = lambda r: print(json.dumps(r, indent=1, ensure_ascii=False, default=str))
    if cmd == "build":
        pr(build_index())
    elif cmd == "search":
        pr(_safe(search, " ".join(rest) or "transformer efficiency"))
    elif cmd == "next":
        pr(_safe(next_topics, rest[0] if rest else "gate", int(rest[1]) if len(rest) > 1 else 0))
    elif cmd == "radar":
        pr(_safe(radar, rest[0] if rest else "all"))
    elif cmd == "solve":
        pr(_safe(solve, rest[0] if rest else "help", rest[1] if len(rest) > 1 else "", json.loads(rest[2]) if len(rest) > 2 else None))
    elif cmd == "practice":
        pos, flags = _cli_flags(rest)
        action = pos[0] if pos else "question"
        if len(pos) > 1 and "exam" not in flags:   # legacy: practice question <exam>
            flags["exam"] = pos[1]
        pr(_safe(practice, action, exam=flags.get("exam", ""), subject=flags.get("subject", ""),
                 topic=flags.get("topic", ""), question_id=flags.get("question_id", ""),
                 answer=flags.get("answer", ""), rating=int(flags.get("rating", 0) or 0),
                 n=int(flags.get("n", 1) or 1), provenance=flags.get("provenance", ""),
                 attempt_id=flags.get("attempt_id", "")))
    elif cmd == "tools":
        pr(_safe(tools, rest[0] if rest else "list", json.loads(rest[1]) if len(rest) > 1 else None))
    elif cmd == "selftest":
        r = {"search": _safe(search, "transformer efficiency", limit=3).get("count"), "radar": _safe(radar, "gate").get("ok"),
             "solve": _safe(solve, "tf", "25/(s**2+6*s+25)").get("zeta"), "index": _safe(sources).get("sources", {}).get("question_index")}
        pr(r)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "serve":
        mcp.run()
    else:
        sys.exit(_cli(sys.argv[1:]))
