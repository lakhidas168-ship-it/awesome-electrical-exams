#!/usr/bin/env python3
"""transcripts.py - ONE lookup for "full transcript text of video X" (replaces ~/SOVEREIGN_TRANSCRIPT_VAULT/raw_transcripts, 2026-09-27).

Stores, in order (all read-only, stdlib only so any python can import this file):
  1. teacher_library.sqlite  videos     - 50,830 rows copied from the raw files (sha256-verified). TRUTH: 21,339 of them are only
     LAKHIDAS168 manifest JSON stubs (no transcript; their 02_TRANSCRIPTS_RAW folder is gone) -> skipped here, then the stub's
     canonical YouTube id is tried; the 8,807 that had no local text were recovered from sha256-verified blobs (table recovered). Rows with a manifest header + text return just the text. YouTube IP-block error strings count as no text.
  2. teacher_library.sqlite  fragments  - 541 short (<600 char) bodies that existed nowhere else
     teacher_library.sqlite  extra      - LAKHIDAS168 transcript_fts rows found nowhere else (ids 'lakhidas-<rowid>', + extra_fts)
     teacher_library.sqlite  rescue     - raw files whose text the vault only had partly (e.g. vault capped at 49,983 chars)
     teacher_library.sqlite  alt_texts  - other versions of a video's transcript (circuital NotebookLM texts); versions(id), alt_fts
  3. unified vault          youtube_videos.raw/cleaned_transcript or joined transcript_segments (longest wins)
Coverage proof: $AIR10_EXAM_LIBRARY/RAW_TRANSCRIPTS_RETIRE.json

CLI:  transcripts.py <video_id> [--json] [--max N]   (text mode prints the old raw-file layout: header, 40 '=', body)
      transcripts.py --search <words...> [--json] [--max N]
      transcripts.py --stats [--json]
"""
import json, os, re, sqlite3, sys
from contextlib import closing
from pathlib import Path

H = Path.home()
LIBRARY = Path(os.environ.get("AIR10_EXAM_LIBRARY", env("AIR10_EXAM_LIBRARY", Path.cwd() / "teacher_library.sqlite")))
VAULT = Path(os.environ.get("AIR10_EXAM_VAULT",
                            env("AIR10_EXAM_VAULT", "")))
SEP = "=" * 40


def clean_id(video_id):
    v = str(video_id or "").strip().replace("video:", "")
    m = re.search(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{6,})", v)
    return m.group(1) if m else re.sub(r"[^A-Za-z0-9_-]", "", v)


def _ro(p):
    return closing(sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5))


YT_ERROR = "Could not retrieve a transcript"   # youtube-transcript-api IP-block message stored as if it were a transcript


def is_junk(text):
    return not (text or "").strip() or (text or "").lstrip().startswith(YT_ERROR)


def unstub(text):
    """Library rows imported from LAKHIDAS168 manifests start with a JSON record (effect_id, raw_path, ...).
    -> (manifest dict | None, real transcript text after it | '' ). 21,339 rows are manifest-only (text not local)."""
    t = (text or "").lstrip()
    if not (t.startswith("{") and '"effect_id"' in t[:400]):
        return None, text or ""
    try:
        obj, end = json.JSONDecoder().raw_decode(t)
    except ValueError:
        return None, text
    return obj, t[end:].strip()


def _from_library(vid):
    """-> (hit with real text | None, manifest of a text-less stub | None)"""
    if not LIBRARY.exists():
        return None, None
    manifest = None
    with _ro(LIBRARY) as con:
        tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        for table in ("videos", "fragments", "extra", "rescue", "recovered"):
            if table not in tables:
                continue
            r = con.execute(f"select video_id, title, domain, source, url, text from {table} where video_id = ?", (vid,)).fetchone()
            if not r:
                continue
            m, text = unstub(r[5])
            if is_junk(text):
                manifest = manifest or m
                continue
            title, url = r[1] or "", r[4] or ""
            if title.startswith("URL:"):   # 47k rows: an old header parser swallowed the URL line into an empty TITLE
                url, title = url or title[4:].strip(), ""
            return ({"video_id": r[0], "title": title or (m or {}).get("source_title", ""), "domain": r[2] or "", "source": r[3] or "",
                     "url": url or (m or {}).get("source_url", ""), "text": text, "store": f"teacher_library.{table}"}, None)
    return None, manifest


