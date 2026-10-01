# Evidence-aware task feeder

The AIR10 queue previously treated a result filename as proof that a task met its acceptance criteria. A rejected transcript result could therefore become "done" again on the next feeder run, allowing dependent work to start prematurely.

This Python standard-library utility preserves existing results, requires hash-bound independent check receipts before accepting completion, and holds waiting dependents until their prerequisites are accepted. Concurrent feeder instances share a file lock; queue/register updates use atomic replacement.

Run against your own AIR10 task tree:

```sh
python3 feed_frogs.py --home /path/to/your/home --limit 6
python3 test_feed_frogs.py
```

The tree contains `.air10/frog/TOP100_FROGS.json` and `.air10/opencode_pool/{todo,running,done,waiting}`. A frog has `rank`, `title`, `done_when`, `depends_on`, and `status`. Existing completed claims without accepted receipts become `verification_pending`. No result is deleted. Blocked queued tasks move to `waiting`; running tasks are left for their current owner.

An independent reviewer records `.air10/frog/acceptance/FROG_<rank>.json` with:

- `rank` and `criterion_sha256` computed with `criterion_digest(frog)`.
- `checks`: actual captured dry, stress, and live check records, each carrying `phase`, `argv`, integer `returncode=0`, `output_path`, and `output_sha256`.
- `artifacts`: actual output artifact records carrying `path` and `sha256`.

Commands in receipts are never executed by the feeder. Hash checks establish that recorded outputs and artifacts still match; the reviewer must separately establish that each check measures the task's criterion and uses authentic source data. A hash cannot prove that generated text is a real transcript, that a question has the correct official answer, or that a benchmark measures the intended hardware.

Validation covers rejected completion claims, stale outputs/artifacts, changed criteria, malformed receipts, failed checks, missing phases, dependency cycles, unknown prerequisites, reversible holding, preservation of running work, and 40 concurrent invocation attempts at concurrency four. Fixtures exercise queue control only and are not student content.

Code follows this repository's AGPL-3.0 license. This utility contains no chat histories, private resource data, credentials, or third-party teaching material.
