#!/usr/bin/env python3
"""Zero-cost hive agent: a small tool-using agent on free LLM tiers. Stdlib only.

It fills any hive lane when the owner's own agents (JEVX, Hermes, OpenCode) are not running, for example in
GitHub Actions, where GitHub Models is free with the workflow's GITHUB_TOKEN. Providers are tried in the order
set in ops/hive.toml; a provider without a key, or one that is rate-limited, is skipped.

    free_agent.py --lane hermes "<prompt>"          # the hive runner appends the prompt as the last argument

Env:
  HIVE_TASK_ID     task being worked on (limits which receipt path the lane may touch)
  HIVE_FETCH_LOG   JSONL file where every fetch is recorded by code (becomes evidence in the receipt)
  HIVE_NOTES       where finish() writes the agent's notes (default ops/.notes.md)
  HIVE_LLM_BASE_URL / HIVE_LLM_API_KEY / HIVE_LLM_MODEL   extra OpenAI-compatible endpoint, tried first
  OPENCODE_API_KEY (OpenCode Go), GITHUB_MODELS_TOKEN or GITHUB_TOKEN, GEMINI_API_KEY, OPENROUTER_API_KEY,
  GROQ_API_KEY, OLLAMA_BASE_URL. Provider order per lane: ops/hive.toml [free_agent.lane_providers].

Exit: 0 finished · 75 no provider available (rate limits etc.; the runner frees the task) · 2 bad usage.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html.parser
import io
import json
import os
import re
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

CONTENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTENT / "scripts"))
import hive_gate  # noqa: E402
import validate  # noqa: E402

EX_TEMPFAIL = 75
USER_AGENT = "awesome-electrical-exams-hive/1.0 (+https://github.com/lakhidas168-ship-it)"

PROVIDERS = {
    "opencode-go": ("https://opencode.ai/zen/go/v1", ("OPENCODE_API_KEY",)),
    "github": ("https://models.github.ai/inference", ("GITHUB_MODELS_TOKEN", "GITHUB_TOKEN")),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", ("GEMINI_API_KEY",)),
    "openrouter": ("https://openrouter.ai/api/v1", ("OPENROUTER_API_KEY",)),
    "groq": ("https://api.groq.com/openai/v1", ("GROQ_API_KEY",)),
    "ollama": (os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"), ()),
}


class NoProvider(Exception):
    """Every configured provider is missing, failing or rate-limited."""


def load_config() -> dict:
    path = CONTENT / "ops" / "hive.toml"
    return tomllib.loads(path.read_text(encoding="utf-8")).get("free_agent", {}) if path.exists() else {}


# ------------------------------------------------------------------ LLM access with fallback

class LLM:
    def __init__(self, config: dict, lane: str | None = None) -> None:
        self.routes: list[tuple[str, str, str, str]] = []  # (provider, base, key, model)
        if os.environ.get("HIVE_LLM_BASE_URL"):
            self.routes.append(("custom", os.environ["HIVE_LLM_BASE_URL"], os.environ.get("HIVE_LLM_API_KEY", ""),
                                os.environ.get("HIVE_LLM_MODEL", "default")))
        models = config.get("models", {})
        order = config.get("lane_providers", {}).get(lane) or config.get("providers", list(PROVIDERS))
        for name in order:
            if name not in PROVIDERS:
                continue
            base, key_envs = PROVIDERS[name]
            key = next((os.environ[k] for k in key_envs if os.environ.get(k)), "")
            if key_envs and not key:
                continue  # no key configured: skip silently
            for model in models.get(name, []):
                self.routes.append((name, base, key, model))
        self.dead: set[tuple[str, str]] = set()
        self.last_route = ""
        # OpenCode Go's HTTP API rejects requests without a session id (HTTP 400 MissingSessionID, 2026-09-28).
        self.session = f"ses_hive_{os.getpid()}_{int(time.time())}"

    def chat(self, messages: list[dict], tools: list[dict] | None = None, max_tokens: int = 1800) -> dict:
        for provider, base, key, model in self.routes:
            if (provider, model) in self.dead or (provider, "*") in self.dead:
                continue
            body = {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": max_tokens}
            if tools:
                body["tools"] = tools
                body["tool_choice"] = "auto"
            for attempt in range(2):
                try:
                    extra = {"x-opencode-session": self.session} if provider == "opencode-go" else None
                    resp = post_json(f"{base.rstrip('/')}/chat/completions", body, key, extra=extra)
                    self.last_route = f"{provider}:{model}"
                    return resp["choices"][0]["message"]
                except urllib.error.HTTPError as exc:
                    if exc.code == 429 and attempt == 0:
                        time.sleep(float(os.environ.get("HIVE_429_WAIT", "20")))  # pooled keys (CLIProxyAPI) free up fast
                        continue
                    if exc.code == 429 or exc.code in (401, 403):
                        self.dead.add((provider, "*"))  # rate-limited or unauthorised: whole provider out
                        log(f"{provider} unavailable (HTTP {exc.code}), falling back")
                        break
                    if exc.code >= 500 and attempt == 0:
                        time.sleep(5)
                        continue
                    self.dead.add((provider, model))  # unknown model, bad request: try the next model
                    log(f"{provider}:{model} failed (HTTP {exc.code}), trying next")
                    break
                except (urllib.error.URLError, TimeoutError, OSError, KeyError, IndexError, ValueError) as exc:
                    self.dead.add((provider, "*"))
                    log(f"{provider} unreachable ({type(exc).__name__}), falling back")
                    break
        raise NoProvider("no LLM provider available")


def post_json(url: str, body: dict, key: str, timeout: int = 180, extra: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT, **(extra or {})}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def log(msg: str) -> None:
    print(f"[free-agent] {msg}", file=sys.stderr, flush=True)


# ------------------------------------------------------------------ fetching with code-recorded evidence

class _Text(html.parser.HTMLParser):
    SKIP = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        if tag in ("p", "br", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def fetch(url: str, log_path: str | None, max_bytes: int = 4_000_000) -> tuple[str, dict]:
    """GET a URL, return (text, record). The record is appended to the fetch log by code, not by the model."""
    record = {"url": url, "at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}
    text = ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read(max_bytes)
            record.update(status=resp.status, final_url=resp.geturl(),
                          content_type=resp.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as exc:
        record.update(status=exc.code, error=str(exc))
        raw = b""
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        record.update(status=0, error=type(exc).__name__)
        raw = b""
    record["bytes"] = len(raw)
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    host = urlparse(record.get("final_url", url)).netloc
    record["official"] = validate.host_matches(host, validate.load_official_hosts(CONTENT))
    if raw:
        if raw[:5] == b"%PDF-" or "pdf" in record.get("content_type", ""):
            text = pdf_text(raw)
        else:
            parser = _Text()
            parser.feed(raw.decode("utf-8", errors="replace"))
            text = re.sub(r"[ \t\r\f\v]+", " ", "".join(parser.parts))
            text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
            if parser.links:
                text += "\n\nLINKS:\n" + "\n".join(parser.links[:80])
    if log_path:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    return text, record


def pdf_text(raw: bytes) -> str:
    try:
        from pypdf import PdfReader  # optional; installed in the cloud workflow
    except ImportError:
        return "[PDF: install pypdf to extract text]"
    try:
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join((page.extract_text() or "") for page in reader.pages[:40])
    except Exception as exc:  # malformed PDFs are common on government sites
        return f"[PDF could not be parsed: {type(exc).__name__}]"


# ------------------------------------------------------------------ tools

TOOL_SPECS = [
    ("list_files", "List files under a folder of the content root.", {"folder": "string"}),
    ("read_file", "Read part of a text file. Returns at most `limit` characters from `offset`.",
     {"path": "string", "offset": "integer", "limit": "integer"}),
    ("write_file", "Create or overwrite a text file (only paths your lane may change).",
     {"path": "string", "content": "string"}),
    ("replace_in_file", "Replace one exact occurrence of `old` with `new` in a file. Cheaper than rewriting it.",
     {"path": "string", "old": "string", "new": "string"}),
    ("fetch_url", "Download a web page or PDF and return its text. Every fetch is recorded as evidence.",
     {"url": "string", "offset": "integer"}),
    ("run_gate", "Run the content gate (scripts/validate.py) and return its output.", {}),
    ("finish", "End the task. `notes`: sources opened and what each confirmed, what you could not confirm, "
               "and what you changed.", {"notes": "string"}),
]


def tool_schemas() -> list[dict]:
    out = []
    for name, desc, params in TOOL_SPECS:
        required = [p for p in params if p not in ("offset", "limit", "folder")]
        out.append({"type": "function", "function": {
            "name": name, "description": desc,
            "parameters": {"type": "object", "properties": {p: {"type": t} for p, t in params.items()},
                           "required": required}}})
    return out


class Tools:
    def __init__(self, lane: str, task: str, fetch_log: str | None, notes_path: Path) -> None:
        self.lane, self.task, self.fetch_log, self.notes_path = lane, task, fetch_log, notes_path
        self.finished = False
        self.writes: list[str] = []

    def _resolve(self, rel: str) -> Path | None:
        path = (CONTENT / rel).resolve()
        try:
            path.relative_to(CONTENT)
        except ValueError:
            return None
        return path

    def _writable(self, rel: str) -> str | None:
        path = self._resolve(rel)
        if path is None:
            return f"refused: {rel} is outside the content folder"
        repo_path = f"{CONTENT.name}/{path.relative_to(CONTENT).as_posix()}"
        if repo_path.startswith(f"{CONTENT.name}/ops/done/"):
            return "refused: receipts are written by the runner, not by agents"
        if not hive_gate.allowed(self.lane, self.task, repo_path, CONTENT.name):
            return f"refused: the {self.lane} lane may not change {rel}"
        return None

    def call(self, name: str, args: dict) -> str:
        try:
            return getattr(self, f"t_{name}")(**args)
        except AttributeError:
            return f"unknown tool {name}"
        except TypeError as exc:
            return f"bad arguments for {name}: {exc}"

    def t_list_files(self, folder: str = ".") -> str:
        base = self._resolve(folder)
        if base is None or not base.is_dir():
            return f"not a folder: {folder}"
        files = sorted(p.relative_to(CONTENT).as_posix() for p in base.rglob("*")
                       if p.is_file() and "__pycache__" not in p.parts)
        return "\n".join(files[:300]) + (f"\n... {len(files) - 300} more" if len(files) > 300 else "")

    def t_read_file(self, path: str, offset: int = 0, limit: int = 5000) -> str:
        p = self._resolve(path)
        if p is None or not p.is_file():
            return f"no such file: {path}"
        text = p.read_text(encoding="utf-8", errors="replace")
        limit = max(200, min(int(limit), 8000))
        chunk = text[int(offset): int(offset) + limit]
        more = len(text) - (int(offset) + len(chunk))
        return chunk + (f"\n[... {more} more characters; read again with offset={int(offset) + len(chunk)}]" if more > 0 else "")

    def t_write_file(self, path: str, content: str) -> str:
        refusal = self._writable(path)
        if refusal:
            return refusal
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
        self.writes.append(path)
        return f"wrote {path} ({len(content)} characters)"

    def t_replace_in_file(self, path: str, old: str, new: str) -> str:
        refusal = self._writable(path)
        if refusal:
            return refusal
        p = self._resolve(path)
        if not p.is_file():
            return f"no such file: {path}"
        text = p.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            return f"refused: `old` occurs {count} times in {path}; it must occur exactly once"
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
        self.writes.append(path)
        return f"replaced 1 occurrence in {path}"

    def t_fetch_url(self, url: str, offset: int = 0) -> str:
        if not url.startswith(("http://", "https://")):
            return "refused: only http(s) URLs"
        text, rec = fetch(url, self.fetch_log)
        head = (f"status={rec.get('status')} official_domain={rec['official']} bytes={rec['bytes']} "
                f"final_url={rec.get('final_url', url)}")
        chunk = text[int(offset): int(offset) + 6000]
        more = len(text) - (int(offset) + len(chunk))
        return head + "\n\n" + chunk + (f"\n[... {more} more characters; fetch again with offset]" if more > 0 else "")

    def t_run_gate(self) -> str:
        res = subprocess.run([sys.executable, str(CONTENT / "scripts" / "validate.py")],
                             capture_output=True, text=True)
        out = (res.stdout + res.stderr).strip().splitlines()
        return "\n".join(out[-40:])

    def t_finish(self, notes: str = "") -> str:
        self.notes_path.parent.mkdir(parents=True, exist_ok=True)
        self.notes_path.write_text(notes.strip() + "\n", encoding="utf-8")
        self.finished = True
        return "finished"


# ------------------------------------------------------------------ agent loop

SYSTEM = """You are the {lane} lane of an automated team that maintains a free, public study guide for Indian
competitive exams. You work by calling tools; you cannot see files you have not read. Paths are relative to the
content folder. Be economical: read only what you need, prefer replace_in_file for small edits, and call run_gate
before finish. Never invent facts: every exam fact must come from an official document you fetched with
fetch_url, and pages you could not verify keep their honest status. When done, call finish with notes."""


def trim(messages: list[dict], budget: int) -> None:
    """Keep the conversation under the free tier's per-request limit by blanking the oldest tool outputs."""
    def size() -> int:
        return sum(len(json.dumps(m)) for m in messages)
    for m in messages[2:-2]:
        if size() <= budget:
            return
        if m.get("role") == "tool" and not m["content"].startswith("[older"):
            m["content"] = "[older tool output removed to stay within the free-tier context limit]"