def _from_vault(vid):
    if not VAULT.exists():
        return None
    with _ro(VAULT) as con:
        r = con.execute("select title, channel, topic, url, raw_transcript, cleaned_transcript from youtube_videos where video_id = ?",
                        (vid,)).fetchone()
        segs = " ".join(s for (s,) in con.execute("select segment_text from transcript_segments where video_id = ? "
                                                   "order by start_time_s", (vid,)) if s)
    cands = [("vault.youtube_videos.raw_transcript", r[4] if r else ""), ("vault.youtube_videos.cleaned_transcript", r[5] if r else ""),
             ("vault.transcript_segments", segs)]
    cands = [c for c in cands if not is_junk(c[1])]
    if not cands:
        return None
    store, text = max(cands, key=lambda c: len(c[1] or ""))
    return {"video_id": vid, "title": (r[0] if r else "") or "", "domain": (r[2] if r else "") or "",
            "source": (r[1] if r else "") or "", "url": (r[3] if r else "") or "", "text": text, "store": store}


def is_junk_id(vid):
    """ids moved out by $AIR10_LIBRARY/junk.py (both models: unrelated) - their export sits in the Trash"""
    if not LIBRARY.exists():
        return False
    with _ro(LIBRARY) as con:
        try:
            return con.execute("select 1 from junk where video_id = ?", (vid,)).fetchone() is not None
        except sqlite3.Error:
            return False


def get(video_id, max_chars=0, include_junk=False):
    """-> dict(video_id, title, domain, source, url, text, chars, store) or None. max_chars>0 truncates text."""
    vid = clean_id(video_id)
    if not vid or (not include_junk and is_junk_id(vid)):
        return None
    hit, manifest = _from_library(vid)
    hit = hit or _from_vault(vid)
    cv = clean_id((manifest or {}).get("canonical_video_id") or "")
    if not hit and cv and cv != vid:   # stub rows use hash ids; the real text often sits under the YouTube id
        hit = _from_library(cv)[0] or _from_vault(cv)
    if not hit:
        return None
    if manifest and not hit["title"]:
        hit["title"] = manifest.get("source_title", "")
    if not hit["url"] and re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
        hit["url"] = f"https://youtube.com/watch?v={vid}"
    hit["chars"] = len(hit["text"])
    if max_chars and max_chars > 0:
        hit["text"] = hit["text"][:max_chars]
    return hit


def _fts_or(q, max_terms=6):
    words = [w for w in re.split(r"\W+", q or "") if len(w) > 2][:max_terms]
    return " OR ".join(f'"{w}"' for w in words)


def search(query, limit=5):
    """BM25 full-text search over real transcripts (library + extra + vault); manifest stubs and YouTube error rows skipped.
    -> [{video_id, title, snippet, bm25, store}] best first (bm25: lower = better, comparable only within one store)."""
    q, limit = _fts_or(query), max(1, min(int(limit or 5), 50))
    if not q:
        return []
    q = f'({q}) NOT "{YT_ERROR}"'   # FTS-level filter: never read document text just to drop error rows
    out = []

    def ranked(con, fts, content, title_col, text_col, n, skip=frozenset()):
        # rank first (bm25 over the index only), snippet() just for the winners - snippet on every match is what made this slow
        src, a = (f"{fts} join {content} c on c.rowid = {fts}.rowid", "c") if content else (fts, fts)
        top = con.execute(f"select {fts}.rowid, {a}.video_id, {a}.{title_col}, bm25({fts}) r from {src} "
                          f"where {fts} match ? order by r limit ?", (q, n + (3 * n if skip else 0))).fetchall()
        top = [t for t in top if t[1] not in skip][:n]
        for rid, vid, title, rank in top:
            snip = con.execute(f"select snippet({fts}, {text_col}, '[[', ']]', '...', 20) from {fts} where {fts} match ? and rowid = ?",
                               (q, rid)).fetchone()
            out.append({"video_id": vid, "title": title or "", "snippet": snip[0] if snip else "", "bm25": round(rank, 3)})
        return top

    if LIBRARY.exists():
        with _ro(LIBRARY) as con:
            tables = {r[0] for r in con.execute("select name from sqlite_master")}
            stubs = frozenset(v for (v,) in con.execute("select video_id from stub_manifest where text_after_manifest = 0")) \
                if "stub_manifest" in tables else frozenset()
            n0 = len(out); ranked(con, "videos_fts", "videos", "title", 3, limit, stubs)
            for o in out[n0:]: o["store"] = "teacher_library"
            for fts, content, label in (("extra_fts", "extra", "teacher_library.extra"), ("alt_fts", "alt_texts", "teacher_library.alt_texts")):
                if fts in tables:
                    n0 = len(out); ranked(con, fts, content, "title", 1, limit)
                    for o in out[n0:]: o["store"] = label
    if VAULT.exists():
        with _ro(VAULT) as con:
            n0 = len(out); ranked(con, "transcripts_fts", None, "title", 5, limit)
            for o in out[n0:]: o["store"] = "vault"
    out.sort(key=lambda r: r["bm25"])
    return out[:limit]


