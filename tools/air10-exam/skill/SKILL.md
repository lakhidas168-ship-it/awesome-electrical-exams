---
name: air10-exam
description: Use for ANY Electrical Engineering exam study with Rajon (GATE EE, UPSC ESE, SSC JE, RRB JE, State AE/JE, PSUs) - search hacks/PYQs/lectures, what to study next, practice with auto-check + FSRS, exact EE math (control, power systems, circuits), teacher triangulation, NotebookLM routing, Gemini Study Notebook sessions. One MCP (air10-exam) replaces jarvis study tools, air10-study*, circuital-rag, quiz engines and the Hermes supertutor skills.
---

# air10-exam — one skill for all EE exam study (merged 2026-09-27)

Replaces: air10-pyq-first, air10-question-generator, air10-dynamic-selector, air10-exact-resume, per-unit-normalizer
(Hermes supertutor), air10-study (Gemini Study Notebook bridge), the jevx `jarvis` study actions and ~40 study CLIs.

## Tools (MCP server `air10-exam`)
| Need | Call |
|---|---|
| Find anything (hacks, questions, exact lecture moment, insights, notes, NotebookLM source) | `exam_search(query, scope="all", exam, subject)` |
| What to study now | `exam_next(exam, days_left)` → subjects ranked by weightage × (1 − FSRS recall) × urgency, each with a question + timestamped clips |
| Practice | `exam_practice("question", exam, subject, provenance)` → `exam_practice("answer", question_id, answer)` → `exam_practice("stats")` |
| Exact math | `exam_solve(kind, expression, params)`: tf, margins, eigen, laplace_inv, rlc, vr, phasor, linsolve, three_phase, swing, eac, powerflow, per_unit |
| Pattern / weightage | `exam_radar(exam)`; crosswalk = subjects that pay in the most exams |
| Teachers disagree? | `exam_tools("triangulate", {"topic": ...})` — same concept from 3 teachers + lethal trap |
| Traps | `exam_tools("trap_radar", {"topic": ...})` |
| Ask NotebookLM | `exam_tools("route", {"topic": ...})` → notebook id + account, then notebooklm MCP `nlm_query(query, target=<notebook_id>)` |
| Related exams | `exam_tools("exam_family", {"exam": "gate"})` |
| Gemini Study Notebook | `exam_tools("gemini_study", {"action": "status|resume|next|launch|prepare"})` |
| New lecture | `exam_tools("youtube_transcript", {"url": ...})` (network) |

## Rules (keep these — they are the lessons of 9 months)
1. **PYQ-first, honestly.** Prefer `provenance="curated_unverified"` (old name `curated_pyq` still works; 110 curated items whose official year/shift is NOT yet verified — the old "top 100" file was a duplicate). `practice` = teacher-derived (180). Former `generated` (9,484) and
   `template` banks were fake and are gone (Trash 2026-09-27); never invent PYQ years or numbers.
2. **Verify numbers with `exam_solve`** before stating any numeric answer; show the formula used.
3. **Variants (question generator):** from a parent question make 5 variants — parameter inversion, boundary stress (R→0, X→∞,
   δ→π), topology change, misconception trap, multi-concept hybrid — and solve each with `exam_solve`; say clearly they are practice variants (never store or present them as PYQs).
4. **Exact resume:** start with `exam_practice("stats")` + `exam_next(...)`; never paste old chat history into context.
5. **Per-unit:** always convert to one base with `exam_solve("per_unit", ...)` before adding impedances.
6. **State AE/JE** weightage is not published: use SSC JE / ESE Paper-II as a proxy and say so.
7. Answer Rajon in Hinglish, short; he prefers audio (podcast) summaries for long outputs.

## Chapter study packet + new solvers (2026-09-27)
- `exam_tools` tool=`study_packet` args `{topic: "speed control of dc motor"}` or `{subject, chapter}` -> official GATE 2026 syllabus line,
  weightage (GATE/ESE/SSC JE), best lectures from $AIR10_EXAM_LIBRARY_TREE (8-layer folders: syllabus > subject > chapter > major topic > topic >
  sub topic > micro topic > sub micro topic), practice questions, matching exam_solve kinds, reference GitHub repos. Start chapter work here.
- `exam_solve` kind=`netlist` (expression = 'V1 1 0 step 10; R1 1 2 2; C1 2 0 1'), `control` (G='100/(s*(s+10))' or num/den or A,B,C),
  `logic` ("A'B + AB'" or minterms+variables), `twoport` (Z|Y|ABCD|h matrix). Use them to CHECK every numeric answer before trusting it.