def run(lane: str, prompt: str, llm: LLM, tools: Tools, max_steps: int, budget: int) -> int:
    messages = [{"role": "system", "content": SYSTEM.format(lane=lane)}, {"role": "user", "content": prompt}]
    schemas = tool_schemas()
    for step in range(max_steps):
        trim(messages, budget)
        try:
            msg = llm.chat(messages, schemas)
        except NoProvider as exc:
            log(str(exc))
            return EX_TEMPFAIL
        calls = msg.get("tool_calls") or []
        messages.append({"role": "assistant", "content": msg.get("content") or "", **({"tool_calls": calls} if calls else {})})
        log(f"step {step + 1} via {llm.last_route}: {', '.join(c['function']['name'] for c in calls) or 'text'}")
        if not calls:
            messages.append({"role": "user", "content": "Use the tools. Call finish(notes) when you are done."})
            continue
        for call in calls:
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.call(call["function"]["name"], args if isinstance(args, dict) else {})
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": result[:12000]})
        if tools.finished:
            return 0
    log("step budget used up without finish()")
    if not tools.notes_path.exists():
        tools.t_finish("Stopped at the step limit before calling finish. Files written: " + ", ".join(tools.writes))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lane", required=True, choices=["hermes", "opencode", "jevx"])
    ap.add_argument("--max-steps", type=int)
    ap.add_argument("prompt", nargs="?", help="prompt text (the hive runner passes it as the last argument)")
    ap.add_argument("--prompt-file")
    args = ap.parse_args(argv)
    prompt = Path(args.prompt_file).read_text(encoding="utf-8") if args.prompt_file else args.prompt
    if not prompt:
        ap.error("a prompt is required")
    config = load_config()
    llm = LLM(config, args.lane)
    if not llm.routes:
        log("no provider configured (set GITHUB_TOKEN in Actions, or a key, or HIVE_LLM_BASE_URL)")
        return EX_TEMPFAIL
    notes = Path(os.environ.get("HIVE_NOTES", CONTENT / "ops" / ".notes.md"))
    tools = Tools(args.lane, os.environ.get("HIVE_TASK_ID", "none"), os.environ.get("HIVE_FETCH_LOG"), notes)
    # Env overrides (Mac, 2026-09-28): large-context providers (DeepSeek, CLIProxyAPI Gemini) ran out of the 14 steps
    # tuned for GitHub Models' 8k window while still reading files; the cloud keeps the hive.toml defaults.
    return run(args.lane, prompt, llm, tools,
               args.max_steps or int(os.environ.get("HIVE_MAX_STEPS") or config.get("max_steps", 14)),
               int(os.environ.get("HIVE_CONTEXT_CHARS") or config.get("context_chars", 22000)))


if __name__ == "__main__":
    sys.exit(main())