def versions(video_id):
    """Other stored transcript versions of one video (e.g. a NotebookLM text next to the served ASR text)."""
    vid = clean_id(video_id)
    if not vid or not LIBRARY.exists():
        return []
    with _ro(LIBRARY) as con:
        if not con.execute("select 1 from sqlite_master where name = 'alt_texts'").fetchone():
            return []
        return [{"video_id": v, "source": s, "title": t, "chars": n, "text": x}
                for v, s, t, n, x in con.execute("select video_id, source, title, chars, text from alt_texts where video_id = ?", (vid,))]


def exists(video_id):
    return get(video_id, max_chars=1) is not None


def as_raw_file(hit):
    """Old raw_transcripts/<id>.txt layout, so callers that parsed it keep working."""
    return (f"VIDEO_ID: {hit['video_id']}\nTITLE: {hit['title']}\nURL: {hit['url']}\nDOMAIN: {hit['domain']}\n"
            f"SOURCE: {hit['source']}\nCHARS: {hit['chars']}\n{SEP}\n\n{hit['text']}")


def stats():
    """Counts of transcripts with REAL text, from the last audit (build_stub_manifest.py -> teacher_library.meta).
    Manifest-only stubs and YouTube IP-block error messages are excluded."""
    out = {"library_real_texts": 0, "library_fragments": 0, "library_recovered_texts": 0, "vault_real_texts": 0, "no_local_text_stubs": 0,
           "vault_yt_error_rows": 0, "audited": ""}
    try:
        with _ro(LIBRARY) as con:
            meta = dict(con.execute("select k, v from meta"))
            out["library_fragments"] = con.execute("select count(*) from fragments").fetchone()[0]
        for k in ("library_real_texts", "library_recovered_texts", "vault_real_texts", "vault_yt_error_rows"):
            out[k] = int(meta.get(k, 0))
        out["no_local_text_stubs"] = int(meta.get("no_text_anywhere_local", 0))
        out["audited"] = meta.get("audited", "")
    except sqlite3.Error:
        pass
    out["total"] = out["library_real_texts"] + out["library_fragments"] + out["library_recovered_texts"] + out["vault_real_texts"]
    return out


def main(argv):
    as_json = "--json" in argv
    args = [a for a in argv if a != "--json"]
    mx = 0
    if "--max" in args:
        i = args.index("--max"); mx = int(args[i + 1]); del args[i:i + 2]
    if not args:
        print(__doc__); return 2
    if args[0] == "--search":
        hits = search(" ".join(args[1:]), mx or 5)
        print(json.dumps(hits, ensure_ascii=False) if as_json else
              "\n".join(f"[{h['store']}] {h['video_id']} {h['title'][:70]}\n    {h['snippet']}" for h in hits))
        return 0 if hits else 1
    if args[0] == "--stats":
        s = stats()
        print(json.dumps(s) if as_json else "\n".join(f"{k}: {v:,}" if isinstance(v, int) else f"{k}: {v}" for k, v in s.items()))
        return 0
    hit = get(args[0], mx)
    if not hit:
        print(json.dumps({"video_id": clean_id(args[0]), "found": False}) if as_json else f"No transcript found for {args[0]}")
        return 1
    print(json.dumps(hit, ensure_ascii=False) if as_json else as_raw_file(hit))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
