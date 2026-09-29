# air10-exam — Open Source MCP for EE Exam Study

**One MCP server for all Electrical Engineering competitive exams in India:**
GATE EE, UPSC ESE, SSC JE, RRB JE, State AE/JE, PSUs.

## What it does

| Tool | Purpose |
|------|---------|
| `exam_search` | Search hacks, formulas, questions, 763K+ timestamped lecture segments, notes, NotebookLM sources |
| `exam_next` | What to study next: FSRS memory decay × exam weightage × days left |
| `exam_practice` | Question → answer (auto-checked, FSRS-scheduled, mistakes logged) |
| `exam_solve` | 16 exact EE solvers: tf, margins, eigen, laplace_inv, rlc, vr, phasor, linsolve, three_phase, swing, eac, powerflow, per_unit, netlist, control, logic, twoport |
| `exam_radar` | Pattern + weightage of 6 exams; crosswalk = topics that pay in ≥3 exams |
| `exam_tools` | Lecture clips, teacher triangulation, trap radar, NotebookLM routing, study packets |

## Quick Start

```bash
# Clone the repo
git clone https://github.com/lakhidas168-ship-it/awesome-electrical-exams
cd awesome-electrical-exams/tools/air10-exam

# Install dependencies (add ,solvers for the netlist/control/power-flow solvers)
pip install -e '.[dev]'

# Set up your data paths (see "Building Your Index" below)
export AIR10_EXAM_HOME=~/.air10_exam_data
export AIR10_EXAM_DATA=~/.air10/data

# Build the question index from your sources
air10-exam build

# Run the MCP server
air10-exam serve
```

## Building Your Index from Public Data

The open-source code **does not include** any databases, models, or personal data. You build your own index from public sources:

### Required Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `AIR10_EXAM_HOME` | Writable directory for progress.sqlite, questions.sqlite (default: `./.air10_exam_data`) | `~/my_exam_data` |
| `AIR10_EXAM_DATA` | Read-only data directory (default: `~/.air10/data`) | `~/data` |
| `AIR10_EXAM_Q_OFFICIAL` | GATE EE official PYQ SQLite (from IIT PDFs) | `~/data/gate_official_pyq.sqlite` |
| `AIR10_EXAM_Q_OFFICIAL_ESE` | UPSC ESE official PYQ SQLite (from upsc.gov.in PDFs) | `~/data/ese_official.sqlite` |
| `AIR10_EXAM_Q_CURATED` | Curated questions (provenance: curated_unverified) | `~/data/curated.sqlite` |
| `AIR10_EXAM_Q_TOP100` | SSC JE Top 100 JSON | `~/data/ssc_je_top100.json` |
| `AIR10_EXAM_Q_COLLECTED` | Collected PYQs (provenance: pyq_collected) | `~/data/pyq_collected.sqlite` |
| `AIR10_EXAM_Q_QUIZ` | Practice quiz banks | `~/data/quiz.sqlite` |
| `AIR10_EXAM_VAULT` | Unified transcript vault (763K segments) | `~/data/transcript_vault.sqlite` |
| `AIR10_EXAM_LIBRARY` | Teacher library (50K+ transcripts) | `~/data/teacher_library.sqlite` |
| `AIR10_EXAM_NLM_CATALOG` | NotebookLM catalog (320 notebooks) | `~/data/nlm_catalog.sqlite` |
| `AIR10_EXAM_LIBRARY_TREE` | AIR10_LIBRARY lecture folders | `~/AIR10_LIBRARY` |
| `AIR10_EXAM_FLASHRANK` | FlashRank model directory | `~/models/flashrank` |
| `AIR10_EXAM_FLASHRANK` | FlashRank model directory | `~/models/flashrank` |

### Public Data Sources

