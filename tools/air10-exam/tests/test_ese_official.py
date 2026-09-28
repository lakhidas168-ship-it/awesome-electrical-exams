"""ESE official backfill tests (2026-09-27, task 02): real read-only sources, throwaway index.

Uses the already-loaded air10_exam module if present (same pattern as the other
test files: AIR10_EXAM_HOME points at a temp dir, never the real progress store).

NOTE: These tests require the official ESE database at $AIR10_EXAM_Q_OFFICIAL_ESE
and the GATE official database at $AIR10_EXAM_Q_OFFICIAL.
Set these environment variables to run the tests, or they will be skipped.
"""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

TMP = tempfile.mkdtemp(prefix="air10exam_ese_")
os.environ["AIR10_EXAM_HOME"] = TMP
SRC = Path(__file__).resolve().parents[1] / "air10_exam.py"
sys.argv = ["air10_exam.py", "test"]
if "air10_exam" in sys.modules:
    X = sys.modules["air10_exam"]
else:
    sys.path.insert(0, str(SRC.parent))
    spec = importlib.util.spec_from_file_location("air10_exam", SRC)
    X = importlib.util.module_from_spec(spec)
    sys.modules["air10_exam"] = X
    spec.loader.exec_module(X)

ESE_DB = os.environ.get("AIR10_EXAM_Q_OFFICIAL_ESE", "").strip()
GATE_DB = os.environ.get("AIR10_EXAM_Q_OFFICIAL", "").strip()

if not any(p and str(p).strip() and Path(str(p)).exists() for p, _, _ in X.QBANKS):
    pytestmark = pytest.mark.skip(
        "No question banks configured. Set AIR10_EXAM_Q_* env vars to run data-dependent tests.")


def _con_ese():
    if not ESE_DB or not Path(ESE_DB).exists():
        pytest.skip(f"ESE official DB not found at {ESE_DB}. Set AIR10_EXAM_Q_OFFICIAL_ESE to run.")
    c = sqlite3.connect(f"file:{ESE_DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def _con_gate():
    if not GATE_DB or not Path(GATE_DB).exists():
        pytest.skip(f"GATE official DB not found at {GATE_DB}. Set AIR10_EXAM_Q_OFFICIAL to run.")
    c = sqlite3.connect(f"file:{GATE_DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def test_ese_source_db_exists_and_schema():
    c = _con_ese()
    cols = [r[1] for r in c.execute("PRAGMA table_info(questions)")]
    assert {"id", "exam", "year", "organizer", "section", "qno", "stem",
            "options_json", "answer_key", "pdf", "source_url", "key_url"} <= set(cols)
    n = c.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    assert n >= 1500, f"only {n} ESE rows parsed (9y x 250q = 2250 max)"
    c.close()


def test_ese_rows_exam_organizer_and_years():
    c = _con_ese()
    assert c.execute("SELECT COUNT(*) FROM questions WHERE exam != '|ese|'").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM questions WHERE organizer != 'UPSC'").fetchone()[0] == 0
    have = {(r[0], r[1]) for r in c.execute("SELECT year, section FROM questions GROUP BY year, section")}
    for y in range(2017, 2026):
        assert (y, "GS") in have and (y, "EE") in have, f"missing paper for {y}"
    c.close()


def test_ese_rows_parse_quality_and_unique_qno():
    c = _con_ese()
    bad = 0
    for r in c.execute("SELECT id, stem, options_json FROM questions"):
        r = dict(r)
        if len(r["stem"] or "") < 20:
            bad += 1
            continue
        try:
            opts = json.loads(r["options_json"])
        except ValueError:
            bad += 1
            continue
        if not isinstance(opts, dict) or set(opts) != {"a", "b", "c", "d"}:
            bad += 1
    assert bad == 0, f"{bad} rows with bad stem/options"
    dup = c.execute("SELECT COUNT(*) - COUNT(DISTINCT id) FROM questions").fetchone()[0]
    assert dup == 0
    c.close()


def test_ese_no_fabricated_keys():
    c = _con_ese()
    assert c.execute("SELECT COUNT(*) FROM questions WHERE answer_key != ''").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM questions WHERE key_url != ''").fetchone()[0] == 0
    c.close()


def test_ese_pdfs_on_disk_and_upsc_only_sources():
    c = _con_ese()
    pdfs = {r[0] for r in c.execute("SELECT DISTINCT pdf FROM questions")}
    assert len(pdfs) == 18, f"expected 18 PDFs, got {len(pdfs)}"
    for p in pdfs:
        assert Path(p).exists() and Path(p).stat().st_size > 100_000, f"missing/small {p}"
    srcs = {r[0] for r in c.execute("SELECT DISTINCT source_url FROM questions")}
    assert srcs == {"https://www.upsc.gov.in/examinations/previous-question-papers"}, srcs
    c.close()


def test_official_pyq_sqlite_has_no_ese_rows():
    """The GATE official DB stays untouched: ESE lives only in ese_official.sqlite."""
    c = _con_gate()
    n = c.execute("SELECT COUNT(*) FROM questions WHERE exam LIKE '%ese%'").fetchone()[0]
    c.close()
    assert n == 0


def test_index_build_includes_ese_official():
    banks = [str(p) for p, _, _ in X.QBANKS]
    assert any("ese_official.sqlite" in b for b in banks), "ese bank not hooked into QBANKS"
    r = X.build_index()
    assert r["ok"], r
    assert r["questions"].get("ese_official.sqlite", 0) >= 1500
    s = X.sources()["sources"]["question_index"]
    assert s["by_exam"].get("ese", 0) > 0


def test_ese_search_returns_official_rows_with_ese_explanation():
    res = X.search("transformer", scope="questions", exam="ese", limit=10)
    assert res["ok"] and res["count"] > 0
    off = [h for h in res["results"] if h.get("provenance") == "official_pyq"]
    assert off, "no official_pyq rows for exam=ese"
    assert all("ese" in (h.get("exams") or []) for h in res["results"])
    for h in off:
        assert "ESE" in (h.get("explanation") or ""), h.get("explanation")
        assert "GATE" not in (h.get("explanation") or ""), h.get("explanation")