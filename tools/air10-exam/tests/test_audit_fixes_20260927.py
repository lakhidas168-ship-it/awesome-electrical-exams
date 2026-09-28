"""Audit-fix tests (2026-09-27): one test per verified bug; real read-only sources, throwaway progress."""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TMP = os.environ.get("AIR10_EXAM_HOME") or tempfile.mkdtemp(prefix="air10exam_audit_")
os.environ["AIR10_EXAM_HOME"] = TMP          # progress + question index go to a throwaway dir
SRC = Path(__file__).resolve().parents[1] / "air10_exam.py"
sys.argv = ["air10_exam.py", "test"]          # CLI mode: no MCP import
spec = importlib.util.spec_from_file_location("air10_exam_audit", SRC)
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)

YTB = re.compile(r"^https://youtu\.be/[A-Za-z0-9_-]{11}(\?t=\d+)?$")


def test_fix1_figure_rows_never_served():
    X.build_index()
    assert X._unusable("torque here [figure in source PDF]", "[]", "") is not None
    assert X._unusable("plain stem", "[]", "", figure=1) is not None
    assert X._unusable("plain stem", '["a", "", "c", "d"]', "A") is not None   # one lost option is enough
    q = X._qdb()
    fig = [r[0] for r in q.execute("select qid from q where figure=1")]
    assert len(fig) > 1500   # 468 official + ~2000 collected figure flags survive the build
    meta = X._qmeta()
    assert all(meta[qid][1] for qid in fig)
    assert meta["GATE2020_EE_Q06"][1] is not None   # 4th option lost in extraction
    served = set()
    for subj in ("Control Systems", "Power Systems", "Electrical Machines", "Network Theory",
                 "General Aptitude", "Electromagnetic Fields"):
        r = X.practice("question", exam="gate", subject=subj, n=10)
        assert r["ok"], subj
        served.update(x["id"] for x in r["questions"])
    assert served and not (served & set(fig))
    assert "GATE2025_EE_Q18" not in served and "GATE2026_EE_Q41" not in served


def test_fix2_pyq_never_official_pyq():
    q = X._qdb()
    rows = q.execute("select qid, prov, explanation from q where prov='official_pyq'").fetchall()
    assert rows and all(re.match(r"GATE\d{4}_EE", r["qid"]) for r in rows)   # only organizer-PDF rows
    assert not q.execute("select count(*) from q where qid like 'PYQ:%' and prov='official_pyq'").fetchone()[0]
    r = q.execute("select prov from q where qid='PYQ:GATE_2020_EE_963ec52cd3138086'").fetchone()
    assert r is None or r["prov"] == "pyq_collected"   # dropped as an official-row duplicate, or demoted
    assert q.execute("select count(*) from q where prov='pyq_collected' and explanation like '%coaching copy of official paper%'").fetchone()[0] > 500


def test_fix3_gate_ee_serves_no_other_branch():
    for subj in ("Analog & Digital Electronics", "Control Systems", "Power Systems"):
        r = X.practice("question", exam="gate", subject=subj, n=10)
        assert r["ok"], subj
        for x in r["questions"]:
            assert x.get("branch", "EE") not in ("EC", "IN", "CS", "DA"), (subj, x["id"], x.get("branch"))
    q = X._qdb()
    ec = q.execute("select qid, stem from q where qid='PYQ:GATE_2026_EC_00ca97ed61f997b8'").fetchall()
    assert ec and X._qmeta()[ec[0]["qid"]][1] is not None   # the audit's example: figure row, EC branch
    hits = X.search("shift register flip-flop XOR propagation delay", scope="questions", exam="gate", limit=25)["results"]
    tagged = [h for h in hits if h["id"] == ec[0]["qid"]]
    assert tagged and tagged[0].get("branch") == "EC"   # searchable, tagged with its branch


def test_fix4_dedupe_prefers_official():
    q = X._qdb()
    seen = {}
    for qid, stem in q.execute("select qid, stem from q"):
        h = X._norm_stem(stem)
        assert h and h not in seen, (qid, seen.get(h))   # no normalized-stem duplicate survives
        seen[h] = qid
    assert q.execute("select count(*) from q where qid='GATE2025_EE_Q01'").fetchone()[0] == 1
    assert q.execute("select count(*) from q where qid in ('PYQ:GATE_2025_EE_703932e981de8d4e','PYQ:GATE_2025_EE_ea6028188d612f09')").fetchone()[0] == 0


