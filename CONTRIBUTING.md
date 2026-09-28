# Contributing

Students, teachers and toppers are all welcome. The one rule: **anything a student might act on must be
traceable to an official source.**

## Fixing or adding exam facts

1. Find the official document (notification, information brochure, syllabus PDF) on an official domain.
   The accepted domains are listed in [`ops/official-domains.txt`](ops/official-domains.txt). To add a domain,
   say in your PR why it is official.
2. Edit the exam page in `exams/`. Put the document's URL under `## Official sources`.
3. Set `verification: official` and `last_verified: <today>` only if the official document supports every
   number on the page. Otherwise leave it as `secondary` or `unverified`.
4. Run the gate: `python3 scripts/validate.py` (Python 3.11+, no dependencies).

## Adding an exam page

1. Find or add the exam in [`registry/exams.toml`](registry/exams.toml): id, name, family, conducting body,
   official site (if you know it) and the shared modules it tests.
2. Create `exams/<family>/<id>.md`, copying the structure of an existing page. Frontmatter keys: `title`,
   `exam_id` (the file name), `conducting_body`, `official_site`, `cycle`, `last_verified`, `verification`.
   Required sections: `At a glance`, `Official sources`, `Exam pattern`, `Syllabus`, `Free resources`.
3. Don't edit the README index, `resources/all-exams.md`, `resources/overlap-map.md` or `UPDATES.md`. They are
   regenerated from the registry automatically.

## Adding a shared module

Modules (`modules/<id>.md`) are syllabus blocks shared by many exams. Each needs a `[[module]]` entry in the
registry and frontmatter `title` + `module_id`. See [`modules/quant-aptitude.md`](modules/quant-aptitude.md).

## Adding resources

- Free and legal only, linked to the publisher. No links to Telegram, Google Drive, Mega, Scribd or other file
  dumps (the gate rejects them).
- No copied text from coaching material, paid courses, books or lecture transcripts. Write in your own words.
- Paid resources are out of scope for this list.

## Licensing of contributions

By contributing, you agree that your content is published under CC BY-SA 4.0 and your code under MIT.