1. **GATE EE Official Papers (2016–2026)**: Download PDFs from [gate2026.iitg.ac.in](https://gate2026.iitg.ac.in) → Previous Question Papers. Parse with `scripts/official_pyq.py`.

2. **UPSC ESE Official Papers (2017–2025)**: Download from [upsc.gov.in](https://upsc.gov.in) → Examinations → Previous Question Papers → Engineering Services. OCR with Tesseract (see `scripts/ese_ocr.py`).

3. **NPTEL Lectures**: Free courses at [nptel.ac.in](https://nptel.ac.in). Use `air10-library` to build the 8-layer taxonomy.

4. **SSC JE Top 100**: Publicly shared question sets (provenance: `curated_unverified`).

5. **NotebookLM**: Create your own notebooks from public sources.

### Building Steps

```bash
# 1. Set up directory structure
mkdir -p ~/exam_data ~/data

# 2. Download and parse official GATE papers
export AIR10_EXAM_Q_OFFICIAL=~/data/gate_official_pyq.sqlite
python3 scripts/official_pyq.py --download --parse --output $AIR10_EXAM_Q_OFFICIAL

# 3. Download and OCR UPSC ESE papers
export AIR10_EXAM_Q_OFFICIAL_ESE=~/data/ese_official.sqlite
python3 scripts/ese_ocr.py --download --parse --output $AIR10_EXAM_Q_OFFICIAL_ESE

# 4. Build lecture index (requires air10-library)
export AIR10_EXAM_VAULT=~/data/transcript_vault.sqlite
export AIR10_EXAM_LIBRARY=~/data/teacher_library.sqlite
export AIR10_EXAM_LIBRARY_TREE=~/AIR10_LIBRARY
python3 -m air10_library build --syllabus gate_ee --out ~/data/taxonomy.md

# 5. Build the combined question index
export AIR10_EXAM_HOME=~/exam_data
air10-exam build

# 6. Verify
air10-exam selftest
```

## CLI Usage

```bash
# Search
air10-exam search "power systems stability" --exam gate --limit 10

# What to study next (90 days left for GATE)
air10-exam next --exam gate --days-left 90

# Practice with curated questions
air10-exam practice question --exam gate --subject "Power Systems" --provenance curated_unverified --n 5

# Answer a question (auto-checked, FSRS-scheduled)
air10-exam practice answer --question-id "CUR:EE_PS_001" --answer "B"

# Check your stats
air10-exam practice stats

# Exact math solvers
air10-exam solve tf "100/(s*(s+10))"
air10-exam solve margins "100/(s*(s+10))"
air10-exam solve netlist "V1 1 0 step 10; R1 1 2 2; C1 2 0 1"
air10-exam solve per_unit "base_mva=100 base_kv=11 z_pu=0.1+j0.2"

# Exam radar
air10-exam radar --exam all
air10-exam radar --exam gate --subject "Power Systems"

# Teacher triangulation (3 teachers on one topic)
air10-exam tools triangulate --topic "power factor correction"

# Trap radar (common misconceptions)
air10-exam tools trap_radar --topic "induction motor starting"

# NotebookLM routing
air10-exam tools route --topic "power systems stability"

# Study packet for a chapter
air10-exam tools study_packet --subject "Power Systems" --chapter "Load Flow Analysis"
```

## Architecture

```
air10_exam.py      # Main MCP server (FastMCP), 6 tools, CLI entry point
ee_solvers.py      # 16 exact EE solvers (SymPy, SciPy, lcapy, python-control)
transcripts.py     # Transcript lookup (teacher library + unified vault)
math_safety.py     # Numerical safety: bounds, tolerances, validation
ese_official.py    # UPSC ESE official question bank (separate module)
prerequisites.py   # Dependency checks
tests/             # Unit tests (pytest)
skill/SKILL.md     # Skill definition for Antigravity/Claude Code
```

## Provenance Honesty

Every question carries a `provenance` field:

| Provenance | Meaning |
|------------|---------|
| `official_pyq` | Official GATE/ESE question + final answer key from organizing IIT/UPSC |
| `curated_unverified` | Curated local question; official origin NOT verified |
| `pyq_collected` | Previous-year question from public paper/solution PDF (coaching copy of official); verify answers |
| `practice` | Practice question written from teacher lectures (NOT an official PYQ) |
| `upsc_cse_pyq` | UPSC CSE previous-year question (not Electrical) |

**Never invent PYQ years or numbers.** Unverified stays marked unverified.

## License

- **Code**: MIT License (see `LICENSE.md`)
- **Text/Data**: CC BY 4.0 — provenance field mandatory

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md). In short:
1. Fork → branch → PR with tests
2. All gates must pass: `gitleaks`, `pytest`, path guard
3. Only real, sourced content. Link to official sources.
4. Unverified stays marked unverified.

## Related Repos

- [awesome-indian-exams](https://github.com/lakhidas168-ship-it/awesome-indian-exams) — 118 exams, 33 shared modules
- [awesome-upsc-cse](https://github.com/lakhidas168-ship-it/awesome-upsc-cse) — UPSC CSE focused
- sovereign-study-commons-india — reference RAG implementation (not public yet)