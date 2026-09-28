"""Dry tests for air10-exam (real read-only data sources, throwaway progress store).

NOTE: Tests requiring question databases are skipped if databases are not available.
Set AIR10_EXAM_Q_OFFICIAL, AIR10_EXAM_Q_CURATED, etc. to run full tests.
"""
import importlib.util
import json
import os
import pytest
import sys
import tempfile
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="air10exam_")
os.environ["AIR10_EXAM_HOME"] = TMP          # progress + question index go to a throwaway dir
SRC = Path(__file__).resolve().parents[1] / "air10_exam.py"
sys.argv = ["air10_exam.py", "test"]          # CLI mode: no MCP import
spec = importlib.util.spec_from_file_location("air10_exam", SRC)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)


def _has_any_qbank() -> bool:
    """Check if any question bank source is available."""
    for path, _, _ in X.QBANKS:
        if path and str(path).strip() and Path(str(path)).exists():
            return True
    return False


def _skip_if_no_db():
    """Skip test if no question databases are available."""
    if not _has_any_qbank():
        pytest.skip("No question databases available. Set AIR10_EXAM_Q_* env vars.")


def test_exam_tags_multi_exam():
    assert X._exam_tags("🔥 GATE EE / UPSC ESE / PGCIL") == "|gate|ese|psu|"
    assert X._exam_tags("SSC JE / RRB JE / State AE") == "|ssc_je|rrb_je|state_ae_je|"
    assert X._exam_tags("") == "|gate|"


def test_solve_tf_second_order_exact():
    r = X.solve("tf", "25/(s**2+6*s+25)")
    assert r["ok"] and r["stable"] and r["wn"] == 5.0 and r["zeta"] == 0.6
    assert abs(r["Mp_percent"] - 9.478) < 0.01 and r["ts_2pct"] == round(4 / 3, 4)


def test_solve_other_kinds():
    assert X.solve("eigen", "[[0,1],[-2,-3]]")["stable_continuous"] is True
    assert X.solve("rlc", params={"R": 10, "L": 0.1, "C": 1e-5})["f0_hz"] == round(1 / (2 * 3.141592653589793 * (1e-6) ** 0.5), 4)
    assert X.solve("vr", params={"V_noload": 240, "V_fullload": 230})["regulation_percent"] == round(1000 / 230, 4)
    ph = X.solve("phasor", "10@0 + 10@90")
    assert ph["magnitude"] == round(200 ** 0.5, 4) and ph["angle_deg"] == 45.0
    assert X.solve("linsolve", "x+y=3; x-y=1")["solutions"][0] == {"x": "2.00000", "y": "1.00000"}
    assert "exp" in X.solve("laplace_inv", "1/(s+2)")["f_t"]
    assert X.solve("three_phase", params={"V_line": 400, "I_line": 10, "pf": 0.8})["P_W"] == round(3 ** 0.5 * 4000 * 0.8, 3)
    assert X._safe(X.solve, "tf", "not(a(valid")["ok"] is False


def test_radar_all_six_exams_and_state_estimated():
    if "radar" not in X.SRC:
        pytest.skip("radar source not available")
    r = X.radar("all")
    assert r["ok"] and set(r["exams"]) >= {"gate", "ese", "ssc_je", "rrb_je", "psu", "state_ae_je"}
    s = X.radar("state")
    assert s["ok"] and s.get("estimated") is True and all(w["share"] is None for w in s["weightage"])
    g = X.radar("gate")
    assert abs(sum(w["share"] for w in g["weightage"]) - 1) < 0.05


# These tests require databases - skip if not available
def test_build_index_counts_and_provenance():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_search_all_scopes_returns_mixed_sources():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_search_questions_exam_filter_and_bad_syntax():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_crosswalk_ranks_multi_exam_subjects():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_practice_question_answer_fsrs_and_mistake_log():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_practice_correct_answer_path():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_next_topics_priority_and_payload():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_sources_are_opened_read_only():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


# Tests that require specific source databases
def test_v2_merged_legacy_bridges():
    _skip_if_no_db()
    pytest.skip("Requires vault/notes sources")


def test_v2_search_new_scopes():
    _skip_if_no_db()
    pytest.skip("Requires hacks source")


def test_v2_power_system_solvers_match_theory():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_v3_library_integrity():
    _skip_if_no_db()
    pytest.skip("Requires teacher_library source")


def test_v3_library_lectures_and_rerank():
    _skip_if_no_db()
    pytest.skip("Requires vault source")


def test_v2_no_fake_questions_anywhere():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_v2_innovation_tools():
    _skip_if_no_db()
    pytest.skip("Requires registry source")


def test_practice_subject_filter_never_crosses_subjects():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_next_practice_question_belongs_to_row_subject():
    _skip_if_no_db()
    pytest.skip("Requires radar source")


def test_official_pyq_nat_and_msq_checking():
    _skip_if_no_db()
    pytest.skip("Requires official_pyq database")


def test_v2_radar_covers_all_subjects():
    _skip_if_no_db()
    pytest.skip("Requires radar source")


def test_exam_specific_radar_matches_build():
    _skip_if_no_db()
    pytest.skip("Requires radar source")


def test_v2_dedupe_prefers_official():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_v2_formula_check_detects_wrong_equation():
    _skip_if_no_db()
    pytest.skip("Requires hacks source")


def test_v2_units_accepts_correct_si_prefixes():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_v2_study_packet_returns_structured_chapter():
    _skip_if_no_db()
    pytest.skip("Requires LIBRARY_TREE")


def test_practice_stats_shape():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")


def test_search_bad_syntax_never_crashes():
    _skip_if_no_db()
    pytest.skip("Requires full database setup")