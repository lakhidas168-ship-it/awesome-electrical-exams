# Contributing

Students, teachers and toppers are all welcome. The one rule: **anything a student might act on must be
traceable to an official source.**

## Adding or fixing EE facts

1. Find the official document (notification, information brochure, syllabus, question paper)
   on an official domain (`gate*.iitm/iitg/iitr.ac.in`, `upsc.gov.in`, `ssc.gov.in`,
   `rrbapply.gov.in` / regional `rrb*.gov.in`, `indianrailways.gov.in`, `nptel.ac.in`).
2. Add the link to the README or the matching file in `resources/`.
3. Open every link you add and confirm it loads; record the check in `docs/LINK_CHECK.md`.
4. Never copy coaching material, lecture transcripts, or proprietary content — links only.
   Never invent numbers, dates, cut-offs, or paper URLs. Advice must be labelled
   **(suggestion)**, never stated as fact.

## Adding to `tools/air10-exam`

1. Work in a branch, add tests under `tools/air10-exam/tests/`.
2. The code must work with zero bundled data: all data paths come from
   `AIR10_EXAM_*` environment variables, and tests must pass in a temp dir
   (`AIR10_EXAM_HOME=$(mktemp -d)`).
3. Gates before any commit: `gitleaks detect --no-git -s . --redact` clean,
   no personal paths or emails, `pytest tools/air10-exam/tests` green.
