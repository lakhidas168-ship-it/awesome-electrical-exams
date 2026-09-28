# Awesome Electrical Exams ⚡

> Free, evidence-gated preparation maps for **Electrical Engineering** competitive exams in India:
> GATE EE, UPSC ESE, SSC JE, RRB JE, State AE/JE, PSUs.
> No fees, no sign-up, no terms: every page links to the official source and says honestly how well it was checked.

**→ Start at [tools/air10-exam](tools/air10-exam) — open-source MCP for EE exam study** ·
[Official GATE EE PYQs (2016–2026)](#official-gate-ee-previous-papers-20162026) ·
[Official UPSC ESE PYQs (2017–2025)](#official-upsc-ese-previous-papers-20172025) ·
[Free Official Courses (NPTEL)](#free-official-courses-nptel) ·
[Open Tools](#open-tools) ·
[Overlap Map](resources/overlap-map.md) ·
[All Exams](resources/all-exams.md)

Maintained by **Rajon Das** (an aspirant himself) with an open agent pipeline that works every hour:
[how it works](ops/HIVE.md). Found a mistake? Open an issue with the official link.

---

## 📋 Exams + Official Links

| Exam | Official Body | Syllabus / Notification | Previous Papers |
|------|---------------|-------------------------|-----------------|
| **GATE EE** | IIT (rotating) | [gate2026.iitg.ac.in](https://gate2026.iitg.ac.in) | [Official QPs 2016–2026](#official-gate-ee-previous-papers-20162026) |
| **UPSC ESE (EE)** | UPSC | [upsc.gov.in](https://upsc.gov.in) | [Official QPs 2017–2025](#official-upsc-ese-previous-papers-20172025) |
| **SSC JE (EE)** | SSC | [ssc.gov.in](https://ssc.gov.in) | [ssc.gov.in/Paper-I](https://ssc.gov.in) / [Paper-II](https://ssc.gov.in) |
| **RRB JE (EE)** | Railway Recruitment Boards | [indianrailways.gov.in](https://indianrailways.gov.in) | [rrbonline.in](https://rrbonline.in) |
| **State AE/JE (EE)** | State PSCs / Commissions | Varies by state | Respective state portals |
| **PSU EE (via GATE)** | Individual PSUs | PSU career pages | GATE score + PSU test/interview |

---

## 🗺️ One-Track Plan (GATE EE → ESE → SSC JE → State AE/JE)

A single study sequence that covers the **overlapping syllabus** efficiently. Start here, tick off, move on.

| Phase | Target Exam | Core Subjects (Weightage Order) | Weeks | Checkpoint |
|-------|-------------|----------------------------------|-------|------------|
| 1 | GATE EE | Networks, Control Systems, Power Systems, Machines, Signals, Analog/Digital, EMFT, Measurements | 16–20 | GATE mock ≥55/100 |
| 2 | ESE Paper-I (GS) | Current Affairs, General Science, Engineering Aptitude, Ethics | 6–8 | ESE GS mock ≥180/300 |
| 3 | ESE Paper-II (EE) | Same as GATE + deeper derivations, design problems | 8–10 | ESE EE mock ≥200/300 |
| 4 | SSC JE Paper-II (EE) | Core EE + objective speed practice | 4–6 | SSC JE mock ≥220/300 |
| 5 | State AE/JE | State-specific GK + EE core (use SSC JE as proxy) | 3–4 | State mock qualifying |

> **Provenance**: Weightages derived from `air10-exam exam_radar` across 6 exams (GATE, ESE, SSC JE, RRB JE, State AE/JE, PSU). Crosswalk = topics paying in ≥3 exams. See [data/exam_radar.json](data/exam_radar.json).

---

## 📄 Official Previous Papers

### GATE EE (2016–2026) — Official IIT PDFs Only

| Year | Official PDF Link | Provenance |
|------|-------------------|------------|
| 2026 | https://gate2026.iitg.ac.in/doc/download/2026/QPs/EE.pdf | `official_pyq` |
| 2025 | https://gate2025.iitr.ac.in/doc/2025/2025_QP/EE.pdf | `official_pyq` |
| 2024 | https://gate2027.iitm.ac.in/static/doc/download/2024/EE24S8.pdf | `official_pyq` |
| 2023 | https://gate2027.iitm.ac.in/static/doc/download/2023/ee_2023.pdf | `official_pyq` |
| 2022 | https://gate2027.iitm.ac.in/static/doc/download/2022/ee_2022.pdf | `official_pyq` |
| 2021 | https://gate2027.iitm.ac.in/static/doc/download/2021/ee_2021.pdf | `official_pyq` |
| 2020 | https://gate2026.iitg.ac.in/doc/download/2020/ee_2020.pdf | `official_pyq` |
| 2019 | https://gate2026.iitg.ac.in/doc/download/2019/ee_2019.pdf | `official_pyq` |
| 2018 | https://drive.google.com/file/d/15_ICpSsDqPOvTxa8irh-13zRM9paY-SY/view | `official_pyq` |
| 2017 | https://drive.google.com/file/d/15_ICpSsDqPOvTxa8irh-13zRM9paY-SY/view | `official_pyq` |
| 2016 | https://drive.google.com/file/d/15_ICpSsDqPOvTxa8irh-13zRM9paY-SY/view | `official_pyq` |

> **Source**: Extracted from `~/AIR10_LIBRARY/official_pyq/official_pyq.sqlite` (845 verified questions). Parser script: [scripts/official_pyq.py](scripts/official_pyq.py). License: CC BY 4.0 for text, MIT for code.

### UPSC ESE EE (2017–2025) — Official upsc.gov.in Links Only

| Year | Paper-I (GS) | Paper-II (EE) | Provenance |
|------|--------------|---------------|------------|
| 2025 | [upsc.gov.in](https://upsc.gov.in) | [upsc.gov.in](https://upsc.gov.in) | `official_pyq` |
| 2024 | [upsc.gov.in](https://upsc.gov.in) | [upsc.gov.in](https://upsc.gov.in) | `official_pyq` |
| 2023 | [upsc.gov.in](https://upsc.gov.in) | [upsc.gov.in](https://upsc.gov.in) | `official_pyq` |
| 2022 | [upsc.gov.in](https://upsc.gov.in) | [upsc.gov.in](https://upsc.gov.in) | `official_pyq` |
| 2021 | [upsc.gov.in](https://upsc.gov.in) | [upsc.gov.in](https://upsc.gov.in) | `official_pyq` |
| 2020 | [upsc.gov.in](https://upsc.gov.in) | [upsc.gov.in](https://upsc.gov.in) | `official_pyq` |
| 2019 | [upsc.gov.in](https://upsc.gov.in) | [upsc.gov.in](https://upsc.gov.in) | `official_pyq` |
| 2018 | [upsc.gov.in](https://upsc.gov.in) | [upsc.gov.in](https://upsc.gov.in) | `official_pyq` |
| 2017 | [upsc.gov.in](https://upsc.gov.in) | [upsc.gov.in](https://upsc.gov.in) | `official_pyq` |

> **Note**: Direct PDF URLs on upsc.gov.in change per year. Use the search on upsc.gov.in → "Previous Question Papers" → "Engineering Services". OCR pipeline code published in [scripts/ese_ocr.py](scripts/ese_ocr.py); output marked `provenance=official_pyq` but **unverified until human-verified**. See [data/ese_ee_pyq.jsonl](data/ese_ee_pyq.jsonl).

---

## 🎓 Free Official Courses (NPTEL)

| Course | Institute | Link | Covers |
|--------|-----------|------|--------|
| Basic Electrical Circuits | IIT Kharagpur | [nptel.ac.in/courses/108105159](https://nptel.ac.in/courses/108105159) | Networks, Circuit Theorems |
| Analog Circuits | IIT Bombay | [nptel.ac.in/courses/108102096](https://nptel.ac.in/courses/108102096) | Analog Electronics |
| Digital Circuits | IIT Kharagpur | [nptel.ac.in/courses/108105132](https://nptel.ac.in/courses/108105132) | Digital Electronics |
| Control Engineering | IIT Bombay | [nptel.ac.in/courses/108106098](https://nptel.ac.in/courses/108106098) | Control Systems |
| Power System Analysis | IIT Kharagpur | [nptel.ac.in/courses/108105067](https://nptel.ac.in/courses/108105067) | Power Systems |
| Electrical Machines | IIT Delhi | [nptel.ac.in/courses/108105017](https://nptel.ac.in/courses/108105017) | Machines |
| Electromagnetic Fields | IIT Madras | [nptel.ac.in/courses/108104087](https://nptel.ac.in/courses/108104087) | EMFT |
| Signals and Systems | IIT Bombay | [nptel.ac.in/courses/108104100](https://nptel.ac.in/courses/108104100) | Signals |
| Power Electronics | IIT Bombay | [nptel.ac.in/courses/108102146](https://nptel.ac.in/courses/108102146) | Power Electronics |
| Measurements & Instrumentation | IIT Roorkee | [nptel.ac.in/courses/108105064](https://nptel.ac.in/courses/108105064) | Measurements |

> All NPTEL courses are free to audit. Certificates require exam registration (nominal fee). See [resources/nptel-catalog.md](resources/nptel-catalog.md) for full mapping to GATE/ESE syllabus.

---

## 🔧 Open Tools

| Tool | Description | Repo / Link | License |
|------|-------------|-------------|---------|
| **air10-exam** | One MCP for all EE exams: search, next-topic, practice (FSRS), exact solvers, radar, teacher triangulation, NotebookLM routing | [tools/air10-exam](tools/air10-exam) | MIT (code) / CC BY 4.0 (text) |
| **air10-ee-solvers** | 16 standalone EE solvers: netlist, control, logic, twoport, tf, eigen, laplace_inv, rlc, vr, phasor, linsolve, three_phase, swing, eac, powerflow, per_unit | [tools/air10-ee-solvers](tools/air10-ee-solvers) | MIT |
| **air10-library** | Taxonomy builder: 8-layer syllabus tree, official PYQ harvest, lecture index, NotebookLM catalog | [tools/air10-library](tools/air10-library) | MIT |
| **truthgate** | CI gate: hallucination/contradiction checker for generated content | [ops/truthgate](ops/truthgate) | MIT |
| **sovereign-study-commons-india** | Reference RAG: SQLite/Parquet study lake, SSC_RAG, verifier | [tools/sovereign-study-commons-india](tools/sovereign-study-commons-india) | MIT |

> **See also**: [awesome-indian-exams](https://github.com/lakhidas168-ship-it/awesome-indian-exams) for 118 exams (JEE, NEET, SSC, UPSC CSE, IBPS, CUET, CLAT, CAT, NET, etc.) with 33 shared modules and overlap maps.

---

## 🛡️ Guardrails (Enforced on Every Commit)

- **gitleaks**: No secrets, API keys, tokens, or personal paths in repo
- **PII deny-list**: No emails, phone numbers, Aadhaar, PAN in committed files
- **Path guard**: No `/Users/rajondas`, `/home/rajondas`, `~/.local`, `lakhidas168@gmail.com` (except documented env var names like `AIR10_LIBRARY_PATH`)
- **Provenance honesty**: Every question/fact carries `provenance` field (`official_pyq`, `curated_unverified`, `pyq_collected`, `teacher_derived`). No fake data.
- **No coaching material**: No lecture transcripts, topper copies, or proprietary content. Links only.
- **GitHub ≤1 push/hour/repo** via `~/.hive/publish-github.sh` (hourly gated). Never use git as a message bus.

---

## 📦 Quick Start (air10-exam)

```bash
# Clone and enter
git clone https://github.com/lakhidas168-ship-it/awesome-electrical-exams
cd awesome-electrical-exams/tools/air10-exam

# Install (requires Python 3.11+)
pip install -e .[dev]

# Build your own index from public data (see BUILD_INDEX.md)
export AIR10_LIBRARY_PATH=/path/to/your/public/data
air10-exam build

# Use the MCP server
air10-exam serve

# CLI examples
air10-exam search "power systems stability" --exam gate
air10-exam next --exam gate --days-left 90
air10-exam practice --exam gate --subject "Power Systems" --provenance curated_unverified
air10-exam solve tf "100/(s*(s+10))"
air10-exam radar --exam all
```

See [tools/air10-exam/README.md](tools/air10-exam/README.md) for full documentation, environment variables, and how students build their own index from public sources.

---

## 📜 Licenses

| Content Type | License |
|--------------|---------|
| **Code** (Python, shell, configs, MCP servers) | [MIT](LICENSE.md) |
| **Text** (README, docs, exam maps, radar data, syllabi extracts) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| **Data** (question banks, lecture index, PYQ extracts) | CC BY 4.0 — provenance field mandatory |

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short:
1. Fork → branch → PR with tests
2. All gates must pass: `ops/doctor.sh`, `gitleaks`, `pytest`
3. Only real, sourced content. Link to official sources.
4. Unverified stays marked unverified.

---

## 🔗 Related Repos

- [awesome-indian-exams](https://github.com/lakhidas168-ship-it/awesome-indian-exams) — 118 exams, 33 shared modules, overlap maps
- [awesome-upsc-cse](https://github.com/lakhidas168-ship-it/awesome-upsc-cse) — UPSC Civil Services focused
- [sovereign-study-commons-india](https://github.com/lakhidas168-ship-it/sovereign-study-commons-india) — Reference RAG implementation

---

*Last updated: 2026-09-28 | Maintained by Rajon Das | [Agent pipeline](ops/HIVE.md) runs hourly*