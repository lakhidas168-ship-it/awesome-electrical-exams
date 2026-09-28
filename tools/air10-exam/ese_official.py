"""ESE official source module (2026-09-27, task 02_STUDY_ESE_OFFICIAL_BACKFILL).

Separate module (not an edit of air10_exam.py's bank table) so parallel index tasks
don't collide. air10_exam.py appends EXTRA_QBANKS to its QBANKS at import.

Source: official UPSC ESE Prelims PDFs downloaded ONLY from upsc.gov.in
(Previous Question Papers pages + per-exam nodes), stored read-only under
$AIR10_EXAM_Q_OFFICIAL_ESE (default: empty). Built by ese_ee/_build_ese.py from tesseract
OCR halves. A row exists ONLY if stem + all 4 options parsed; figure-only or
unparseable questions are skipped (counted in the build log, never invented).
Official answer keys are not exposed on upsc.gov.in live pages (verified 2026-09-27:
answer-key archives view holds the current year only; per-exam nodes list no
Answer Key rows), so answer_key='' for every row.
"""
import os
from pathlib import Path

_ESE_DIR = os.environ.get("AIR10_EXAM_Q_OFFICIAL_ESE", "").strip()
EXTRA_QBANKS = (
    [(Path(_ESE_DIR), "official_sqlite", "official_pyq")]
    if _ESE_DIR and Path(_ESE_DIR).exists()
    else []
)