def test_fix5_radar_covers_all_subjects():
    g = X.radar("gate")
    names = [w["subject"] for w in g["weightage"]]
    for s in ("General Aptitude", "Electromagnetic Fields", "Measurement & Instrumentation", "Digital Electronics"):
        assert s in names, names
    assert abs(sum(w["share"] for w in g["weightage"]) - 1.0) < 0.02
    e = X.radar("ese")
    names = [w["subject"] for w in e["weightage"]]
    for s in ("Engineering Mathematics", "Electrical Materials", "Computer Fundamentals",
              "Basic Electronics Engineering", "Systems & Signal Processing"):
        assert s in names, names
    assert abs(sum(w["share"] for w in e["weightage"]) - 1.0) < 0.02
    assert e.get("estimated") is True


def test_fix6_fsrs_coverage_prior():
    rows = X._qdb().execute(
        "select qid from q where prov='official_pyq' and subject='ENGINEERING_MATHEMATICS'").fetchall()
    served = [r[0] for r in rows if not (X._qmeta().get(r[0]) or (None, True))[1]][:3]
    assert served
    assert X.practice("answer", question_id=served[0], rating=4)["ok"]   # one perfect review, hundreds unseen
    plan = {t["subject"]: t for t in X.next_topics("gate", days_left=130, n=12, clips=False)["plan"]}
    m = plan["Engineering Mathematics"]
    assert m["cards_available"] > 100 and m["coverage"] < 0.05
    assert m["priority"] > 0, m   # one right answer must not zero the subject


def test_fix7_only_real_youtube_urls():
    assert X._watch_url("https://www.youtube.com/watch?v=TEACHER_261_phasor_diagram_of_tr") is None
    assert X._yt_url("yt:i6grqHH9JKs") == "https://youtu.be/i6grqHH9JKs"
    assert X._yt_url("yt:short") is None and X._yt_url("") is None
    pkt = X.tools("study_packet", {"subject": "Power Systems", "n": 5})
    assert pkt["ok"] and pkt.get("lectures")
    forlec = [lec for lec in pkt["lectures"]]
    assert forlec and all(lec["url"] is None or YTB.match(lec["url"]) for lec in forlec)
    assert not any("TEACHER_" in (lec["url"] or "") for lec in forlec)
    clips = [c for t in X.next_topics("gate", days_left=30, n=3)["plan"] for c in t.get("clips", [])]
    assert clips and all(YTB.match(c["url"]) and "?t=" in c["url"] for c in clips)


def test_fix8_errata_overrides_verified():
    r = X.build_index()
    assert set(("GATE2018_EE_Q61", "GATE2023_EE_Q53", "GATE2020_EE_Q31",
                "PYQ:GATE_2020_EE_963ec52cd3138086", "GATE2026_EE_Q41")) <= set(r["errata_applied"])
    assert r["errata_skipped"] == []
    q = X._qdb()
    s61 = q.execute("select stem from q where qid='GATE2018_EE_Q61'").fetchone()[0]
    assert "√3 kV" in s61 and "97.20 to 97.55" in q.execute(
        "select answer from q where qid='GATE2018_EE_Q61'").fetchone()[0]
    s53 = q.execute("select stem from q where qid='GATE2023_EE_Q53'").fetchone()[0]
    assert "π" in s53 and "￰" not in s53
    s31 = q.execute("select stem from q where qid='GATE2020_EE_Q31'").fetchone()[0]
    assert "single-phase" in s31 and "sinLTle" not in s31
    meta = X._qmeta()
    assert meta["GATE2026_EE_Q41"][1] is not None
    dup = meta.get("PYQ:GATE_2020_EE_963ec52cd3138086")
    assert dup is None or dup[1] is not None   # official Q31 wins the normalized-stem dupe; the 'A'-keyed copy never serves


def test_fix9_printed_paper_labels():
    assert X._build_plabel("GATE2018_EE_Q11", "EE", 11) == "EE Q.1"
    assert X._build_plabel("GATE2016_EE_S2_Q54", "EE", 54) == "EE Set-2 Q.44"
    assert X._build_plabel("GATE2026_EE_Q01", "GA", 1) == "GA Q.1"
    assert X._build_plabel("GATE2026_EE_Q41", "EE", 41) == "EE Q.31"
    r = X.practice("question", exam="gate", subject="General Aptitude", n=3)
    assert r["ok"] and all(x.get("paper_label", "").startswith(("GA Q.", "EE Q.", "EE Set-")) for x in r["questions"])


def test_fix10_cli_practice_flags():
    env = dict(os.environ)
    out = subprocess.run([sys.executable, str(SRC), "practice", "question", "--exam", "gate",
                          "--subject", "Control Systems", "--n", "2"],
                         capture_output=True, text=True, timeout=120, env=env)
    assert out.returncode == 0, out.stderr[-500:]
    r = json.loads(out.stdout)
    assert r["ok"] and len(r["questions"]) == 2
    assert all("gate" in x["exams"] for x in r["questions"])
