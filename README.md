# Awesome Electrical Exams ⚡

> A curated list of **official sources and free resources** for Electrical Engineering
> competitive exams in India: GATE EE, UPSC ESE (EE), SSC JE (EE), RRB JE (EE),
> State AE/JE (EE), PSU recruitment (EE).
>
> Every link below points to an official source and was opened and checked on
> 2026-09-28 (see [docs/LINK_CHECK.md](docs/LINK_CHECK.md)).
> Anything that is advice rather than fact is marked **(suggestion)**.

- [Exams + official links](#-exams--official-links)
- [Official previous papers](#-official-previous-papers)
- [Free official courses (NPTEL)](#-free-official-courses-nptel)
- [One-track study sequence (suggestion)](#️-one-track-study-sequence-suggestion)
- [Open tools](#-open-tools)
- [Related](#-related)

Found a mistake? Open an issue with the official link.

---

## 📋 Exams + official links

| Exam | Official site | Per-exam page (hub) |
|------|---------------|---------------------|
| **GATE EE** | [gate2027.iitm.ac.in](https://gate2027.iitm.ac.in) (GATE 2027 organising institute) | [gate-ee.md](https://github.com/lakhidas168-ship-it/awesome-indian-exams/blob/main/awesome-indian-exams/exams/engineering/gate-ee.md) |
| **UPSC ESE (EE)** | [upsc.gov.in](https://upsc.gov.in) | [upsc-ese-ee.md](https://github.com/lakhidas168-ship-it/awesome-indian-exams/blob/main/awesome-indian-exams/exams/engineering/upsc-ese-ee.md) |
| **SSC JE (EE)** | [ssc.gov.in](https://ssc.gov.in) | [ssc-je-ee.md](https://github.com/lakhidas168-ship-it/awesome-indian-exams/blob/main/awesome-indian-exams/exams/engineering/ssc-je-ee.md) |
| **RRB JE (EE)** | [rrbapply.gov.in](https://www.rrbapply.gov.in/) (application portal) · [indianrailways.gov.in](https://indianrailways.gov.in) | [rrb-je-ee.md](https://github.com/lakhidas168-ship-it/awesome-indian-exams/blob/main/awesome-indian-exams/exams/engineering/rrb-je-ee.md) |
| **State AE/JE (EE)** | Varies by state — see the hub page | [state-ae-je.md](https://github.com/lakhidas168-ship-it/awesome-indian-exams/blob/main/awesome-indian-exams/exams/engineering/state-ae-je.md) |
| **PSU EE (via GATE)** | Individual PSU career pages — see the hub page | [psu-ee.md](https://github.com/lakhidas168-ship-it/awesome-indian-exams/blob/main/awesome-indian-exams/exams/engineering/psu-ee.md) |

Detailed per-exam pages (pattern, syllabus, sources) live in the hub repo
[awesome-indian-exams](https://github.com/lakhidas168-ship-it/awesome-indian-exams);
this repo keeps only EE-specific resources and the open-source study tool.

---

## 📄 Official previous papers

Download papers only from the organisers' own sites. Exact PDF URLs change every
year, so start from the home page and follow the site's question-paper archive:

- **GATE EE** — recent organising institutes (each site hosts its year's papers):
  [GATE 2027 (IIT Madras)](https://gate2027.iitm.ac.in),
  [GATE 2026 (IIT Guwahati)](https://gate2026.iitg.ac.in),
  [GATE 2025 (IIT Roorkee)](https://gate2025.iitr.ac.in).
  Older papers are archived on the respective organising institute's GATE site.
- **UPSC ESE** — [upsc.gov.in](https://upsc.gov.in) → "Previous Question Papers" →
  "Engineering Services Examination".
- **SSC JE** — [ssc.gov.in](https://ssc.gov.in) → candidate / examination archives.
- **RRB JE** — [rrbapply.gov.in](https://www.rrbapply.gov.in/) and the regional
  Railway Recruitment Board websites linked from
  [indianrailways.gov.in](https://indianrailways.gov.in).

See also [resources/gate-ee-papers.md](resources/gate-ee-papers.md) and
[resources/ese-ee-papers.md](resources/ese-ee-papers.md).

---

## 🎓 Free official courses (NPTEL)

Courses on [nptel.ac.in](https://nptel.ac.in) are free to audit; check each course
page for certification details.

| Course | Covers |
|--------|--------|
| [Basic Electrical Circuits](https://nptel.ac.in/courses/108105159) (IIT Kharagpur) | Networks, circuit theorems |
| [Analog Circuits](https://nptel.ac.in/courses/108102096) (IIT Bombay) | Analog electronics |
| [Digital Circuits](https://nptel.ac.in/courses/108105132) (IIT Kharagpur) | Digital electronics |
| [Control Engineering](https://nptel.ac.in/courses/108106098) (IIT Bombay) | Control systems |
| [Power System Analysis](https://nptel.ac.in/courses/108105067) (IIT Kharagpur) | Power systems |
| [Electrical Machines](https://nptel.ac.in/courses/108105017) (IIT Delhi) | Machines |
| [Electromagnetic Fields](https://nptel.ac.in/courses/108104087) (IIT Madras) | EMFT |
| [Signals and Systems](https://nptel.ac.in/courses/108104100) (IIT Bombay) | Signals and systems |
| [Power Electronics](https://nptel.ac.in/courses/108102146) (IIT Bombay) | Power electronics |
| [Measurements & Instrumentation](https://nptel.ac.in/courses/108105064) (IIT Roorkee) | Measurements |

See [resources/nptel-courses.md](resources/nptel-courses.md).

---

## 🗺️ One-track study sequence (suggestion)

**(Suggestion — not a rule, not based on cut-offs.)** The EE syllabi of these
exams overlap heavily, so one possible order is:

1. **GATE EE core** — Networks, Control Systems, Power Systems, Machines,
   Signals & Systems, Analog/Digital Electronics, EMFT, Measurements.
2. **ESE Paper-I (General Studies)** — current affairs, general science,
   engineering aptitude, ethics.
3. **ESE technical papers** — GATE core plus deeper derivations and design problems.
4. **SSC JE / State AE-JE** — EE core with objective speed practice; state GK as
   per the state notification.

Details: [resources/one-track-plan.md](resources/one-track-plan.md).

---

## 🔧 Open tools

| Tool | Description | License |
|------|-------------|---------|
| [tools/air10-exam](tools/air10-exam) | MCP server + CLI for EE exam study: question search, what-to-study-next, practice with auto-check, exact EE solvers, exam pattern radar. Ships code only — you build your own index from public sources. | MIT |

```bash
# Enter the tool directory
cd awesome-electrical-exams/tools/air10-exam

# Install (requires Python 3.11+)
pip install -e .[dev]

# Point the tool at your own public data (see tools/air10-exam/README.md)
export AIR10_EXAM_HOME=~/.air10_exam_data
air10-exam build

# CLI examples (real commands — see `air10-exam` with no args for help)
air10-exam search "power systems stability"
air10-exam next gate 90
air10-exam solve tf "100/(s*(s+10))"
air10-exam radar all
air10-exam selftest

# Run as an MCP server
air10-exam serve
```

---

## 🔗 Related

- [awesome-indian-exams](https://github.com/lakhidas168-ship-it/awesome-indian-exams) —
  the hub repo with per-exam pages for all Indian competitive exams (the EE pages
  are linked in the table above).

---

## 📜 Licenses

| Content type | License |
|--------------|---------|
| Code (`tools/`) | [MIT](LICENSE.md) |
| Text (README, docs, resources) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: only real, sourced content —
link to official sources, never copy coaching material, never invent numbers.

---

*Maintained by Rajon Das.*

---

<!-- topper-updater:ee:begin -->
## 🗺️ Strategy — PYQ patterns

- [strategy/gate-ee/pyq-patterns.md](strategy/gate-ee/pyq-patterns.md) — GATE EE five-year previous-year-question pattern.
- [strategy/ese-ee/pyq-patterns.md](strategy/ese-ee/pyq-patterns.md) — UPSC ESE (EE) five-year previous-year-question pattern.

See [strategy/README.md](strategy/README.md).
<!-- topper-updater:ee:end -->
