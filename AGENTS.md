# For AI agents working on this repo (cloud Claude Code, Codex, OpenCode, Hermes)

Read this first. It says what runs where, so you don't redo or fight the Mac side.

## Two halves, one backlog
- **Mac (owner's laptop, runs while it is on):** `~/code/awesome-electrical-exams` is a clone of a LOCAL bare repo
  `~/.hive/hub.git`. `awesome-electrical-exams/ops/hive-loop.sh` runs Hermes (Muse 1.3 free), OpenCode (OpenCode Go,
  DeepSeek V4.1 Flash) and HTTP free-agent workers. They claim tasks and push `agent/*` branches to the LOCAL
  repo; `~/.hive/judge-loop.sh` runs `ops/judge.py --publish` locally. Config: `~/.hive/agents.env`.
- **GitHub (this repo):** receives ONE gated, batched commit per hour from `~/.hive/publish-github.sh`
  (validate --strict, unit tests, gitleaks, path/PII deny-list). Commits you land on `main` here are merged back
  into the Mac hub by the same script before it publishes, so the two halves stay in sync.

## Rules that are not negotiable
- **Never use git as a message bus.** No claim refs, heartbeat commits or per-task pushes to GitHub, and no
  schedule on `hive-cloud.yml`. The owner's previous GitHub account was flagged as spam for exactly that. The
  global pre-push guard allows ≤20 pushes/day/repo.
- **Only real, sourced content.** Link to official sources; never copy coaching material, lecture transcripts or
  topper copies; never invent numbers or dates. Unverified stays marked unverified.
- Keep the guardrail files (gates, judge, runner, agentctl, harvest, doctor, workflows) intact; propose changes in
  a PR with tests.

## How a cloud session helps best
Work in a branch and open a PR here (content pages, registry, modules, tooling with tests). The hourly Mac sync
pulls `main`. Tasks that need the owner's disk or logins are `where = "mac"` in `ops/tasks.toml`; leave those to
the Mac. The cloud session cannot see the Mac; everything it needs to know is in this file and `ops/HIVE.md`.

## Open items for the Claude session on the Mac
- **Switch on the website** (the cloud session has no settings access): run
  `gh api -X POST repos/lakhidas168-ship-it/awesome-electrical-exams/pages -f build_type=workflow`
  (HTTP 409 means it is already on). `.github/workflows/pages.yml` then deploys on the next push to `main`, to
  https://lakhidas168-ship-it.github.io/awesome-electrical-exams/ with the open data at `/data/exams.json`.
- **More free LLM providers** (docs in `awesome-electrical-exams/docs/FREE-LLM-APIS.md`): wire Cerebras, NVIDIA NIM,
  Mistral, SambaNova, Cloudflare Workers AI and Ollama Cloud into `ops/free_agent.py` PROVIDERS and
  `ops/hive.toml` (you hold the newer local copies of both files), with a test, then add the owner's keys to
  `~/.hive/agents.env` under the env var names listed there. Never schedule the hive on GitHub.