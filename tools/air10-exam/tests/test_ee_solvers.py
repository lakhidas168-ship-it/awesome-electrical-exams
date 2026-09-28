"""Known-answer tests for ee_solvers (hand-derived results, not library self-consistency)."""
import math
import sys
from pathlib import Path

import pytest
import sympy as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ee_solvers as E  # noqa: E402


def test_netlist_divider_and_thevenin():
    r = E.netlist("V1 1 0 10\nR1 1 2 2\nR2 2 0 3", "all", "2", "0")
    assert r["ok"], r
    assert sp.sympify(r["node_voltages"]["2"]) == 6                     # 10 * 3/(2+3)
    assert sp.sympify(r["thevenin"]["Voc"]) == 6 and sp.nsimplify(r["thevenin"]["Zth"]) == sp.Rational(6, 5)   # 2||3


def test_netlist_rc_step_transient():
    r = E.netlist("V1 1 0 step 10; R1 1 2 2; C1 2 0 1", "elements", elements=["C1"])
    t = sp.Symbol("t", positive=True)
    v = sp.sympify(r["elements"]["C1"]["v"], locals={"t": t}).subs(sp.Heaviside(t), 1)
    assert sp.simplify(v - 10 * (1 - sp.exp(-t / 2))) == 0            # tau = RC = 2 s


@pytest.mark.parametrize("bad", ["V1 1 0 __import__('os').getcwd()", "R1 1 2 open('x')", "X1 1 0 5", "R1 1 2", "R1 1 2 step 5",
                                 "V1 1 0 (lambda: 1)()", "R1 1; 2 3"])
def test_netlist_rejects_unsafe_or_malformed(bad):
    assert E.netlist(bad)["ok"] is False


def test_control_second_order():
    r = E.control({"num": [25], "den": [1, 6, 0]})                       # open loop 25/(s(s+6)) -> closed loop 25/(s^2+6s+25)
    assert r["ok"], r
    cl = r["closed_loop_unity_feedback"]
    z = 6 / (2 * 5)
    assert cl["overshoot_pct"] == pytest.approx(100 * math.exp(-z * math.pi / math.sqrt(1 - z * z)), abs=0.05)   # 9.48 %
    assert r["system_type"] == 1 and sp.sympify(r["error_constants_open_loop"]["Kv"]) == sp.Rational(25, 6)
    assert cl["stable"] and cl["dc_gain"] == pytest.approx(1.0)


def test_control_state_space_controllability():
    r = E.control({"A": [[0, 1], [-2, -3]], "B": [[0], [1]], "C": [[1, 0]]})
    assert r["ok"] and r["controllable"] and r["observable"]
    r2 = E.control({"A": [[-1, 0], [0, -2]], "B": [[1], [0]], "C": [[1, 1]]})
    assert r2["controllable"] is False and r2["rank_ctrb"] == 1


def test_logic_expression_and_minterms_agree():
    a = E.logic("A'B + AB' + AB")                                        # = A + B
    assert a["ok"] and a["minterms"] == [1, 2, 3] and a["minimal_SOP"] in ("A | B", "B | A")
    b = E.logic(minterms=[0, 2, 5, 7], variables=["A", "B", "C"])       # = A'C' + AC
    assert b["ok"] and set(b["maxterms"]) == {1, 3, 4, 6}
    assert E.logic("__import__('os')")["ok"] is False and E.logic("A.__class__")["ok"] is False


def test_twoport_z_to_abcd_reciprocal():
    r = E.twoport({"Z": [[4, 2], [2, 6]]})
    assert r["ok"] and r["ABCD"] == [[2.0, 10.0], [0.5, 3.0]]           # A=z11/z21, B=dz/z21, C=1/z21, D=z22/z21
    assert r["reciprocal"] and not r["symmetric"] and r["AD_minus_BC"] == 1.0
    back = E.twoport({"ABCD": [[2, 10], [0.5, 3]]})
    assert back["Z"] == [[4.0, 2.0], [2.0, 6.0]]


def test_study_packet_joins_stores():
    import air10_exam as X
    if not X.LIBRARY_TREE:
        pytest.skip("LIBRARY_TREE not set")
    if not (X.LIBRARY_TREE / "taxonomy_spec.json").exists():
        pytest.skip("8-layer library not built on this machine")
    r = X.study_packet(topic="speed control of dc motor", n=3)
    assert r["ok"] and r["key"] == ["GATE_ESE_EE", "ELECTRICAL_MACHINES", "DC_MACHINES"]
    assert "DC machines" in r["official_syllabus_gate2026"] and r["weightage"]["gate"][0]["subject"] == "Electrical Machines"
    assert set(r["solvers"]) == {"vr", "three_phase", "per_unit"} and r["practice_questions"]
    c = X.study_packet(subject="control systems", chapter="root locus")
    assert c["key"][1:] == ["CONTROL_SYSTEMS", "ROOT_LOCUS"] and [w["subject"] for w in c["weightage"]["gate"]] == ["Control Systems"]
    assert X.study_packet(topic="zzqq nothing")["ok"] is False


def test_official_pyq_nat_and_msq_checking(tmp_path, monkeypatch):
    import air10_exam as X
    if not X.QBANKS:
        pytest.skip("No question banks configured")
    try:
        q = X._qdb().execute("select * from q where prov='official_pyq' and answer like '% to %' limit 1").fetchone()
    except RuntimeError:
        pytest.skip("official PYQ bank not accessible")
    if not q:
        pytest.skip("official PYQ bank not present")
    monkeypatch.setattr(X, "PROGRESS", tmp_path / "progress.sqlite")      # never touch the real FSRS state
    lo, hi = (float(x) for x in q["answer"].split(" to "))
    assert X.practice("answer", question_id=q["qid"], answer=str((lo + hi) / 2))["correct"] is True
    assert X.practice("answer", question_id=q["qid"], answer=str(hi + 10))["correct"] is False
    assert X.practice("answer", question_id=q["qid"], answer="abc")["ok"] is False
    m = X._qdb().execute("select * from q where prov='official_pyq' and answer like '%;%' limit 1").fetchone()
    assert X.practice("answer", question_id=m["qid"], answer=m["answer"].replace(";", ","))["correct"] is True
    assert X.practice("answer", question_id=m["qid"], answer=m["answer"][0])["correct"] is (m["answer"] == m["answer"][0])
